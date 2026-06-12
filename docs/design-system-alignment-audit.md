# Design-System Alignment Audit — isnad-graph `frontend/`

**Issue:** [#967](https://github.com/noorinalabs/noorinalabs-isnad-graph/issues/967) · **Wave:** P4W3 · **Meta:** noorinalabs-main#637
**Author:** Ravi Wickramasinghe · **Date:** 2026-06-12

## Purpose

Verify that the isnad-graph React frontend **derives its styling from the shared
`@noorinalabs/design-system` (Qalam)** package rather than re-implementing tokens,
components, icons, color, and typography locally. This document is the audit; each
non-conforming surface is filed as a separate, parallelizable "align …" issue so the
remediation can be distributed across the team. **This audit does not fix the gaps.**

## Method

- Static read of `frontend/` (`src/`, `package.json`, `package-lock.json`, styles).
- DS contract cross-checked against the installed package
  (`node_modules/@noorinalabs/design-system/dist`) and the org ontology
  (`ontology/repos/design-system.yaml`).
- Searched for hand-rolled equivalents of DS exports (components, icons, tokens) and
  for hardcoded values (hex colors, ad-hoc inline styles) that bypass DS tokens.

## Summary verdict

The frontend is **partially DS-derived**. The component-primitive and token layers are
in good shape; the **icon layer is fully duplicated** from the DS, and the
**graph-visualization color layer is hand-rolled**. Inline-style usage is broad but
mostly token-backed (pattern divergence, not value divergence). No emoji icons found.

| Surface | Status | Notes |
|---|---|---|
| UI component primitives | ✅ Conforming | `src/components/ui/*` re-export Button, Input, Card, Badge, Tabs, Table, Select, Dialog from DS (thin barrel; local impls retired to git history). |
| Design tokens (color/spacing/type/radii/shadow/z) | ✅ Conforming | `src/styles/theme.css` imports `@noorinalabs/design-system/styles.css`; `common.css` (1090 ln), 3 CSS modules (184 ln), and inline styles consume DS CSS vars (`--color-*`, `--spacing-*`, `--text-*`, `--font-*`). |
| DS package pin | ✅ Conforming | `package.json` `^0.0.4-wave10.0`; lockfile resolves the same from GHCR npm. (Local `node_modules` was stale at 0.0.1 during audit — `npm ci` needed; dev-env caveat, not a repo defect.) |
| OAuth brand tokens + Google logo SVG | ✅ Legit app-specific | `theme.css` OAuth vars and `LoginPage` Google mark are provider-mandated; intentionally outside the DS. |
| **Icons (functional + decorative + illustrations)** | ❌ **Diverged** | `src/components/icons/{index,decorative,empty-states}.tsx` re-implement **16 components with the exact same names as DS exports** instead of importing them. → **Bucket A** |
| **Graph-viz colors (ForceGraph)** | ❌ **Diverged** | `COMMUNITY_HEX` 8-color palette + `ACCENT = '#1a73e8'` + hex fallbacks are hardcoded, not derived from DS tokens. → **Bucket B** (+ DS-gap **Bucket E**) |
| **Hardcoded color fallbacks / non-DS token names** | ⚠️ Minor diverged | Inline styles carry hex fallbacks (`#ef4444`, `#f59e0b`, `#22c55e`, `#fff`) and one **non-existent token** `--color-green-500` (DS uses `--color-success`). → **Bucket C** |
| **Ad-hoc inline `style={{}}` pattern** | ⚠️ Pattern divergence | 34 files use inline style objects (GraphExplorerPage: 78 occurrences). Values are mostly token-backed, but the pattern bypasses DS utility-class / layout composition. → **Bucket D** (lower priority) |

## Detailed findings

### ✅ Conforming surfaces

**Component primitives.** `frontend/src/components/ui/` is a re-export barrel
(`index.ts` + per-component files) pointing at `@noorinalabs/design-system`. Button,
Input, Card, Badge, Tabs, Table, Select, and Dialog all derive from the DS; the local
implementations are explicitly retired ("preserved in git history").

**Tokens.** `frontend/src/styles/theme.css` imports `tailwindcss` then
`@noorinalabs/design-system/styles.css`, and its own additions are scoped to
isnad-graph-specific OAuth brand vars + a base layer. The large `common.css` and the
CSS modules reference DS CSS custom properties throughout rather than literal values —
this is correct token derivation. 602 `className=` usages across the app lean on DS/
Tailwind utility classes.

### ❌ Bucket A — Icons duplicated from the design system (HIGH value)

`src/components/icons/` re-implements the **entire DS icon set, 1:1 by name**:

- `index.tsx` — `NarratorsIcon, HadithsIcon, CollectionsIcon, SearchIcon, TimelineIcon, CompareIcon, GraphExplorerIcon, AdminIcon, SignOutIcon` (9 functional)
- `decorative.tsx` — `GeometricBorder, OctagonalFrame, PageHeaderAccent` (3 decorative)
- `empty-states.tsx` — `NoResultsIllustration, EmptyGraphIllustration, NoDataIllustration, EmptyState` (4 illustration/empty-state)

All 16 names are exported by `@noorinalabs/design-system` (verified in
`dist/icons/index.d.ts` and `dist/index.cjs`). The local copies are consumed by
`Sidebar.tsx` and `HomePage.tsx` (and the illustrations by empty states). This is the
single clearest derivation gap: the app maintains a parallel icon library instead of
importing the shared one, so DS icon updates never reach isnad-graph.

Also in scope: 22 `.tsx` files contain raw inline `<svg>` markup; several are one-off
page illustrations (e.g. `ServerErrorPage`, `NotFoundPage`, `ForbiddenPage`,
`CheckEmailPage`) that may map onto DS illustrations.

### ❌ Bucket B — ForceGraph colors not derived from DS tokens

`src/components/ForceGraph.tsx` reads some theme colors from CSS vars (good) but defines
a **bespoke categorical palette** for community coloring:

```
const COMMUNITY_HEX = ['#4285f4','#e8a735','#34a853','#9c27b0','#ea4335','#00897b','#7cb342','#ad1457']
const ACCENT = '#1a73e8'
```

These hex values are hand-tuned (CVD/AA notes in comments) but are **not sourced from
DS tokens**, so they drift from the brand palette and dark-mode adjustments. Canvas can't
use `var()` directly, so remediation needs a token→resolved-hex bridge. **This depends
on the DS actually exposing a categorical/data-viz palette → Bucket E.**

### ⚠️ Bucket C — Hardcoded color fallbacks + a non-DS token name

Inline styles carry hardcoded color fallbacks that should be DS tokens, and one
reference to a **token that does not exist in the DS**:

- `VerifyEmailPage.tsx:105` — `var(--color-green-500, #22c55e)` → DS has **no** `--color-green-500`; the correct token is `--color-success`.
- `ProfilePage.tsx` — `var(--color-destructive, #ef4444)`, `var(--color-warning, #f59e0b)`, `color: '#fff'`.
- `UserMenu.tsx`, `AuthCallbackPage.tsx` — `var(--color-destructive…, #ef4444 / #fff)` fallbacks.

Small, safe, mechanical bucket: drop literal fallbacks and fix the wrong token name.

### ⚠️ Bucket D — Ad-hoc inline `style={{}}` pattern (lower priority)

34 components style via inline objects; the heaviest are `GraphExplorerPage` (78),
`admin/UserManagementPage` (26), `PricingPage` (26), `UserMenu` (19). Most values are
token-backed (`var(--spacing-*)`, `var(--color-*)`), so this is a **pattern** divergence
— bypassing DS utility-class / layout-primitive composition — rather than a value
divergence. Worth a gradual migration starting with the heaviest files; not urgent.

### ❌ Bucket E — DS-side gap (file against `noorinalabs-design-system`)

The DS lacks a **categorical / community "data-viz" color palette** that ForceGraph
(and the comparative/timeline views) need — CVD-distinguishable, AA on parchment and in
dark mode. Until the DS provides these as tokens, Bucket B cannot fully land. (Note also
the DS provides no `ThemeToggle`/`useTheme`; isnad-graph's local `ThemeToggle.tsx` +
`useTheme.ts` are acceptable app-level, but their data-theme contract must stay aligned
with DS token names.)

## Filed alignment-bucket issues

Tracked below; each links back to #967. (Issue numbers filled in on filing.)

| Bucket | Repo | Issue | Priority |
|---|---|---|---|
| A — adopt DS icons (retire local icon set) | isnad-graph | #978 | High |
| B — derive ForceGraph/graph-viz colors from DS tokens | isnad-graph | #979 | High (blocked by E) |
| C — remove hardcoded color fallbacks + fix `--color-green-500`→`--color-success` | isnad-graph | #980 | Medium (quick) |
| D — migrate ad-hoc inline `style={{}}` to DS utility/layout composition | isnad-graph | #981 | Low |
| E — add categorical/data-viz palette tokens | design-system | noorinalabs-design-system#102 | High (unblocks B) |

#967 stays **open as the audit/bucket-parent tracker** until all child buckets close.
