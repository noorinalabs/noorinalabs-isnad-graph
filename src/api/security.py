"""Security utilities: input sanitization, Cypher audit helpers."""

from __future__ import annotations

import re
from pathlib import Path

# Allowed pattern for entity IDs: alphanumeric, hyphens, underscores, dots, colons.
# This prevents any Cypher injection via malformed IDs.
_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-_.:\u0600-\u06FF]+$")

# Maximum allowed length for entity IDs.
_MAX_ID_LENGTH = 256


def sanitize_id(value: str) -> str:
    """Validate and sanitize entity IDs to prevent injection.

    Args:
        value: The raw ID string from user input.

    Returns:
        The validated ID string (unchanged if valid).

    Raises:
        ValueError: If the ID contains disallowed characters or exceeds length limits.
    """
    if not value:
        msg = "ID must not be empty"
        raise ValueError(msg)
    if len(value) > _MAX_ID_LENGTH:
        msg = f"ID exceeds maximum length of {_MAX_ID_LENGTH}"
        raise ValueError(msg)
    if not _ID_PATTERN.match(value):
        msg = f"ID contains disallowed characters: {value!r}"
        raise ValueError(msg)
    return value


def audit_cypher_queries(root: Path | None = None) -> list[dict[str, str]]:
    """Scan all Cypher queries and Python files for string interpolation.

    All Cypher queries should use parameterized queries ($param syntax)
    rather than string interpolation (f-strings, .format(), %).

    Args:
        root: Project root directory. Defaults to repository root.

    Returns:
        List of findings, each with 'file', 'line', and 'issue' keys.
    """
    if root is None:
        root = Path(__file__).resolve().parent.parent.parent

    findings: list[dict[str, str]] = []

    # Patterns that indicate string interpolation in Cypher queries
    # f-string with MATCH/MERGE/CREATE/WHERE/RETURN/SET/DELETE
    cypher_keywords = r"(?:MATCH|MERGE|CREATE|WHERE|RETURN|SET|DELETE|REMOVE|DETACH|UNWIND)"
    fstring_pattern = re.compile(rf'f["\'].*{cypher_keywords}', re.IGNORECASE)
    format_pattern = re.compile(rf"\.format\(.*{cypher_keywords}", re.IGNORECASE)
    percent_pattern = re.compile(rf"%s.*{cypher_keywords}|{cypher_keywords}.*%s", re.IGNORECASE)

    # Known safe patterns: constraint creation uses f-string with a hardcoded allowlist
    # of node types (no user input). Flag but note as low-risk.
    constraint_pattern = re.compile(r"CREATE CONSTRAINT IF NOT EXISTS")

    _skip_dirs = {".venv", "__pycache__", ".git", "build", "dist", "node_modules", ".tox"}

    for py_file in root.rglob("*.py"):
        parts = py_file.parts
        if _skip_dirs & set(parts):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for line_num, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            for pattern, desc in [
                (fstring_pattern, "f-string interpolation in Cypher query"),
                (format_pattern, ".format() interpolation in Cypher query"),
                (percent_pattern, "%-formatting in Cypher query"),
            ]:
                if pattern.search(stripped):
                    risk = (
                        "LOW (hardcoded allowlist)"
                        if constraint_pattern.search(stripped)
                        else "HIGH"
                    )
                    findings.append(
                        {
                            "file": str(py_file.relative_to(root)),
                            "line": str(line_num),
                            "issue": f"{desc} [{risk}]",
                            "code": stripped[:120],
                        }
                    )

    return findings
