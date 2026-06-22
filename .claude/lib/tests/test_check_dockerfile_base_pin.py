"""Tests for check_dockerfile_base_pin — the Base Image Pinning gate (#735).

Verifies the deterministic conversion of `tech-decisions.md § Base Image
Pinning`: every FROM must be digest-pinned AND carry the matching distro
upgrade, with the section's exact exemptions (scratch, distroless, stage
references, vendor `# RATIONALE:`). Positive cases use the real required pattern
the section documents; negative cases use the exact prohibited shapes it names
(floating tag, pin-only, apk-only).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_dockerfile_base_pin import (  # noqa: E402
    check_dockerfile_text,
    main,
    parse_froms,
)

# A real digest (truncated only for readability is NOT allowed by the checker —
# it needs the literal `@sha256:` marker, which these carry in full shape).
_DIGEST = "@sha256:0272e4609f1b5f3a2d8c9e1a4b6c8d0e2f4a6b8c0d2e4f6a8b0c2d4e6f8a0b2c4"


class CompliantFromsPass(unittest.TestCase):
    def test_alpine_pinned_with_apk_upgrade(self) -> None:
        df = f"""# Digest-pinned tag + apk upgrade for defense-in-depth
FROM nginx:stable-alpine3.23{_DIGEST}
RUN apk upgrade --no-cache
"""
        self.assertEqual(check_dockerfile_text("Dockerfile", df), [])

    def test_debian_slim_pinned_with_apt_upgrade(self) -> None:
        df = f"""FROM python:3.12-slim{_DIGEST}
