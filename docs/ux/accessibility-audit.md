# Accessibility Audit Report -- WCAG 2.2 AA

**Date:** 2026-03-29
**Auditor:** Priya Nair (QA Engineer)
**Scope:** Frontend (`frontend/src/`) -- all pages, components, and styles
**Standard:** WCAG 2.2 Level AA

---

## Summary

| Category                 | Status  | Details |
|--------------------------|---------|---------|
| Color Contrast           | PASS    | OKLCH palette designed for AA; comment in theme.css confirms all combinations verified |
| Keyboard Navigation      | WARNING | Most elements accessible; clickable table rows lack keyboard support |
| Screen Reader / ARIA     | WARNING | Good ARIA on detail pages; missing landmarks and labels on list pages |
| RTL / BiDi               | PASS    | Arabic text consistently uses `dir="rtl"` and `lang="ar"` |
| Motion                   | PASS    | `prefers-reduced-motion` handled in theme.css and ForceGraph |
| Form Labels              | WARNING | Some inputs missing explicit labels or `aria-label` |
| Focus Management         | PASS    | Dialog uses Radix (auto focus trap); focus-visible ring defined globally |
| Heading Hierarchy        | WARNING | Some pages skip heading levels |
| Semantic HTML / Landmarks | WARNING | Layout missing landmark roles on `<main>` and `<nav>` |

---

## Findings

### Critical

No critical violations found. The design system has been built with accessibility in mind.

### High

#### H1. Clickable table rows not keyboard-accessible (SC 2.1.1 Keyboard)

**Files:** `NarratorsPage.tsx:59-70`, `HadithsPage.tsx:35-58`, `CollectionsPage.tsx:32-49`, `ComparativePage.tsx:40-69`, `UserManagementPage.tsx:72-104`, `UsageAnalyticsPage.tsx:42-49`

Table rows with `onClick` handlers are not focusable and cannot be activated with keyboard. Screen reader users and keyboard-only users cannot navigate to individual records.

**Fix:** Add `tabIndex={0}`, `role="link"` (or `role="button"`), `onKeyDown` handler for Enter/Space, and `style={{ cursor: 'pointer' }}` to each clickable `<tr>`.

#### H2. Missing `aria-label` on search inputs (SC 1.3.1 Info and Relationships)

**Files:** `NarratorsPage.tsx:30-36`, `UserManagementPage.tsx:43-49`

Search `<input>` elements use `placeholder` as the only label. Placeholder text disappears on focus and is not announced as a label by all screen readers.

**Fix:** Add `aria-label="Search narrators"` (or equivalent) to each input.

#### H3. Missing labels on ModerationPage form inputs (SC 1.3.1)

**Files:** `ModerationPage.tsx:61-76`

The "Entity ID" and "Reason" inputs in the flag form use only `placeholder` as label text. The `<select>` for entity type also has no visible label.

**Fix:** Add `aria-label` attributes to each input and select.

#### H4. Feature flag checkboxes missing labels (SC 1.3.1)

**File:** `ConfigPage.tsx:217-219`

Feature flag checkboxes are associated with a `<span>` but not wrapped in a `<label>`. Screen readers will announce the checkbox without its name.

**Fix:** Wrap each checkbox + name in a `<label>` element.

#### H5. `<nav>` sidebar missing `aria-label` (SC 1.3.1)

**Files:** `Sidebar.tsx:17-76`, `AdminLayout.tsx:34`

The sidebar `<nav>` elements lack `aria-label` to distinguish them from other nav landmarks (e.g., breadcrumbs). Multiple `<nav>` elements on the same page require unique labels.

**Fix:** Add `aria-label="Main navigation"` and `aria-label="Admin navigation"`.

### Medium

#### M1. Layout `<main>` has no landmark role announcement

**File:** `Layout.tsx:26`

The `<main>` element exists but is fine. However, the outer `<div>` wrapping the page has no skip-navigation link for keyboard users to bypass the sidebar.

**Recommendation:** Add a "Skip to main content" link as the first focusable element.

#### M2. Clickable cells in ComparativePage use inline handlers (SC 2.1.1)

**File:** `ComparativePage.tsx:43-56`

