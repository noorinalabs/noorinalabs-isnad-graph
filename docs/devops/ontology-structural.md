# Structural ontology index (distributed C×T2 pilot)

isnad-graph is the **polyglot pilot** for the distributed structural ontology
(parent meta noorinalabs-main#820 "C×T2", generator noorinalabs-main#855, this
repo's wiring isnad-graph#1128). This note records the distribution choice, the
operational tradeoffs to carry into the P7W1 six-repo fan-out, and the
polyglot-fidelity findings from running the generator on this repo's real
Python + TypeScript/React + Cypher source.

## What is committed here

Two generated artifacts under `ontology/structural/`:

- `code-graph.json` — one JSON document, one record per line:
  `{"nodes":[{id,kind,path,line,lang}],"edges":[{src,dst,type}]}`.
  `kind` is one of `file, module, class, func, method`; `type` is one of
  `contains, imports, imports_from, calls, inherits, references`.
- `llms.txt` — a scope-loadable summary, one `## <path> [lang]` section per
  file, so an agent can read one module's section instead of the whole graph.

Regenerate and re-commit them with `make structural-ontology` (or
`python3 scripts/structural_ontology.py emit`).

## Tool distribution: sibling-checkout, not vendoring

The generator (`ontology_gen`) is **owned by noorinalabs-main** and is
deliberately **not copied** into this repo. A vendored copy would fork: a fix to
the extractor in noorinalabs-main would silently not reach the consuming repos,
re-introducing the exact drift the owned-generator design exists to remove
(eval noorinalabs-main#854). Instead the generator is consumed from a single
source of truth:

- **CI** (`.github/workflows/structural-ontology.yml`) checks out
  noorinalabs-main as a sibling, resolving the ref to the matching wave branch
  with a `main` fallback — the established cross-repo pattern, the same shape as
  `.github/workflows/schema-drift.yml` (see the wave-ref resolution lesson from
  noorinalabs-deploy#159). It then runs
  `python3 scripts/structural_ontology.py check --gen-lib _main/.claude/lib`.
- **Local dev** relies on the standard org layout (child repos cloned beneath
  `noorinalabs-main/`); `scripts/structural_ontology.py` walks up to find the
  parent's `.claude/lib/ontology_gen` automatically. Set `ONTOLOGY_GEN_LIB` to
  override for a non-standard checkout.

The generator + wrapper are stdlib-only (zero runtime dependency), so neither CI
nor the local pre-commit hook needs a uv/pip/npm install to run the check.

### Staleness gate (local ⇄ CI parity)

A CI job and a `structural-ontology-staleness` pre-commit hook both run the same
`check` subcommand: regenerate the index into a temp dir and fail if it differs
from the committed copy. The `structural-ontology` kind is registered in
`.claude/lib/pre_commit_ci_sync.py`, so the sync-drift gate DEMANDS the local
mirror exist (the noorinalabs-main#684 full-parity contract — an un-classified
CI check is a silent blind spot).

The two sides differ in one respect: if the sibling generator cannot be located
LOCALLY (a developer without the parent repo, or a parent checkout on a branch
predating the generator), the pre-commit hook degrades to a warning and passes,
because CI is the authoritative gate. CI passes `--require-generator`, so a
missing generator there is a hard error, never a silent skip. A genuinely stale
or uncommitted index fails on both sides.

### Merge driver

`ontology/structural/code-graph.json` is a single committed artifact every
branch regenerates, so a plain text 3-way merge produces spurious conflicts on
the sorted node/edge arrays. `.gitattributes` maps the path to an
`ontology-codegraph` union merge driver. The driver script lives in the sibling
noorinalabs-main, so it is registered per-clone in git config by
`make setup-hooks` (which calls
`scripts/structural_ontology.py register-merge-driver`). Until it is registered,
git falls back to the normal text merge for that path.

## Tradeoffs to carry into the P7W1 fan-out

1. **Version coupling.** The committed index is coupled to the generator VERSION
   in noorinalabs-main. A generator change there can turn a consumer's staleness
   gate red until the index is regenerated and re-committed. This is expected for
   a drift gate, but the fan-out should sequence a generator change AHEAD of a
   coordinated consumer-repo index refresh, not land it and let six repos go red.
2. **Pre-merge ref resolution.** While the generator lives only on a wave branch
   (pre-merge), the sibling-ref resolver matches the consumer PR's base branch
   first and only then falls back to `main`. Once the generator merges to
   noorinalabs-main `main`, the `main` fallback is the steady state.
3. **Bootstrap order per repo.** Each fan-out repo must (a) add the wrapper +
   workflow + pre-commit hook + `.gitattributes` line, (b) register the
   `structural-ontology` sync-gate kind in its own copy of
   `pre_commit_ci_sync.py`, and (c) commit a first index in the same PR so the
   staleness gate is green on landing.
4. **Merge-driver invocation gotcha (flagged upstream).** `merge_driver.py` uses
   a package-relative import (`from .model import ...`), so the registration form
   in its own docstring (`python3 .../merge_driver.py ...`) raises ImportError.
   The working form is the Python MODULE form,
   `PYTHONPATH=<lib> python3 -m ontology_gen.merge_driver ...`, which is what
   `register-merge-driver` uses. The noorinalabs-main#855/#856 docstring +
   wiring should be corrected before the fan-out depends on it.

## Polyglot-fidelity findings

Run against this repo's real source (294 files: python 129, typescript 150,
javascript 3, cypher 11 — 1919 nodes / 2399 edges):

- **Python (`ast`-based): full fidelity.** Modules, classes, methods, functions,
  imports, and intra-file calls are all captured.
- **TypeScript/React (regex/line scanner): adequate for the contract
  granularity.** Real declarations are captured reliably — exported and default
  `function` declarations, arrow-function consts, and classes; 70% of `.ts`/`.tsx`
  files carry at least one symbol, and the zero-symbol remainder is legitimate:
  re-export barrels (captured as `references`), type-only modules, and test files
  with only `describe`/`it` blocks. No `forwardRef`/`memo`/anonymous-default
  misses were found in this repo. **Verdict: a tree-sitter backend is NOT needed
  yet** — it would buy per-call precision the contract does not even model.
- **The one real gap is the contract enum, not the TS backend.** ~82 exported
  `interface`/`type` declarations are invisible because the node-kind enum has no
  `interface`/`type` kind. For a TS-heavy product repo, types/interfaces are a
  large part of the API surface. **Recommendation for the fan-out:** extend the
  contract with `interface`/`type` node kinds (and optionally TS method
  extraction) BEFORE investing in tree-sitter.
- **Cypher (regex scanner → `llms.txt`): adequate.** Each query becomes one
  `file` node; node labels, relationship types, and clauses are extracted
  accurately and rendered into the file's `llms.txt` section (spot-checked
  against source). Labels/relationships are intentionally NOT minted as graph
  nodes (the enum has no such kind). **Verdict: Cypher-as-nodes is NOT needed**
  for the fan-out — the structural detail is already where an agent reads it.
