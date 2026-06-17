"""Emit and diff the cross-repo ingest schema allow-lists from Pydantic models.

This script is the source-of-truth bridge between the Pydantic models in
``src/models/`` (this repo) and the per-label property allow-lists in
``noorinalabs-isnad-ingest-platform/workers/ingest/schema.py`` (sibling repo).

Two subcommands:

- ``emit``  — write a ``NODE_PROPERTY_MAP`` / ``EDGE_PROPERTY_MAP`` Python literal
  derived from ``model.model_fields``, minus exclusions declared in
  ``model-extras.yaml``. Emits stdout by default; ``--out PATH`` writes to a file.
- ``check`` — fetch the live ingest ``schema.py`` (from a path you provide via
  ``--ingest-schema``), compare against the model + extras files, and exit
  non-zero on any unrationalized drift. This is what the schema-drift CI job
  runs to gate cross-repo PRs.

Drift is detected in BOTH directions:

  1. **Model → ingest drop**: a field on a Pydantic model that ingest does NOT
     accept AND is NOT excused by ``model-extras.yaml``. This is the failure
     case noorinalabs/noorinalabs-isnad-ingest-platform#24 was filed to catch.

  2. **Ingest → model phantom**: a field in ingest's allow-list that is NOT on
     the Pydantic model AND is NOT excused by ``ingest-extras.yaml``. Catches
     the inverse case (model field renamed/removed but ingest still merging).

The two YAML extras files (``scripts/ingest-extras.yaml`` and
``scripts/model-extras.yaml``) explicitly document the asymmetry between the
two surfaces with per-field rationale + tracking-issue refs.
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

# `from src.models...` imports resolve because `isnad-graph` is installed into the
# venv by `uv sync` (this script's CI invocation is `uv run python …`); no
# sys.path manipulation needed (#1095).


# Cypher node label → Pydantic model class. Order is preserved in emitted output.
NODE_LABEL_TO_MODEL_PATH: dict[str, tuple[str, str]] = {
    "Hadith": ("src.models.hadith", "Hadith"),
    "Narrator": ("src.models.narrator", "Narrator"),
    "Collection": ("src.models.collection", "Collection"),
    "Chain": ("src.models.chain", "Chain"),
    "Grading": ("src.models.grading", "Grading"),
    "HistoricalEvent": ("src.models.historical", "HistoricalEvent"),
    "Location": ("src.models.historical", "Location"),
}

# Cypher relationship type → edge model class. Relationships with no model-defined
# properties (NARRATED, GRADED_BY) are intentionally absent — they map to ``[]``
# in the emitted ``EDGE_PROPERTY_MAP``.
EDGE_LABEL_TO_MODEL_PATH: dict[str, tuple[str, str]] = {
    "TRANSMITTED_TO": ("src.models.edges", "TransmittedTo"),
    "APPEARS_IN": ("src.models.edges", "AppearsIn"),
    "STUDIED_UNDER": ("src.models.edges", "StudiedUnder"),
    "PARALLEL_OF": ("src.models.edges", "ParallelOf"),
    "ACTIVE_DURING": ("src.models.edges", "ActiveDuring"),
    "BASED_IN": ("src.models.edges", "BasedIn"),
}

# Edge labels that ingest accepts but for which there is no model-defined property
# allow-list (the edge carries no SET properties — only the relationship itself).
EDGE_LABELS_NO_PROPS: tuple[str, ...] = ("NARRATED", "GRADED_BY")

# Per-relationship FROM/TO endpoint fields. Matched in the MERGE clause and never
# re-SET on the relationship as properties. Per-relationship because the same field
# name can be an endpoint on one relationship and a SET property on another (e.g.
# `location_id` is the TO-endpoint of BASED_IN but a SET property on STUDIED_UNDER).
EDGE_ENDPOINT_FIELDS: dict[str, frozenset[str]] = {
    "TRANSMITTED_TO": frozenset({"from_narrator_id", "to_narrator_id"}),
    "APPEARS_IN": frozenset({"hadith_id", "collection_id"}),
    "STUDIED_UNDER": frozenset({"student_id", "teacher_id"}),
    "PARALLEL_OF": frozenset({"hadith_id_a", "hadith_id_b"}),
    "ACTIVE_DURING": frozenset({"narrator_id", "event_id"}),
    "BASED_IN": frozenset({"narrator_id", "location_id"}),
}


@dataclass(frozen=True)
class Extra:
    field: str
    category: str
    issue: str
    note: str


def _load_extras(path: Path) -> tuple[dict[str, list[Extra]], dict[str, list[Extra]]]:
    """Load a {nodes, edges} YAML extras file into per-label lists."""
    if not path.exists():
        return {}, {}
    raw = yaml.safe_load(path.read_text()) or {}
    nodes: dict[str, list[Extra]] = {}
    edges: dict[str, list[Extra]] = {}
    for section, target in (("nodes", nodes), ("edges", edges)):
        for label, entries in (raw.get(section) or {}).items():
            for entry in entries or []:
                target.setdefault(label, []).append(
                    Extra(
                        field=entry["field"],
                        category=entry["category"],
                        issue=entry["issue"],
                        note=entry.get("note", ""),
                    )
                )
    return nodes, edges


def _model_fields(module_path: str, class_name: str) -> list[str]:
    """Return ordered field names declared on a Pydantic model."""
    module = __import__(module_path, fromlist=[class_name])
    cls: type[BaseModel] = getattr(module, class_name)
    return list(cls.model_fields.keys())


def _emit_node_map(
    model_extras: dict[str, list[Extra]],
) -> dict[str, list[str]]:
    """Build the NODE_PROPERTY_MAP derived from models minus model-extras exclusions."""
    out: dict[str, list[str]] = {}
    for label, (mod, cls) in NODE_LABEL_TO_MODEL_PATH.items():
        excluded = {e.field for e in model_extras.get(label, [])}
        out[label] = [f for f in _model_fields(mod, cls) if f not in excluded]
    return out


def _emit_edge_map(
    model_extras: dict[str, list[Extra]],
) -> dict[str, list[str]]:
    """Build the EDGE_PROPERTY_MAP. Empty list for relationships with no props."""
    out: dict[str, list[str]] = {label: [] for label in EDGE_LABELS_NO_PROPS}
    for label, (mod, cls) in EDGE_LABEL_TO_MODEL_PATH.items():
        excluded = {e.field for e in model_extras.get(label, [])}
        endpoints = EDGE_ENDPOINT_FIELDS.get(label, frozenset())
        out[label] = [
            f for f in _model_fields(mod, cls) if f not in endpoints and f not in excluded
        ]
    return out


def _render_python_map(name: str, mapping: dict[str, list[str]]) -> str:
    """Render a {label: [fields]} dict as a stable Python literal for diffing."""
    lines = [f"{name}: dict[str, list[str]] = {{"]
    for label, fields in mapping.items():
        if not fields:
            lines.append(f'    "{label}": [],')
            continue
        lines.append(f'    "{label}": [')
        for field in fields:
            lines.append(f'        "{field}",')
        lines.append("    ],")
    lines.append("}")
    return "\n".join(lines)


def _parse_ingest_schema(text: str) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Extract NODE_PROPERTY_MAP and EDGE_PROPERTY_MAP literals from ingest schema.py.

    Uses ast.literal_eval on the assigned dict body — no execution of ingest code,
    which would require its full Python env. The ingest file is small and the maps
    are static literal assignments by convention; if that ever changes the parser
    will raise a clear error.
    """
    tree = ast.parse(text)
    found: dict[str, dict[str, list[str]]] = {}
    targets = {"NODE_PROPERTY_MAP", "EDGE_PROPERTY_MAP"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign | ast.Assign):
            continue
        target_names = (
            [node.target.id]
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
            else [t.id for t in getattr(node, "targets", []) if isinstance(t, ast.Name)]
        )
        for name in target_names:
            if name in targets and node.value is not None:
                found[name] = ast.literal_eval(node.value)
    missing = targets - found.keys()
    if missing:
        msg = f"ingest schema.py missing expected literals: {sorted(missing)}"
        raise ValueError(msg)
    return found["NODE_PROPERTY_MAP"], found["EDGE_PROPERTY_MAP"]


