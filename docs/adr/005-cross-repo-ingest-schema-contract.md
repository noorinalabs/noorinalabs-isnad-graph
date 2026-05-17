# ADR-005: Cross-repo schema contract for ingest-platform ⟷ isnad-graph

## Status: Accepted (Phase 3 / Wave 11)

## Context

Two repositories share an implicit schema contract:

- **noorinalabs-isnad-graph** owns the canonical Pydantic v2 models in `src/models/*.py` (Hadith, Narrator, Collection, Chain, Grading, HistoricalEvent, Location, and edge models).
- **noorinalabs-isnad-ingest-platform** owns per-label property allow-lists in `workers/ingest/schema.py` (`NODE_PROPERTY_MAP` and `EDGE_PROPERTY_MAP`). The ingest worker uses these to drive `MERGE … SET n.x = row.x` Cypher generation; any property name not in the allow-list is silently dropped before the Cypher statement is built.

The allow-list mechanism was introduced (PR #18 / closes #192) as a defensive measure: the original `SET n += row.props` was vulnerable to attacker-controlled keys (`:label`, `id`, future scholar-curated fields) overwriting node state. Hand-authored allow-lists fix that, but introduce a new failure mode the security fix did not: silent schema drift.

Without an automated contract:

- A new field on a Pydantic model that ingest's allow-list does not learn about is silently dropped during ingest. Discovery typically happens at the query layer, weeks later, when the field is read and returns null.
- A field renamed or removed on the Pydantic model that remains in the allow-list is silently merged into the graph with no Pydantic-side validation. Bad-data risk.
- A property the ingest layer legitimately needs but the model does not define (Phase-3 legacy denormalizations, defensive allow-list entries) has no place to live in the contract — it either looks like drift or gets forgotten.

Issue noorinalabs/noorinalabs-isnad-ingest-platform#24 was filed to formalize the contract.

## Decision

Adopt a **bidirectional drift gate** with **two asymmetric exceptions files**, run as a required CI check on this repo's PRs.

### Mechanism

1. **`scripts/emit_ingest_schema.py`** — a tool with two subcommands:
   - `emit` derives a `NODE_PROPERTY_MAP` / `EDGE_PROPERTY_MAP` Python literal from `model.model_fields` (via Pydantic v2 introspection), minus exclusions declared in `model-extras.yaml`. For codegen during model refactors.
   - `check` parses the live ingest `schema.py` (AST-based — no execution of ingest's runtime, which would require the sibling repo's full Python env) and reports drift in BOTH directions. Exit non-zero on any unrationalized divergence.

2. **`scripts/model-extras.yaml`** — model fields ingest deliberately omits, each with rationale + tracking issue. Categories: `merge-key` (matched in `MERGE` clause, never re-SET), `enrichment-only` (post-ingest Phase-4 fields that an unenriched batch must not wipe), `todo-rationalize` (explicitly undecided, never silently dropped).

3. **`scripts/ingest-extras.yaml`** — fields ingest accepts that the Pydantic model does not define, each with rationale + tracking issue. Categories: `phase-3-legacy` (denormalized fields emitted by normalize-v1; rationalization tracked in ingest-platform#35), `defensive`, `permanent`.

4. **`.github/workflows/schema-drift.yml`** — CI gate. Sparse-checkout sibling ingest repo (single file: `workers/ingest/schema.py`), wave-aware ref resolution (matches PR base branch when sibling has it, falls back to `main`), run `emit_ingest_schema.py check`, fail PR on non-zero exit.

### Failure modes the gate catches

- **Hard fail — model → ingest drop**: a Pydantic field on a model that ingest does NOT accept AND is NOT in `model-extras.yaml`. This is the silent-drop hazard #24 was filed to catch.
- **Hard fail — ingest → model phantom**: a field in ingest's allow-list that is NOT on the Pydantic model AND is NOT in `ingest-extras.yaml`. Catches the reverse hazard (model field renamed/removed but ingest still merging it).

## Alternatives Considered

### (a) Strict equality — `model_fields == ingest_allow_list`

Rejected. Forces churn-coupling between repos: every Phase-4 enrichment-only field added to the model (Narrator centrality / pagerank / community_id) would require a coordinated ingest PR or fail the gate. The asymmetry between "model is canonical schema" and "ingest is a particular consumer with its own constraints" is real and should be representable.

### (b) Lenient subset — `model_fields ⊆ ingest_allow_list`

Rejected after Round-2 dialog with the ingest-platform Architect surfaced bidirectional drift at `origin/deployments/phase-3/wave-11` HEAD: model has 3 Hadith fields not in ingest, ingest has 8 Hadith fields not in model. (b) would silently allow every model→ingest divergence — exactly the bug class #24 was filed to prevent. Subset is asymmetric in the wrong direction.

### (c) Single combined exceptions file

Rejected. Collapsing model-only-exclusions and ingest-only-additions into one file would hide which side is the source of truth and which is the consumer. The asymmetry IS the point — model is canonical, ingest is a downstream consumer with its own legacy + security constraints. Two files with distinct category enums make the asymmetry legible in code review and easier to grep.

### (d) Bidirectional drift with two exceptions files — **CHOSEN**

Bidirectional check correctly models the contract: both sides own a surface the other depends on. Two YAMLs reflect that the surfaces are asymmetric (different category vocabularies). Initial design from Round-2 had only `ingest-extras.yaml`; Round-3 added `model-extras.yaml` after identifying 5 Narrator Phase-4 enrichment-only fields that ingest deliberately omits per its own docstring, which would have failed the model→ingest direction without an explicit exception channel.

## Consequences

### Positive

- Silent prop-drops between model changes and ingest are now PR-time hard failures.
- The `todo-rationalize` category in `model-extras.yaml` gives schema designers a first-class place to defer a promote/keep decision without silently dropping the field. Decisions surface in CI rather than at the query layer.
- The `phase-3-legacy` category in `ingest-extras.yaml` routes all 12 denormalized normalize-v1 fields through a single tracking issue (ingest-platform#35) rather than scattering them across individual conversations.
- AST-based ingest parsing means this repo's CI does not need ingest-platform's runtime environment installed. Sibling sparse-checkout keeps the dependency surface to a single file.
- Wave-aware ref resolution per [feedback_cross_repo_wave_ref_resolution](https://github.com/noorinalabs/noorinalabs-main/blob/main/.claude/team/charter/) (deploy#159 W10 lesson): a wave-branch PR in this repo checks against the matching wave-branch in ingest-platform, with main fallback when the sibling does not have the branch yet.

### Negative / Trade-offs

- Adding a field to a Pydantic model now requires either (a) a coordinated cross-repo PR to expand ingest's allow-list, or (b) an entry in `model-extras.yaml` with rationale + tracking issue. This is by design — the friction is the contract.
- The script must remain in sync with the structure of ingest's `schema.py`. AST `literal_eval` on `NODE_PROPERTY_MAP` / `EDGE_PROPERTY_MAP` assumes both are top-level static dict literals; if ingest ever refactors to dynamic construction, the parser must adapt. The check raises a clear error if the expected literals are missing (not silent).
- `model-extras.yaml` and `ingest-extras.yaml` are hand-curated. Periodic review (proposed: per-wave) should aim to drain `todo-rationalize` and `phase-3-legacy` entries by resolving the underlying decisions, not by letting them accumulate.

### Per-relationship endpoint subtlety

Edge models include both endpoint fields (matched in `MERGE`) and SET-property fields. The same field name can be an endpoint on one relationship and a SET property on another — `location_id` is the TO-endpoint of `BASED_IN` but a SET property on `STUDIED_UNDER`. The codegen uses a per-relationship `EDGE_ENDPOINT_FIELDS` map (not a global endpoints set) to handle this correctly. Naive global-endpoint deduplication would mishandle `STUDIED_UNDER.location_id`.

## Migration / Rationalization Path

- 4 `todo-rationalize` entries (Hadith `topic_tags`, `has_shia_parallel`, `has_sunni_parallel`; Narrator `aliases`) need promote/keep decisions in Phase-4 planning. Tracked under #24 follow-up.
- 12 `phase-3-legacy` entries are bulk-tracked in ingest-platform#35 with three possible resolutions per entry: promote to model, keep ingest-only with `permanent` recategorization, or remove from ingest after query-layer migration.
- Periodic sweep proposed at each wave retrospective: count `todo-rationalize` + `phase-3-legacy` entries; rising counts indicate contract debt accumulating.

## References

- noorinalabs/noorinalabs-isnad-ingest-platform#24 — design issue
- noorinalabs/noorinalabs-isnad-ingest-platform#35 — phase-3-legacy rationalization tracking
- noorinalabs/noorinalabs-isnad-graph#919 — implementation PR (this repo)
- noorinalabs/noorinalabs-isnad-ingest-platform PR #18 — original allow-list mechanism (closes #192)
- `feedback_cross_repo_wave_ref_resolution` — wave-aware sibling ref resolution pattern (W10 deploy#159)
