# CI Job Name Audit Process

After ANY change to `.github/workflows/ci.yml` that renames or adds/removes jobs:

1. List current CI job names: `gh api repos/parametrization/isnad-graph/actions/workflows -q '.workflows[].name'`
2. Check branch protection required checks: `gh api repos/parametrization/isnad-graph/branches/main/protection/required_status_checks`
3. If mismatched, update branch protection:
   ```bash
   gh api repos/parametrization/isnad-graph/branches/main/protection/required_status_checks \
     -X PATCH --input - <<'EOF'
   {"strict": true, "contexts": ["lint-and-typecheck", "test", "security-audit"]}
   EOF
   ```
4. Verify: `gh pr checks <any-open-pr>` should show all required checks.

## Current Required Checks
- `lint-and-typecheck`
- `test`
- `security-audit`