def _check_drift(
    model_node_map: dict[str, list[str]],
    model_edge_map: dict[str, list[str]],
    ingest_node_map: dict[str, list[str]],
    ingest_edge_map: dict[str, list[str]],
    ingest_extras_nodes: dict[str, list[Extra]],
    ingest_extras_edges: dict[str, list[Extra]],
) -> list[str]:
    """Return human-readable drift errors. Empty list means clean."""
    errors: list[str] = []

    def _check_one_direction(
        kind: str,
        model_map: dict[str, list[str]],
        ingest_map: dict[str, list[str]],
        ingest_extras: dict[str, list[Extra]],
    ) -> None:
        all_labels = set(model_map) | set(ingest_map)
        for label in sorted(all_labels):
            model_set = set(model_map.get(label, []))
            ingest_set = set(ingest_map.get(label, []))
            extras_set = {e.field for e in ingest_extras.get(label, [])}

            # Model → ingest drop
            for field in sorted(model_set - ingest_set):
                errors.append(
                    f"[{kind}:{label}] model field '{field}' is NOT in ingest "
                    f"NODE_PROPERTY_MAP/EDGE_PROPERTY_MAP and NOT in "
                    f"model-extras.yaml. Either add it to ingest's allow-list "
                    f"(cross-repo PR to ingest-platform) OR add an entry to "
                    f"scripts/model-extras.yaml explaining why ingest deliberately "
                    f"omits it (with category + tracking issue)."
                )

            # Ingest → model phantom
            for field in sorted(ingest_set - model_set - extras_set):
                errors.append(
                    f"[{kind}:{label}] ingest allow-list contains '{field}' which "
                    f"is NOT on the Pydantic model AND NOT in "
                    f"scripts/ingest-extras.yaml. Either remove it from ingest's "
                    f"allow-list (cross-repo PR) OR add an entry to "
                    f"scripts/ingest-extras.yaml documenting why ingest accepts a "
                    f"property the model doesn't define (with category + tracking issue)."
                )

    _check_one_direction("node", model_node_map, ingest_node_map, ingest_extras_nodes)
    _check_one_direction("edge", model_edge_map, ingest_edge_map, ingest_extras_edges)
    return errors


