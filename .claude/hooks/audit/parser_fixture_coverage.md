# Parser-Fixture Coverage Audit — noorinalabs-isnad-graph

**Audit date:** 2026-05-07
**Auditor:** Anya Volkov
**Wave:** P3W7 (meta-issue: noorinalabs/noorinalabs-main#300)
**Hook count:** 6 registered hooks + 1 utility library (7 files total)

> **Note on inventory discrepancy:** Meta-issue #300 lists 9 isnad-graph hooks. Ground truth (settings.json + hooks/ directory scan) yields 6 registered standalone hooks + 1 utility (`annunaki_log.py`). The 2-hook gap is unresolved by available artifacts; this audit covers all 7 files present.

---

## Coverage Table

| Hook | Input Kind | Input Shapes Known | Fixtures Present | Gaps | Priority |
|------|-----------|-------------------|-----------------|------|----------|
| `validate_commit_identity.py` | JSON (hook envelope) + shell command string | git commit with/without -c flags, heredoc bodies, single/double-quoted strings, backslash continuation, `cd <repo> && git commit`, nested heredocs in double-quoted bash -c | Yes — `tests/test_validate_commit_identity.py` covers 18 cases across 4 test classes | Backslash line-continuation (tracked main#287); `git -c` ordering variants not covered | MEDIUM |
| `auto_set_env_test.py` | JSON (hook envelope) + shell command string | `pytest`, `uv run pytest`, `make test`, commands with/without `ENVIRONMENT=test`, gh commands with pytest in body | None — no test file exists | Full gap: no fixtures for any input shape | HIGH |
| `block_git_config.py` | JSON (hook envelope) + shell command string | `git config` write vs read-only (--get, --list, -l, --show-origin), chained commands | None — no test file exists | Full gap: read-only allowlist patterns not fixture-tested; `git config user.name` write shape untested | HIGH |
| `block_no_verify.py` | JSON (hook envelope) + shell command string | `git commit --no-verify`, commit without flag, chained commands with --no-verify in non-commit position | None — no test file exists | Full gap: substring false-positive risk on `git commit --no-verify-sig` or body text not covered | HIGH |
| `validate_labels.py` | JSON (hook envelope) + shell command string + gh API JSON response | `gh issue create --label "val"`, `--label 'val'`, comma-separated labels, `-l val`, no labels, gh issue list (negative), cwd-relative paths | None — no test file exists | Full gap: extract_labels regex not tested; comma-split not fixture-tested; negative case (gh issue list must not match) absent | HIGH |
| `validate_pr_ci_status.py` | JSON (hook envelope) + shell command string + gh API JSON (statusCheckRollup) | `gh pr merge <N>`, `--admin` bypass, `--auto` pending, chained commands with env-var prefixes, statusCheckRollup shapes (bucket/conclusion/status), NEUTRAL bucket | None — no test file exists | Full gap: classify_check logic not fixture-tested; is_merge_command segment splitting not tested; NEUTRAL allowlist absent (parent has it, child copy does not) | HIGH |
| `annunaki_log.py` | Python function calls (not a hook) | log_pretooluse_block call signature | None | Utility library — fixture coverage not required; no input parsing | N/A |

---

## Summary Statistics

| Category | Count |
|----------|-------|
| Total files | 7 |
| Standalone hooks (registered) | 6 |
| Utility libraries | 1 |
| Parser-class hooks | 6 |
| Non-parser hooks | 0 |
| Hooks with fixture coverage | 1 |
| Hooks with zero fixtures | 5 |
| Gap count (fixture files missing entirely) | 5 |
| In-wave Pattern G fixes applied | 1 (see below) |

---

## Parser Classification Detail

All 6 registered hooks are parser-class: every hook reads `input_data.get("tool_name")` and `input_data.get("tool_input", {}).get("command", "")` from JSON stdin, then applies regex or structural parsing to the command string. There are no non-parser hooks in this repo's local inventory.

---

## Gap Detail

### H1 — `auto_set_env_test.py` (HIGH)

**Input shapes requiring fixtures:**
1. `pytest tests/` — basic match, no ENVIRONMENT prefix → block
2. `ENVIRONMENT=test pytest tests/` — already set → allow
3. `make test` — match, no ENVIRONMENT → block
4. `uv run pytest tests/` — match → block
5. `gh pr create --body "run pytest"` — `gh` argv[0] skip → allow (charter hook 4 skip conditions not implemented in child copy; see Pattern G below)
6. `gh pr comment --body "make test passes"` — `--body` flag skip → allow
7. `echo 'pytest'` — pytest in non-command position → allow (current regex `\bpytest\b` would MATCH this — potential false positive)

**Critical gap:** Shape 7 is an unguarded false positive. `re.search(r"\bpytest\b", command)` matches `echo 'running pytest locally'`. Charter hook 4 § Skip Conditions specifies two short-circuits (gh argv[0] and --body/--body-file flags) that are present in the parent version but absent from the child local copy.

### H2 — `block_git_config.py` (HIGH)

**Input shapes requiring fixtures:**
1. `git config user.name "Alice"` — write → block
2. `git config --global user.email "a@b.c"` — global write → block
3. `git config --get user.name` — read-only → allow
4. `git config --list` — read-only → allow
5. `git config -l` — read-only short flag → allow
6. `git config --show-origin` — read-only → allow
7. `grep "something" && git config user.name x` — chained write → block
8. `echo "git config user.name" | cat` — substring in non-command position → allow (not tested; current regex `\bgit\s+config\b` would match this false positive)

### H3 — `block_no_verify.py` (HIGH)

**Input shapes requiring fixtures:**
1. `git commit --no-verify -m "x"` → block
2. `git commit -m "x"` — clean → allow
3. `git push --no-verify` — not a commit → allow (current regex `\bgit\b.*\bcommit\b` would match `git commit` in `git push --no-verify` only if "commit" appears — edge case: `git push && git commit --no-verify` in chain needs test)
4. `echo "--no-verify"` — not a git command → allow
5. `git stash --no-verify` — not commit → allow (regex matches stash if "commit" also present in command)

**Pattern G fix applied:** The check `if "--no-verify" not in command` uses plain string search, not word-boundary regex — `--no-verify-sig` would not match (correct), but this is not documented.

### H4 — `validate_labels.py` (HIGH)

**Input shapes requiring fixtures:**
1. `gh issue create --label "bug"` — single label → validate
2. `gh issue create --label "bug,enhancement"` — comma-separated → validate both
3. `gh issue create --label 'tech-debt' --label 'phase-3'` — multiple flags → validate both
4. `gh issue create -l "p3-wave-7"` — short form → validate
5. `gh issue create` — no labels → allow (skip)
6. `gh issue list --label "bug"` — not create → allow (current regex `\bgh\s+issue\s+create\b` correctly excludes this)
7. `gh issue create --label "nonexistent-label"` — missing label → block
8. Network failure path → warn-allow

**Negative case gap:** `gh issue list` shape (6) is correctly excluded by the regex, but no fixture pins this. The W6 bug #294 pattern (head_ref shape causing false positives) could recur if the regex is ever widened.

### H5 — `validate_pr_ci_status.py` (HIGH)

**Input shapes requiring fixtures:**
1. `gh pr merge 123` — merge command → check CI
2. `gh pr merge 123 --admin` → allow (skip)
3. `gh pr merge 123 --auto` with pending checks → warn-allow
4. `VAR=x gh pr merge 123` — env-var prefix → requires `is_merge_command` segment stripping
5. `gh pr list` — not merge → allow (critical negative case)
6. `gh pr merge 123 --repo noorinalabs/noorinalabs-isnad-graph` — `--repo` extraction
7. statusCheckRollup with `bucket: "fail"` → fail verdict
8. statusCheckRollup with `status: "QUEUED"` → pending verdict
9. statusCheckRollup with `status: "COMPLETED"`, `conclusion: ""` → pass verdict
10. statusCheckRollup with `conclusion: "NEUTRAL"` → pass (parent has NEUTRAL_PENDING allowlist for chromatic; child copy does not)
11. Empty rollup `[]` → allow (no checks)
12. `fetch_checks` returns None (network failure) → warn-allow

**Divergence from parent:** The child `validate_pr_ci_status.py` does not include the NEUTRAL pending-check allowlist (`_NEUTRAL_PENDING_CHECK_NAMES`) that the parent added in P3W4 T5 (resolves isnad-graph#219 per parent charter). This is a functional regression — Chromatic `NEUTRAL` would allow merge when it should pend.

---

## Pattern G Observations (In-Wave Fix Opportunities)

### PG-1 — `auto_set_env_test.py`: Missing skip conditions (one-line obvious)

The parent version of this hook includes two short-circuit conditions (gh argv[0] skip, --body/--body-file skip) per charter Hook 4 § Skip Conditions. The child local copy omits them. This is a literal copy-drift — the fix is adding the same short-circuit block from the parent.

**Fix applied in this PR:** Yes — added gh/--body skip conditions to `auto_set_env_test.py` (Pattern G in-wave fix).

### PG-2 — `validate_pr_ci_status.py`: Missing NEUTRAL allowlist

The parent version includes `_NEUTRAL_PENDING_CHECK_NAMES = {"chromatic"}` and consults it in `classify_check`. Child copy is missing this. This is a functional regression enabling PRs to merge while Chromatic visual-regression review is pending.

**In-wave fix:** Deferred — requires reading isnad-graph#219 context and understanding if chromatic is active in this repo. Filed as backport issue (see below).

---

## Backport Issues Filed

| Issue | Title | Labels | Priority |
|-------|-------|--------|----------|
| [isnad-graph#866](https://github.com/noorinalabs/noorinalabs-isnad-graph/issues/866) | add parser-fixture coverage for auto_set_env_test hook | tech-debt, phase-3 | HIGH |
| [isnad-graph#867](https://github.com/noorinalabs/noorinalabs-isnad-graph/issues/867) | add parser-fixture coverage for block_git_config hook | tech-debt, phase-3 | HIGH |
| [isnad-graph#868](https://github.com/noorinalabs/noorinalabs-isnad-graph/issues/868) | add parser-fixture coverage for block_no_verify — includes false-positive on git stash --no-commit | tech-debt, phase-3 | HIGH |
| [isnad-graph#869](https://github.com/noorinalabs/noorinalabs-isnad-graph/issues/869) | add parser-fixture coverage for validate_labels hook | tech-debt, phase-3 | HIGH |
| [isnad-graph#870](https://github.com/noorinalabs/noorinalabs-isnad-graph/issues/870) | add parser-fixture coverage + NEUTRAL allowlist sync for validate_pr_ci_status | tech-debt, phase-3 | HIGH |
