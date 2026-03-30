# Comparative View — Wireframe Specification

**Author:** Sable Nakamura-Whitfield (Principal UX Designer)
**Issue:** #541
**Date:** 2026-03-29
**Status:** Draft

---

## 1. Design Intent

The comparative view enables side-by-side analysis of parallel hadith across Sunni and Shia collections. It answers the scholarly question: "How does the same tradition appear in different sources, what textual variations exist, and where do the isnad chains converge or diverge?"

The design uses a split-panel layout inspired by textual criticism tools. Diff highlighting draws the eye to variation without obscuring the base text. Chain comparison reveals shared narrators as structural evidence of common transmission pathways.

---

## 2. Page Layout

### 2.1 Desktop (>=1280px)

```
+-----------------------------------------------------------------------+
| HEADER: Isnad Graph > Comparative Analysis            [user avatar]   |
+-------+---------------------------------------------------------------+
| NAV   | SELECTOR BAR                                                  |
| SIDE  | [Select hadith A...] [vs] [Select hadith B...]  [+ Add C]     |
| BAR   | [Collection filter v] [Grade filter v]           [Reset]      |
| (220) +-----------------------------------+---------------------------+
|       | HADITH A                          | HADITH B                  |
|       | Bukhari 1                         | Muslim 1907               |
|       |                                   |                           |
|       | إنما الأعمال بالنيات وإنما لكل     | إنما الأعمال بالنيات وإنما  |
|       | امرئ ما نوى فمن كانت هجرته        | لكل امرئ ما نوى فمن كانت   |
|       | إلى دنيا يصيبها أو إلى امرأة      | هجرته إلى الله ورسوله       |
|       | ينكحها فهجرته إلى ما هاجر إليه    | فهجرته إلى الله ورسوله      |
|       |                                   | ومن كانت هجرته لدنيا        |
|       | ─────────────────────             | ─────────────────────     |
|       | "Actions are judged by            | "Actions are judged by    |
|       | intentions..."                    | intentions..."            |
|       |                                   |                           |
|       | Grade: Sahih                      | Grade: Sahih              |
|       | Similarity: 0.96                                              |
|       +-----------------------------------+---------------------------+
|       | CHAIN COMPARISON                                              |
|       |                                                               |
|       | A: Prophet → Umar → Alqama → M.Ibrahim → Yahya → Sufyan → B. |
|       | B: Prophet → Umar → Alqama → M.Ibrahim → Yahya → Malik → M.  |
|       |    ●━━━━━━●━━━━━━●━━━━━━●━━━━━━━━●┐                           |
|       |                                   ├→ ● Sufyan → ● Bukhari     |
|       |                                   └→ ● Malik  → ● Muslim      |
|       |    [shared]  [shared]  [shared]  [shared] [diverge]           |
|       +---------------------------------------------------------------+
|       | DIFF SUMMARY                                                  |
|       +---------------------------------------------------------------+
```

### 2.2 Tablet (768px–1279px)

```
+-----------------------------------------------------------------------+
| HEADER                                 [hamburger] [user avatar]      |
+-----------------------------------------------------------------------+
| [Select hadith A...] [vs] [Select hadith B...]                        |
| [Collection v] [Grade v]                              [Reset]         |
+-----------------------------------------------------------------------+
| HADITH A (full width)                                                 |
| Bukhari 1                                                             |
| [Arabic text]                                                         |
| [Translation]                                                         |
+-----------------------------------------------------------------------+
| HADITH B (full width)                                                 |
| Muslim 1907                                                           |
| [Arabic text]          (diff highlights inline)                       |
| [Translation]                                                         |
+-----------------------------------------------------------------------+
| CHAIN COMPARISON (full width, horizontal scroll)                      |
+-----------------------------------------------------------------------+
| DIFF SUMMARY                                                          |
+-----------------------------------------------------------------------+
```

- Hadith panels stack vertically instead of side-by-side
- Diff highlights shown inline within the text

### 2.3 Mobile (<768px)

```
+-----------------------------------+
| HEADER          [ham] [avatar]    |
+-----------------------------------+
| [Select A...] [vs] [Select B...] |
+-----------------------------------+
| [Tab: Hadith A] [Hadith B] [Diff]|
+-----------------------------------+
| (tab content)                     |
|                                   |
| [Arabic text with diff marks]    |
|                                   |
+-----------------------------------+
| Similarity: 0.96    [Full diff]  |
+-----------------------------------+
```

