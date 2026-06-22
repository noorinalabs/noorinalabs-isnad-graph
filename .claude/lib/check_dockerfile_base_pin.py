#!/usr/bin/env python3
"""Lint Dockerfile `FROM` statements for digest-pin + distro-upgrade compliance.

Deterministic conversion of `.claude/team/charter/tech-decisions.md § Base Image
Pinning` (noorinalabs-main#735, the charter-prose-inventory worklist item #4 /
epic #726). The section requires every `FROM` to use a **digest-pinned tag**
(`image:tag@sha256:<digest>`) **combined with an in-image package upgrade**, to
close the two failure modes it names — floating-tag drift and within-tag package
drift (the shape isnad-graph#853 hit).

What this gate enforces (verbatim from the section's distro table)
================================================================
For every `FROM` that is not exempt:

1. The image reference MUST carry an `@sha256:` digest pin.
2. The stage MUST run the package-manager upgrade matching the base distro:

   | Family      | Pin shape               | Upgrade command                                 |
   |-------------|-------------------------|-------------------------------------------------|
   | Alpine      | image:tag@sha256:digest | `RUN apk upgrade --no-cache`                    |
   | Debian-slim | image:tag@sha256:digest | `apt-get update && apt-get -y upgrade && clean` |
   | Distroless  | image:tag@sha256:digest | none — no package manager (pinned-only is fine) |

   The distro family is inferred from the image name: `alpine` → Alpine,
   `distroless` → Distroless (no upgrade required), otherwise the glibc/Debian
   default (an apt upgrade is required). A genuinely-other base that has no
   package manager should carry the `# RATIONALE:` exemption below.

Exemptions honored (verbatim from the section)
=============================================
- **`scratch`** final/any layer — no package manager; the upstream stages that
  produced its contents still follow the rule and are checked on their own
  `FROM`.
- **Distroless** — pinned-only is sufficient (no package manager); the digest
  pin is still required.
- **Multi-stage stage reference** — a `FROM <earlier-stage>` inherits the
  upstream stage's pin, so it is not re-checked (the named stage was checked at
  its defining `FROM`).
- **Vendor images** documented with an inline `# RATIONALE:` comment on the
  `FROM` line (or the comment line immediately above it).

CLI
===
    python3 .claude/lib/check_dockerfile_base_pin.py <Dockerfile> [<Dockerfile> ...]

Exit codes:
    0 — every FROM in every file is compliant (or exempt)
    1 — at least one violation (each printed as `path:line: FROM <image> — <why>`)
    2 — usage / file-not-found error

This is a reusable template (same CLI/exit-code shape as
`.claude/lib/pre_commit_ci_sync.py`) so it wires identically into a repo's
pre-commit config and its CI. The parent repo `noorinalabs-main` ships no
Dockerfiles itself; the cross-repo rollout that points this at each child's
Dockerfiles is a #735 follow-up.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# `FROM` is the only keyword we parse; Dockerfile keywords are case-insensitive.
_FROM_RE = re.compile(r"^\s*FROM\s+(?P<rest>\S.*?)\s*$", re.IGNORECASE)
# A leading `--platform=...` flag precedes the image and must be stripped.
_PLATFORM_RE = re.compile(r"^--platform=\S+\s+", re.IGNORECASE)
# A trailing `AS <stage>` names the build stage.
_AS_RE = re.compile(r"\s+AS\s+(?P<stage>\S+)\s*$", re.IGNORECASE)

# Upgrade-command signatures per distro family (searched over the stage body).
_ALPINE_UPGRADE_RE = re.compile(r"\bapk\s+upgrade\b", re.IGNORECASE)
# `apt-get update && apt-get -y upgrade` / `apt upgrade` — an apt invocation
# followed (in the same command segment) by `upgrade`. `apt-get update` alone
# does NOT match (that is "update", not "upgrade").
_DEBIAN_UPGRADE_RE = re.compile(r"\bapt(?:-get)?\s+(?:-{1,2}\S+\s+)*upgrade\b", re.IGNORECASE)

_RATIONALE_RE = re.compile(r"#\s*RATIONALE:", re.IGNORECASE)


class FromStatement:
    """One parsed `FROM` line: its image ref, optional stage name, exemptions."""

    def __init__(self, lineno: int, image: str, stage: str | None, has_rationale: bool) -> None:
        self.lineno = lineno
        self.image = image
        self.stage = stage
        self.has_rationale = has_rationale


def _preceding_comment_has_rationale(lines: list[str], from_idx: int) -> bool:
    """True if the comment line(s) immediately above `from_idx` carry RATIONALE."""
    j = from_idx - 1
    while j >= 0:
        stripped = lines[j].strip()
        if stripped == "":
            j -= 1
            continue
        if stripped.startswith("#"):
            return bool(_RATIONALE_RE.search(stripped))
        return False
    return False


def parse_froms(text: str) -> list[FromStatement]:
    """Parse every `FROM` statement in a Dockerfile, in source order."""
    lines = text.splitlines()
    froms: list[FromStatement] = []
    for idx, raw in enumerate(lines):
        m = _FROM_RE.match(raw)
        if not m:
            continue
        rest = m.group("rest")
        has_rationale = bool(_RATIONALE_RE.search(raw)) or _preceding_comment_has_rationale(
            lines, idx
        )
        # Drop any trailing inline comment, then a leading --platform flag.
        code = rest.split("#", 1)[0].strip()
        code = _PLATFORM_RE.sub("", code).strip()
        stage: str | None = None
        as_m = _AS_RE.search(code)
        if as_m is not None:
            stage = as_m.group("stage")
            code = code[: as_m.start()].strip()
        image = code.split()[0] if code.split() else ""
        froms.append(FromStatement(idx + 1, image, stage, has_rationale))
    return froms


def _stage_body(text: str, from_lineno: int, next_from_lineno: int | None) -> str:
    """Return the text between a `FROM` (exclusive) and the next `FROM`/EOF."""
    lines = text.splitlines()
    start = from_lineno  # from_lineno is 1-based; body starts on the next line
    end = (next_from_lineno - 1) if next_from_lineno is not None else len(lines)
    return "\n".join(lines[start:end])


def check_dockerfile_text(path: str, text: str) -> list[str]:
    """Return a list of human-readable violation strings for one Dockerfile."""
    violations: list[str] = []
    froms = parse_froms(text)
    defined_stages: set[str] = set()
    for i, stmt in enumerate(froms):
        next_lineno = froms[i + 1].lineno if i + 1 < len(froms) else None
        image_l = stmt.image.lower()

        # Exemptions, in order. `scratch` and stage-references have no package
        # manager / inherit the upstream pin; a documented vendor RATIONALE opts
        # out explicitly. Record this stage's own name for later references.
        is_exempt = image_l == "scratch" or image_l in defined_stages or stmt.has_rationale
        if stmt.stage:
            defined_stages.add(stmt.stage.lower())
        if is_exempt:
            continue

        if "@sha256:" not in stmt.image:
            violations.append(
                f"{path}:{stmt.lineno}: FROM {stmt.image} — not digest-pinned "
                f"(require image:tag@sha256:<digest>)"
            )

        body = _stage_body(text, stmt.lineno, next_lineno)
        if "distroless" in image_l:
            continue  # distroless has no package manager; pinned-only is sufficient
        if "alpine" in image_l:
            if not _ALPINE_UPGRADE_RE.search(body):
                violations.append(
                    f"{path}:{stmt.lineno}: FROM {stmt.image} — missing Alpine upgrade "
                    f"step (RUN apk upgrade --no-cache)"
                )
        elif not _DEBIAN_UPGRADE_RE.search(body):
            violations.append(
                f"{path}:{stmt.lineno}: FROM {stmt.image} — missing Debian upgrade step "
                f"(RUN apt-get update && apt-get -y upgrade && apt-get clean)"
            )
    return violations


def check_file(path: Path) -> list[str]:
    return check_dockerfile_text(str(path), path.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    paths = argv[1:]
    if not paths:
        print(
            "usage: check_dockerfile_base_pin.py <Dockerfile> [<Dockerfile> ...]",
            file=sys.stderr,
        )
        return 2

    all_violations: list[str] = []
    for p in paths:
        path = Path(p)
        if not path.is_file():
            print(f"ERROR: not a file: {p}", file=sys.stderr)
            return 2
        all_violations.extend(check_file(path))

    if all_violations:
        print("Base Image Pinning violations (tech-decisions.md § Base Image Pinning, #735):")
        for v in all_violations:
            print(f"  {v}")
        print(
            "\nEvery FROM must be digest-pinned (image:tag@sha256:<digest>) AND carry "
            "the matching distro upgrade (apk/apt). Exemptions: scratch, distroless "
            "(pin-only), a FROM that references an earlier stage, or a vendor image with "
            "an inline `# RATIONALE:` comment on the FROM line."
        )
        return 1

    print("OK: all Dockerfile FROM statements are digest-pinned with the required upgrade.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