RUN apt-get update && apt-get -y upgrade && apt-get clean && rm -rf /var/lib/apt/lists/*
"""
        self.assertEqual(check_dockerfile_text("Dockerfile", df), [])

    def test_distroless_pin_only_is_sufficient(self) -> None:
        # Distroless has no package manager — pinned-only passes, no upgrade.
        df = f"FROM gcr.io/distroless/static-debian12{_DIGEST}\n"
        self.assertEqual(check_dockerfile_text("Dockerfile", df), [])

    def test_multistage_scratch_final_layer_exempt(self) -> None:
        df = f"""FROM golang:1.22-alpine{_DIGEST} AS builder
RUN apk upgrade --no-cache
RUN go build -o /app

FROM scratch
COPY --from=builder /app /app
"""
        self.assertEqual(check_dockerfile_text("Dockerfile", df), [])

    def test_multistage_stage_reference_inherits_pin(self) -> None:
        # `FROM builder` references an earlier stage; it inherits the pin and is
        # not re-checked for a digest or an upgrade.
        df = f"""FROM python:3.12-slim{_DIGEST} AS builder
RUN apt-get update && apt-get -y upgrade && apt-get clean

FROM builder
RUN pip install .
"""
        self.assertEqual(check_dockerfile_text("Dockerfile", df), [])

    def test_vendor_rationale_inline_comment_exempts(self) -> None:
        df = "FROM vendor/proprietary:1.4  # RATIONALE: not redistributable digest-pinned\n"
        self.assertEqual(check_dockerfile_text("Dockerfile", df), [])

    def test_vendor_rationale_preceding_comment_exempts(self) -> None:
        df = """# RATIONALE: vendor image, not available as a digest-pinned ref
FROM vendor/proprietary:1.4
"""
        self.assertEqual(check_dockerfile_text("Dockerfile", df), [])

    def test_platform_flag_is_stripped(self) -> None:
        df = f"""FROM --platform=linux/amd64 node:20-alpine{_DIGEST}
RUN apk upgrade --no-cache
"""
        self.assertEqual(check_dockerfile_text("Dockerfile", df), [])


class ProhibitedShapesFlagged(unittest.TestCase):
    def test_floating_tag_flagged(self) -> None:
        # WRONG (floating tag): no digest, no upgrade — both defenses missing.
        violations = check_dockerfile_text("Dockerfile", "FROM nginx:alpine\n")
        self.assertEqual(len(violations), 2)
        self.assertTrue(any("not digest-pinned" in v for v in violations))
        self.assertTrue(any("Alpine upgrade" in v for v in violations))

    def test_pin_only_alpine_missing_upgrade(self) -> None:
        # INSUFFICIENT (pin-only): tag frozen but Alpine packages drift — the
        # exact shape isnad-graph#853 hit.
        df = f"FROM nginx:stable-alpine3.23{_DIGEST}\n"
        violations = check_dockerfile_text("Dockerfile", df)
        self.assertEqual(len(violations), 1)
        self.assertIn("missing Alpine upgrade", violations[0])

    def test_apk_only_missing_digest(self) -> None:
        # INSUFFICIENT (apk-only): upgrade present but base layer is unpinned.
        df = "FROM nginx:alpine\nRUN apk upgrade --no-cache\n"
        violations = check_dockerfile_text("Dockerfile", df)
        self.assertEqual(len(violations), 1)
        self.assertIn("not digest-pinned", violations[0])

    def test_debian_pinned_missing_apt_upgrade(self) -> None:
        df = f"FROM python:3.12-slim{_DIGEST}\nRUN pip install .\n"
        violations = check_dockerfile_text("Dockerfile", df)
        self.assertEqual(len(violations), 1)
        self.assertIn("missing Debian upgrade", violations[0])

    def test_apt_update_only_is_not_an_upgrade(self) -> None:
        # `apt-get update` is not `apt-get upgrade`; pin present, upgrade absent.
        df = f"FROM debian:bookworm-slim{_DIGEST}\nRUN apt-get update\n"
        violations = check_dockerfile_text("Dockerfile", df)
        self.assertEqual(len(violations), 1)
        self.assertIn("missing Debian upgrade", violations[0])

    def test_line_number_reported(self) -> None:
        df = """# header comment
FROM nginx:alpine
RUN apk upgrade --no-cache
"""
        violations = check_dockerfile_text("Dockerfile", df)
        self.assertEqual(len(violations), 1)
        self.assertIn("Dockerfile:2:", violations[0])


class MultiStageMixed(unittest.TestCase):
    def test_compliant_builder_but_bad_runtime_flags_only_runtime(self) -> None:
        df = f"""FROM golang:1.22-alpine{_DIGEST} AS builder
RUN apk upgrade --no-cache
RUN go build -o /app

FROM nginx:alpine
COPY --from=builder /app /app
"""
        violations = check_dockerfile_text("Dockerfile", df)
        # builder is clean; only the floating runtime FROM is flagged (pin+upgrade).
        self.assertEqual(len(violations), 2)
        self.assertTrue(all("FROM nginx:alpine" in v for v in violations))


class ParserBehavior(unittest.TestCase):
    def test_parse_collects_stage_names_and_images(self) -> None:
        df = f"""FROM python:3.12-slim{_DIGEST} AS builder
FROM scratch
"""
        froms = parse_froms(df)
        self.assertEqual(len(froms), 2)
        self.assertEqual(froms[0].stage, "builder")
        self.assertTrue(froms[0].image.startswith("python:3.12-slim@sha256:"))
        self.assertEqual(froms[1].image, "scratch")

    def test_from_keyword_case_insensitive(self) -> None:
        df = f"from nginx:alpine{_DIGEST} as web\nRUN apk upgrade --no-cache\n"
        self.assertEqual(check_dockerfile_text("Dockerfile", df), [])


class CliBehavior(unittest.TestCase):
    def test_clean_file_exits_zero(self) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".dockerfile", delete=False) as fh:
            fh.write(f"FROM nginx:stable-alpine3.23{_DIGEST}\nRUN apk upgrade --no-cache\n")
            name = fh.name
        try:
            self.assertEqual(main(["check_dockerfile_base_pin.py", name]), 0)
        finally:
            Path(name).unlink()

    def test_violating_file_exits_one(self) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".dockerfile", delete=False) as fh:
            fh.write("FROM nginx:alpine\n")
            name = fh.name
        try:
            self.assertEqual(main(["check_dockerfile_base_pin.py", name]), 1)
        finally:
            Path(name).unlink()

    def test_no_args_is_usage_error(self) -> None:
        self.assertEqual(main(["check_dockerfile_base_pin.py"]), 2)

    def test_missing_file_is_error(self) -> None:
        self.assertEqual(main(["check_dockerfile_base_pin.py", "/no/such/Dockerfile"]), 2)


if __name__ == "__main__":
    unittest.main()