def cmd_emit(args: argparse.Namespace) -> int:
    _model_extras_nodes, _model_extras_edges = _load_extras(SCRIPTS_DIR / "model-extras.yaml")
    node_map = _emit_node_map(_model_extras_nodes)
    edge_map = _emit_edge_map(_model_extras_edges)
    output = "\n\n".join(
        [
            "# AUTO-GENERATED by noorinalabs-isnad-graph/scripts/emit_ingest_schema.py.",
            "# Source: src/models/*.py + scripts/model-extras.yaml.",
            "# DO NOT EDIT BY HAND — re-run emit_ingest_schema.py.",
            _render_python_map("NODE_PROPERTY_MAP", node_map),
            _render_python_map("EDGE_PROPERTY_MAP", edge_map),
        ]
    )
    if args.out:
        Path(args.out).write_text(output + "\n")
    else:
        sys.stdout.write(output + "\n")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    ingest_path = Path(args.ingest_schema)
    if not ingest_path.exists():
        sys.stderr.write(f"ingest schema not found: {ingest_path}\n")
        return 2

    _model_extras_nodes, _model_extras_edges = _load_extras(SCRIPTS_DIR / "model-extras.yaml")
    _ingest_extras_nodes, _ingest_extras_edges = _load_extras(SCRIPTS_DIR / "ingest-extras.yaml")

    model_node_map = _emit_node_map(_model_extras_nodes)
    model_edge_map = _emit_edge_map(_model_extras_edges)
    ingest_node_map, ingest_edge_map = _parse_ingest_schema(ingest_path.read_text())

    errors = _check_drift(
        model_node_map,
        model_edge_map,
        ingest_node_map,
        ingest_edge_map,
        _ingest_extras_nodes,
        _ingest_extras_edges,
    )
    if errors:
        sys.stderr.write(
            f"schema-drift: found {len(errors)} unrationalized divergence(s) between "
            f"noorinalabs-isnad-graph models and "
            f"noorinalabs-isnad-ingest-platform/workers/ingest/schema.py:\n\n"
        )
        for err in errors:
            sys.stderr.write(f"  - {err}\n\n")
        sys.stderr.write(
            "Fix by either (a) opening a cross-repo PR to ingest-platform to "
            "align the allow-list, OR (b) adding an entry to "
            "scripts/{ingest,model}-extras.yaml with a rationale + tracking "
            "issue. See noorinalabs/noorinalabs-isnad-ingest-platform#24 for the "
            "design.\n"
        )
        return 1
    sys.stdout.write(
        "schema-drift: clean. Models and ingest allow-list converge "
        "(after applying rationalized extras).\n"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    emit = sub.add_parser("emit", help="emit NODE_PROPERTY_MAP / EDGE_PROPERTY_MAP literal")
    emit.add_argument("--out", help="write to this path instead of stdout")
    emit.set_defaults(func=cmd_emit)

    check = sub.add_parser("check", help="diff models vs a live ingest schema.py")
    check.add_argument(
        "--ingest-schema",
        required=True,
        help="path to noorinalabs-isnad-ingest-platform/workers/ingest/schema.py",
    )
    check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