- Tab interface to switch between hadith A, hadith B, and diff view
- Chain comparison accessible via "Full diff" button (opens full-screen overlay)

---

## 3. Hadith Selector

### 3.1 Selector Bar

```
+-----------------------------------------------------------------------+
| [Select hadith A...]  [vs]  [Select hadith B...]   [+ Add C]         |
+-----------------------------------------------------------------------+
```

- Two search inputs for selecting hadith to compare
- Search accepts: hadith number (e.g., "Bukhari 1"), narrator name, or matn text
- Typeahead dropdown grouped by collection
- `[vs]` is a visual separator, not interactive
- `[+ Add C]` adds a third comparison column (maximum 3)
- Removing a hadith: [x] button within the selector input

### 3.2 Pre-populated Entry

When arriving from a hadith detail page's "Compare parallels" link:
- Hadith A is pre-filled with the source hadith
- Hadith B shows the top parallel by similarity score
- User can change either selection

### 3.3 Filter Controls

```
  [Collection filter v]              [Grade filter v]
  +----------------------------+     +-------------------+
  | [x] Bukhari               |     | [x] Sahih         |
  | [x] Muslim                |     | [x] Hasan         |
  | [x] Abu Dawud             |     | [ ] Da'if         |
  | [x] Tirmidhi              |     | [ ] Mawdu'        |
  | [x] al-Kafi (Shia)        |     +-------------------+
  | ...                        |
  +----------------------------+
```

- Filters apply to the typeahead search results, not to the displayed hadith
- Useful for cross-sectarian comparison (selecting both Sunni and Shia collections)

---

## 4. Hadith Comparison Panels

### 4.1 Side-by-Side Text

```
+-----------------------------------+----------------------------------+
| HADITH A: Bukhari 1              | HADITH B: Muslim 1907            |
+-----------------------------------+----------------------------------+
|                                   |                                  |
| إنما الأعمال بالنيات وإنما لكل    | إنما الأعمال بالنيات وإنما لكل   |
| امرئ ما نوى فمن كانت هجرته       | امرئ ما نوى فمن كانت هجرته      |
| [إلى دنيا يصيبها أو إلى امرأة]   | [إلى الله ورسوله فهجرته إلى]     |
| [ينكحها فهجرته إلى ما هاجر إليه] | [الله ورسوله ومن كانت هجرته]     |
|                                   | [لدنيا يصيبها أو إلى امرأة]     |
|                                   | [ينكحها فهجرته إلى ما هاجر إليه]|
| ─────────────────────             | ─────────────────────            |
| "Actions are judged by            | "Actions are judged by           |
| intentions, and each person       | intentions, and each person      |
| will get the reward according     | will get the reward according    |
| to what he intended.              | to what he intended.             |
| [So whoever emigrated for         | [So whoever emigrated to         |
| worldly benefits or for a woman]  | Allah and His Messenger, his     |
| [to marry, his emigration was     | emigration is to Allah and       |
| for what he emigrated for."]      | His Messenger. And whoever       |
|                                   | emigrated for worldly benefits]  |
|                                   | ..."                             |
+-----------------------------------+----------------------------------+
| Similarity: 0.96    |  Textual overlap: 78%                        |
+-----------------------------------------------------------------------+
```

- Panels scroll in sync (scrolling one scrolls the other)
- Diff-highlighted sections use background color:
  - Text unique to A: `oklch(70% 0.08 25)` — light red background
  - Text unique to B: `oklch(70% 0.08 150)` — light green background
  - Shared text: no highlight
- Diff operates at the word level for Arabic text, respecting word boundaries
- Brackets in the ASCII art above represent highlighted diff regions
- Both Arabic and English text are diff-highlighted

### 4.2 Three-Way Comparison

When a third hadith (C) is added:

```
+-------------------------+-------------------------+-------------------------+
| HADITH A: Bukhari 1    | HADITH B: Muslim 1907   | HADITH C: Tirmidhi 24  |
+-------------------------+-------------------------+-------------------------+
| [Arabic text]           | [Arabic text]            | [Arabic text]           |
| [Translation]           | [Translation]            | [Translation]           |
+-------------------------+-------------------------+-------------------------+
```

- Three equal-width columns
- Diff highlighting uses three colors (one per source)
- Similarity scores shown pairwise: A-B, A-C, B-C

### 4.3 Metadata Row

Below the text panels:

```
+-----------------------------------+----------------------------------+
| Collection: Sahih al-Bukhari      | Collection: Sahih Muslim         |
| Book: كتاب بدء الوحي               | Book: كتاب الإيمان                |
| Number: 1                         | Number: 1907                     |
| Grade: Sahih                      | Grade: Sahih                     |
| Chain length: 7                   | Chain length: 6                  |
+-----------------------------------+----------------------------------+
```

---

## 5. Chain Comparison

### 5.1 Merged Chain Graph

```
+-----------------------------------------------------------------------+
| CHAIN COMPARISON                              [Merged | Side-by-side] |
+-----------------------------------------------------------------------+
|                                                                       |
|  Prophet Muhammad                                                     |
|       │                                                               |
|       ▼                                                               |
|  Umar ibn al-Khattab          ── SHARED (both chains)                 |
|       │                                                               |
|       ▼                                                               |
|  Alqama ibn Waqqas            ── SHARED                               |
|       │                                                               |
|       ▼                                                               |
|  Muhammad ibn Ibrahim         ── SHARED                               |
|       │                                                               |
|       ▼                                                               |
|  Yahya ibn Sa'id              ── SHARED (divergence point)            |
|       ├────────────┐                                                  |
|       ▼            ▼                                                  |
|  Sufyan ibn       Malik ibn                                           |
|  'Uyayna          Anas                                                |
|  (A only)         (B only)                                            |
|       │            │                                                  |
|       ▼            ▼                                                  |
|  al-Bukhari       Muslim                                              |
|  (Compiler A)     (Compiler B)                                        |
|                                                                       |
+-----------------------------------------------------------------------+
```