Individual `<td>` cells have `onClick` but no keyboard activation or role.

**Fix:** Already covered by H1 if the entire row is made clickable, or add `tabIndex={0}` and `onKeyDown` to these cells.

#### M3. Heading hierarchy gaps

**Files:**
- `CollectionDetailPage.tsx:88` -- `<h2>` inside a card without a preceding page-level `<h1>`
- `ConfigPage.tsx:156` -- Uses `<h1>` ("System Configuration") when other admin pages use `<h2>`, creating an inconsistent hierarchy
- `NarratorDetailPage.tsx` -- Jumps from `<h2>` breadcrumb context to `<h4>` in metadata

**Fix:** Ensure each page has exactly one `<h1>` (could be the site title in the header) and content headings start at `<h2>`, descending sequentially.

#### M4. Zoom controls in GraphExplorerPage lack accessible names (SC 1.1.1)

**File:** `GraphExplorerPage.tsx:576-596`

Zoom buttons display "+" and "-" with `title` attributes but no `aria-label`. Title alone is not sufficient for all assistive technologies.

**Fix:** Add `aria-label="Zoom in"` and `aria-label="Zoom out"`.

#### M5. Graph search dropdown items not keyboard-navigable (SC 2.1.1)

**File:** `GraphExplorerPage.tsx:253-274`

The narrator search dropdown in the graph explorer does not support arrow key navigation or have ARIA listbox/option roles.

**Fix:** Add `role="listbox"` to the container and `role="option"` to each item, plus keyboard arrow navigation.

#### M6. Timeline SVG chart is not accessible (SC 1.1.1)

**File:** `TimelinePage.tsx:166`

The SVG timeline chart has no accessible name, no `role="img"`, and no `aria-label` or `<title>` element. Screen reader users cannot perceive the chart content.

**Fix:** Add `role="img"` and `aria-label="Timeline chart showing events from {range} AH"` to the `<svg>`.

### Low

#### L1. "Add Flag" button has no class/style (SC 1.4.11)

**File:** `ConfigPage.tsx:231`

The "Add Flag" button has no CSS class applied, so it uses browser default styling which may not match the design system's contrast requirements.

**Fix:** Add `className="btn"`.

#### L2. Pagination lacks `aria-label` on some pages

**Files:** `NarratorsPage.tsx:75`, `HadithsPage.tsx:63`, `CollectionsPage.tsx` (no pagination), `ComparativePage.tsx:74`, `UserManagementPage.tsx:107`, `ModerationPage.tsx:169`, `ConfigPage.tsx:278`

Pagination `<div>` elements should use `<nav aria-label="Pagination">` for screen reader identification.

**Fix:** Wrap pagination controls in `<nav aria-label="Page navigation">`.

#### L3. ForceGraph canvas has no text alternative (SC 1.1.1)

**File:** `ForceGraph.tsx:293-322`

The canvas-rendered graph has no accessible description. The parent container has `aria-label` which helps, but the canvas itself is opaque to screen readers.

**Recommendation:** This is inherent to canvas-based visualization. The detail panel provides text alternatives for selected nodes, which is an acceptable pattern. Consider adding an "accessible data table" toggle as a future enhancement.

#### L4. Color-only status indication in SystemHealthPage

**File:** `SystemHealthPage.tsx:9`

Status is communicated with both color and text ("Connected" / "Down"), which is correct. However, the color tokens used (success green vs. destructive red) should be verified for red-green color blindness. The ForceGraph community palette already addresses CVD.

**Status:** PASS -- text labels provide non-color fallback.

#### L5. `data-table` clickable rows lack hover focus indicator

**File:** `common.css:50-57`

`.clickable-row:hover` has a background change, but there is no corresponding `:focus-visible` or `:focus-within` style for keyboard navigation.

**Fix:** Add `.data-table tbody tr.clickable-row:focus-visible` style matching the hover style.

---

## Passes

1. **Color contrast (SC 1.4.3):** The OKLCH palette in `theme.css` was designed with WCAG AA contrast ratios. Both light and dark mode tokens provide sufficient contrast for text/background combinations.