- Merged view (default): shared narrators shown once, divergences branching
- Color encoding:
  - Shared nodes: neutral fill (#666)
  - A-only nodes: oklch(65% 0.15 250) — blue
  - B-only nodes: oklch(70% 0.15 60) — amber
- Shared edges: solid line
- Divergent edges: colored by source (A or B)
- Each narrator node is clickable (navigates to narrator detail)

### 5.2 Side-by-Side Chains

```
+---------------------------------+---------------------------------+
| CHAIN A (Bukhari 1)             | CHAIN B (Muslim 1907)           |
+---------------------------------+---------------------------------+
| Prophet Muhammad    ────────── ●| Prophet Muhammad ●              |
| Umar ibn al-Khattab ───────── ●| Umar ibn al-Khattab ●          |
| Alqama ibn Waqqas   ───────── ●| Alqama ibn Waqqas ●            |
| M. ibn Ibrahim      ───────── ●| M. ibn Ibrahim ●               |
| Yahya ibn Sa'id     ───────── ●| Yahya ibn Sa'id ●              |
| Sufyan ibn 'Uyayna            ●| Malik ibn Anas ●               |
| al-Bukhari                    ●| Muslim ●                        |
+---------------------------------+---------------------------------+
```

- Parallel columns with shared narrators aligned horizontally
- Connecting lines between shared narrators across columns
- Unique narrators are visually distinct (colored, no connector)

---

## 6. Diff Summary

```
+-----------------------------------------------------------------------+
| DIFF SUMMARY                                                          |
+-----------------------------------------------------------------------+
|                                                                       |
| Textual overlap:     78%  (word-level comparison)                     |
| Semantic similarity: 0.96 (CAMeLBERT cosine similarity)               |
| Shared narrators:    5 of 7 (A) / 6 (B)                              |
| Divergence point:    Yahya ibn Sa'id al-Ansari                        |
|                                                                       |
| Key textual differences:                                              |
| 1. Hadith B includes additional clause about emigrating "to Allah     |
|    and His Messenger" not present in A                                |
| 2. Hadith A has shorter conclusion                                    |
| 3. Wording of worldly emigration differs slightly                     |
|                                                                       |
| [Export comparison →]  [Citation →]                                   |
|                                                                       |
+-----------------------------------------------------------------------+
```

- Summary statistics at a glance
- Key differences enumerated
- "Export comparison" generates a formatted PDF/text with both texts and analysis
- "Citation" provides formatted academic citation for the comparison

---

## 7. RTL and Bidirectional Text

### 7.1 Arabic Text in Comparison Panels

- Each panel renders Arabic text in `dir="rtl"` blocks with `lang="ar"` and `--font-arabic`
- Diff highlighting backgrounds apply to Arabic words without breaking ligatures or diacritics
- Word-level diff algorithm respects Arabic word boundaries (space-delimited, with clitic awareness)

### 7.2 Synchronized Scrolling

- When panels are side-by-side, both scroll together vertically
- Arabic text (RTL) and English text (LTR) maintain their respective directions within each panel
- Horizontal scroll within a panel is independent (for long Arabic lines)

### 7.3 Font Stack

```css
--font-arabic: 'Noto Naskh Arabic', 'Geeza Pro', 'Traditional Arabic', serif;
--font-ui: system-ui, -apple-system, sans-serif;
```

---

## 8. Accessibility

### 8.1 Keyboard Navigation

| Key | Action |
|-----|--------|
| Tab | Move through: selector A > selector B > filters > panel A > panel B > chain > diff summary |
| Arrow left/right | Switch focus between comparison panels |
| Arrow up/down | Scroll within focused panel |
| Enter | Select hadith from dropdown, activate links in chain |
| Escape | Close dropdowns, deselect |
| d | Toggle diff highlighting on/off |

### 8.2 Screen Reader Support

- Page title: `<title>Compare Bukhari 1 vs Muslim 1907 — Isnad Graph</title>`
- Comparison panels: `role="region"` with `aria-label="Hadith A: Bukhari 1"` and `aria-label="Hadith B: Muslim 1907"`
- Diff highlights: inline `<mark>` elements with `aria-label="Text unique to Bukhari version"` / `aria-label="Text unique to Muslim version"`
- Chain comparison: accessible as `<ol>` with shared/unique status announced per node
- Diff summary: `aria-label="Comparison summary: 78% textual overlap, 0.96 semantic similarity, 5 shared narrators"`

### 8.3 High Contrast Mode

- Diff highlight colors become higher contrast (dark red/green backgrounds with white text)
- Chain shared/unique distinction adds pattern fills
- Panel borders become 2px solid black
- Connecting lines in chain comparison become 2px solid

### 8.4 Reduced Motion

- Panel scroll synchronization is instant
- Chain graph renders in final position without animation
- Diff highlights appear instantly

---

## 9. Responsive Breakpoint Summary

| Feature | Desktop (>=1280) | Tablet (768-1279) | Mobile (<768) |
|---------|:---:|:---:|:---:|
| Nav sidebar | Visible (220px) | Hamburger overlay | Hamburger overlay |
| Comparison layout | Side-by-side | Stacked | Tab view |
| Max hadith compared | 3 | 2 | 2 |
| Chain comparison | Merged + side-by-side toggle | Merged only | Full-screen overlay |
| Diff highlighting | Inline, synchronized | Inline, sequential | Inline per tab |
| Synchronized scroll | Yes | n/a (stacked) | n/a (tabs) |
| Export | PDF/text/citation | Text/citation | Citation only |
| Selector | Two inline inputs | Two inline inputs | Stacked inputs |

---

## 10. Component Mapping

| Wireframe element | Component | Notes |
|-------------------|-----------|-------|
| Page shell | `ComparativePage.tsx` | New page, route: `/compare/:idA/:idB` |
| Hadith selector | `HadithSelector` | Typeahead search, pre-populated from navigation |
| Comparison panel | `ComparisonPanel` | Renders text with diff highlighting |
| Diff engine | `TextDiffEngine` | Word-level Arabic-aware diff algorithm |
| Chain comparison | `ChainComparison` | Merged and side-by-side views |
| Diff summary | `DiffSummary` | Statistics and key differences |
| Export | `ComparisonExport` | PDF/text generation |

---

## 11. Design Tokens

```css
/* Comparison panels */
--panel-bg: #ffffff;
--panel-border: #e0e0e0;
--panel-gap: 1px;
--panel-divider: #d0d0d0;

/* Diff highlighting */
--diff-added-bg: oklch(92% 0.04 150);      /* light green */
--diff-removed-bg: oklch(92% 0.04 25);     /* light red */
--diff-added-bg-contrast: oklch(30% 0.08 150);  /* dark green (high contrast) */
--diff-removed-bg-contrast: oklch(30% 0.08 25); /* dark red (high contrast) */

/* Chain comparison */
--chain-shared-color: #666666;
--chain-a-color: oklch(65% 0.15 250);      /* blue */
--chain-b-color: oklch(70% 0.15 60);       /* amber */
--chain-c-color: oklch(60% 0.15 150);      /* green */

/* Similarity badge */
--similarity-high: oklch(60% 0.15 150);
--similarity-mid: oklch(70% 0.15 60);
--similarity-low: oklch(55% 0.10 0);
```

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-29 | Sable Nakamura-Whitfield | Initial wireframe specification |