2. **RTL/BiDi support (SC 1.3.2):** Arabic text consistently uses `dir="rtl"` and `lang="ar"` attributes. CSS uses logical properties (`margin-inline`, `padding-block`, `start`/`end`) throughout. The `<bdi>` element is used for mixed-direction content in search results.

3. **Reduced motion (SC 2.3.3):** `theme.css` includes `@media (prefers-reduced-motion: reduce)` that disables all animations and transitions. `ForceGraph.tsx` checks `prefers-reduced-motion` and skips simulation warmup.

4. **Focus visible (SC 2.4.7):** Global `:focus-visible` outline is defined in `theme.css` base layer. All Radix UI components (Button, Dialog, Select, Tabs) include `focus-visible:outline-*` classes.

5. **Dialog focus trap (SC 2.4.3):** Dialog component uses `@radix-ui/react-dialog` which automatically traps focus, returns focus on close, and supports Escape key dismissal. Close button has `aria-hidden` icon and `sr-only` text.

6. **ARIA on SearchPage (SC 4.1.2):** Search input uses `role="combobox"`, `aria-expanded`, `aria-haspopup="listbox"`, `aria-autocomplete="list"`, and `aria-activedescendant`. Typeahead items have `role="option"` and `aria-selected`. Results count uses `aria-live="polite"`.

7. **Semantic HTML in detail pages:** NarratorDetailPage and HadithDetailPage use `<dl>`/`<dt>`/`<dd>` for metadata, `<nav>` for breadcrumbs and pagination, `role="progressbar"` with proper aria-value attributes.

---

## Recommended Fix Priority

| Priority | Issue | Effort |
|----------|-------|--------|
| High     | H1: Clickable table rows keyboard access | Medium -- 6 files |
| High     | H2: Missing aria-label on search inputs | Low -- 2 files |
| High     | H3: ModerationPage form labels | Low -- 1 file |
| High     | H4: Feature flag checkbox labels | Low -- 1 file |
| High     | H5: Nav aria-labels | Low -- 2 files |
| Medium   | M4: Zoom button aria-labels | Low -- 1 file |
| Medium   | M5: Graph search dropdown ARIA | Medium -- 1 file |
| Medium   | M6: Timeline SVG accessible name | Low -- 1 file |
| Medium   | M1: Skip-to-content link | Low -- 1 file |
| Medium   | M3: Heading hierarchy | Low -- 3 files |
| Low      | L1: Add Flag button styling | Low -- 1 file |
| Low      | L2: Pagination nav landmarks | Low -- 6 files |
| Low      | L5: Clickable row focus style | Low -- 1 file |

---

## WCAG 2.2 Success Criteria Coverage

| SC | Name | Level | Status |
|----|------|-------|--------|
| 1.1.1 | Non-text Content | A | WARNING (M4, M6, L3) |
| 1.3.1 | Info and Relationships | A | WARNING (H2, H3, H4, H5) |
| 1.3.2 | Meaningful Sequence | A | PASS |
| 1.3.4 | Orientation | AA | PASS |
| 1.4.1 | Use of Color | A | PASS |
| 1.4.3 | Contrast (Minimum) | AA | PASS |
| 1.4.4 | Resize Text | AA | PASS (rem units throughout) |
| 1.4.11 | Non-text Contrast | AA | WARNING (L1) |
| 1.4.12 | Text Spacing | AA | PASS |
| 2.1.1 | Keyboard | A | WARNING (H1, M2, M5) |
| 2.1.2 | No Keyboard Trap | A | PASS |
| 2.4.1 | Bypass Blocks | A | WARNING (M1) |
| 2.4.2 | Page Titled | A | PASS |
| 2.4.3 | Focus Order | A | PASS |
| 2.4.6 | Headings and Labels | AA | WARNING (M3) |
| 2.4.7 | Focus Visible | AA | PASS |
| 2.5.3 | Label in Name | A | PASS |
| 3.1.1 | Language of Page | A | PASS |
| 3.1.2 | Language of Parts | AA | PASS |
| 3.2.1 | On Focus | A | PASS |
| 3.2.2 | On Input | A | PASS |
| 3.3.1 | Error Identification | A | PASS |
| 4.1.2 | Name, Role, Value | A | WARNING (H1, M4) |
