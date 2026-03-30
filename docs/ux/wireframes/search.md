# Search — Wireframe Specification

**Author:** Sable Nakamura-Whitfield (Principal UX Designer)
**Issue:** #537
**Date:** 2026-03-29
**Status:** Draft

---

## 1. Design Intent

The search view is the primary entry point for directed queries across hadith texts, narrators, collections, and topics. It supports both full-text keyword search and semantic (meaning-based) search, surfacing results as typed entity cards with faceted filtering.

The design treats search as a first-class research tool — not a simple text box. Result cards must communicate enough context to evaluate relevance without clicking through, while remaining scannable at volume. Arabic text is always rendered RTL with proper bidirectional isolation.

---

## 2. Page Layout

### 2.1 Desktop (>=1280px)

```
+-----------------------------------------------------------------------+
| HEADER: Isnad Graph > Search                          [user avatar]   |
+-------+---------------------------------------------------------------+
| NAV   | SEARCH BAR                                                    |
| SIDE  | [icon] Search hadith, narrators, collections...     [Search]  |
| BAR   | [Full-text ◉] [Semantic ○]                                    |
| (220) +-------------------+-------------------------------------------+
|       | FILTER SIDEBAR    | RESULTS                                   |
|       | (260px)           |                                           |
|       |                   | Showing 142 results for "ابو هريرة"       |
|       | ENTITY TYPE       | Sort: [Relevance v]                       |
|       | [x] Narrator (47) |                                           |
|       | [x] Hadith (82)   | +---------------------------------------+ |
|       | [ ] Collection(13)| | [Narrator Card]                       | |
|       |                   | | Abu Hurayra (ابو هريرة)               | |
|       | COLLECTION        | | Sahabi | d. 59 AH | 342 transmissions | |
|       | [x] Bukhari       | | Relevance: 0.97                       | |
|       | [x] Muslim        | +---------------------------------------+ |
|       | [ ] Abu Dawud     |                                           |
|       | [ ] Tirmidhi      | +---------------------------------------+ |
|       | ...               | | [Hadith Card]                         | |
|       |                   | | Bukhari 1 — كتاب بدء الوحي            | |
|       | GRADING           | | "Actions are judged by intentions..."  | |
|       | [x] Sahih         | | Chain: 5 narrators | Grade: Sahih      | |
|       | [x] Hasan         | | Relevance: 0.94                       | |
|       | [ ] Da'if         | +---------------------------------------+ |
|       |                   |                                           |
|       | CENTURY (AH)      | +---------------------------------------+ |
|       | [1st] [2nd] [3rd] | | [Collection Card]                     | |
|       | [4th] [5th+]      | | Sahih al-Bukhari (صحيح البخاري)        | |
|       |                   | | 7,563 hadith | 97 books               | |
|       | TOPIC             | | Compiler: Muhammad al-Bukhari         | |
|       | [ ] Jurisprudence | | Relevance: 0.91                       | |
|       | [ ] Theology      | +---------------------------------------+ |
|       | [ ] Ethics        |                                           |
|       |                   | [1] [2] [3] ... [15]  [Next →]           |
|       | [Clear filters]   |                                           |
+-------+-------------------+-------------------------------------------+
```

### 2.2 Tablet (768px–1279px)

```
+-----------------------------------------------------------------------+
| HEADER: Isnad Graph                        [hamburger] [user avatar]  |
+-----------------------------------------------------------------------+
| [icon] Search hadith, narrators, collections...            [Search]   |
| [Full-text ◉] [Semantic ○]           [Filters (3)]                   |
+-----------------------------------------------------------------------+
| Showing 142 results for "ابو هريرة"           Sort: [Relevance v]    |
+-----------------------------------------------------------------------+
| [Result Card]                                                         |
| [Result Card]                                                         |
| [Result Card]                                                         |
| ...                                                                   |
+-----------------------------------------------------------------------+
| [1] [2] [3] ... [Next →]                                             |
+-----------------------------------------------------------------------+
```

- Filter sidebar collapses into a modal triggered by `[Filters (N)]` button
- Nav sidebar becomes hamburger overlay

### 2.3 Mobile (<768px)

```
+-----------------------------------+
| HEADER          [ham] [avatar]    |
+-----------------------------------+
| [Search...]            [Filters]  |
| [Full-text] [Semantic]            |
+-----------------------------------+
| 142 results        [Relevance v]  |
+-----------------------------------+
| +-------------------------------+ |
| | Abu Hurayra (ابو هريرة)       | |
| | Sahabi | d. 59 AH             | |
| | Relevance: 0.97               | |
| +-------------------------------+ |
| +-------------------------------+ |
| | Bukhari 1                     | |
| | "Actions are judged by..."    | |
| | Sahih | 5 narrators           | |
| +-------------------------------+ |
| ...                               |
+-----------------------------------+
| [1] [2] [3] [Next →]             |
+-----------------------------------+
```

- Result cards stack vertically, full width
- Filters open as full-screen modal
- Search mode toggle displayed as compact pills

---

## 3. Search Bar

### 3.1 Input

```
+------------------------------------------------------------------+
| [magnifier] Search hadith, narrators, collections...       [x]   |
+------------------------------------------------------------------+
| SUGGESTIONS (typeahead, 300ms debounce)                          |
| ┌──────────────────────────────────────────────────────────────┐  |
| │ NARRATORS                                                    │  |
| │  Abu Hurayra (ابو هريرة)                    Sahabi, d.59 AH │  |
| │  Abu Hurayra al-Dawsi (ابو هريرة الدوسي)    Sahabi, d.59 AH │  |
| │                                                              │  |
| │ HADITH                                                       │  |
| │  "Actions are judged by intentions..." Bukhari 1, Sahih      │  |
| │  "Whoever believes in Allah..."        Abu Dawud 4, Hasan    │  |
| │                                                              │  |
| │ COLLECTIONS                                                  │  |
| │  Sahih al-Bukhari (صحيح البخاري)         7,563 hadith        │  |
| └──────────────────────────────────────────────────────────────┘  |
```

- Typeahead groups suggestions by entity type (max 3 per type)
- Arabic names right-aligned within each row using `dir="rtl"` inline
- Selecting a suggestion navigates directly to that entity's detail page
- Pressing Enter submits the query and shows full results below
- Keyboard: Arrow keys navigate suggestions, Enter selects, Escape closes dropdown

### 3.2 Search Mode Toggle

```
  [Full-text ◉]  [Semantic ○]
```

- **Full-text**: Keyword matching against indexed text fields (exact, stemmed, transliteration-normalized)
- **Semantic**: Vector similarity search against CAMeLBERT embeddings — finds hadiths with similar meaning even if wording differs
- Radio toggle — one mode active at a time
- Semantic mode shows a cosine similarity score instead of keyword relevance
- Tooltip on semantic: "Find hadith with similar meaning, even with different wording"

---

## 4. Filter Sidebar

### 4.1 Entity Type Filter

```
  ENTITY TYPE
  [x] Narrator (47)
  [x] Hadith (82)
  [ ] Collection (13)
```

- Checkbox group with result counts per type
- Counts update dynamically as other filters change
- At least one type must be selected (disabling the last checked box is prevented)

### 4.2 Collection Filter

```
  COLLECTION
  [x] Bukhari (34)
  [x] Muslim (28)
  [ ] Abu Dawud (12)
  [ ] Tirmidhi (8)
  [ ] Nasa'i (6)
  [ ] Ibn Majah (4)
  [Show all...]
```

- Top 6 collections shown by default, expandable
- Counts reflect current query results
- "Show all" reveals Shia collections (al-Kafi, etc.) and minor compilations

### 4.3 Grading Filter

```
  GRADING
  [x] Sahih (62)
  [x] Hasan (18)
  [ ] Da'if (12)
  [ ] Mawdu' (3)
```

### 4.4 Century Filter

```
  CENTURY (AH)
  [1st] [2nd] [3rd] [4th] [5th+]
```

- Segmented toggle buttons — multiple can be active
- Filters narrators by active lifetime, hadith by chain era

### 4.5 Topic Filter

```
  TOPIC
  [ ] Jurisprudence (fiqh)
  [ ] Theology (aqidah)
  [ ] Ethics (akhlaq)
  [ ] Worship (ibadah)
  [ ] History (sira)
  [ ] Eschatology
```

- Topic labels derived from Phase 4 topic classification output
- Only shown when hadith entity type is active

### 4.6 Clear Filters

```
  [Clear all filters]
```

- Resets all filters to defaults (all entity types, no collection/grading/century/topic filters)
- Only visible when at least one non-default filter is active

---

## 5. Result Cards

### 5.1 Narrator Result Card

```
+---------------------------------------------------------------+
| [person icon]  NARRATOR                     Relevance: 0.97   |
+---------------------------------------------------------------+
|                                                               |
|  ابو هريرة الدوسي                                              |  <- dir="rtl"
|  Abu Hurayra al-Dawsi                                         |
|                                                               |
|  Generation: Sahabi  |  Death: 59 AH  |  Sect: Sunni         |
|  342 transmissions  |  Trustworthiness: Thiqah               |
|                                                               |
|  Matched: name_ar, kunya                                      |  <- which fields matched
+---------------------------------------------------------------+
```

- Click navigates to narrator detail page
- "Matched" line shows which fields matched the query (visual cue for why this result appeared)

### 5.2 Hadith Result Card

```
+---------------------------------------------------------------+
| [document icon]  HADITH                     Relevance: 0.94   |
+---------------------------------------------------------------+
|                                                               |
|  إنما الأعمال بالنيات وإنما لكل امرئ ما نوى                    |  <- dir="rtl"
|  "Actions are judged by intentions, and each person            |
|   will be rewarded according to what they intended."           |
|                                                               |
|  Collection: Sahih al-Bukhari  |  Book 1, Hadith 1           |
|  Grading: Sahih  |  Chain: 5 narrators                       |
|  Topics: Worship, Ethics                                      |
|                                                               |
|  [View chain →]  [Compare parallels →]                        |
+---------------------------------------------------------------+
```

- Arabic matn displayed first (RTL), translation below (LTR)
- Matn text truncated to 2 lines with ellipsis; full text on detail page
- "View chain" navigates to hadith detail with chain visualization
- "Compare parallels" navigates to comparative view with this hadith pre-selected
- In semantic mode, relevance score shows cosine similarity (0.00–1.00)

### 5.3 Collection Result Card

```
+---------------------------------------------------------------+
| [book icon]  COLLECTION                     Relevance: 0.91   |
+---------------------------------------------------------------+
|                                                               |
|  صحيح البخاري                                                  |  <- dir="rtl"
|  Sahih al-Bukhari                                             |
|                                                               |
|  Compiler: Muhammad ibn Ismail al-Bukhari (d. 256 AH)        |
|  7,563 hadith  |  97 books  |  Sect: Sunni                   |
|  Canonical rank: #1 of Kutub al-Sittah                        |
|                                                               |
+---------------------------------------------------------------+
```

- Click navigates to collection detail/browse view

---

## 6. Results Header

```
  Showing 142 results for "ابو هريرة"              Sort: [Relevance v]
```

- Result count updates with filters
- Query string displayed — Arabic text rendered RTL with bidi isolation
- Sort options dropdown:
  - **Relevance** (default): search score descending
  - **Date (oldest)**: by death date / compilation date ascending
  - **Date (newest)**: descending
  - **Name (A-Z)**: alphabetical on English name
  - **Name (ا-ي)**: alphabetical on Arabic name (RTL sort order)

---

## 7. Pagination

```
  [← Prev]  [1] [2] [3] ... [15]  [Next →]
```

- 10 results per page (configurable in future)
- Current page visually distinguished (filled background)
- Prev/Next disabled at boundaries
- Page change scrolls to top of results area
- URL updates with page parameter for shareability

---

## 8. Empty and Error States

### 8.1 Initial Empty State (no query)

```
+-----------------------------------------------+
|                                               |
|        [search icon, muted]                   |
|                                               |
|  Search the hadith corpus                     |
|                                               |
|  Enter a narrator name, hadith text,          |
|  or topic to begin exploring.                 |
|                                               |
|  Try: Abu Hurayra, الأعمال بالنيات,            |
|       Sahih al-Bukhari, prayer                |
|                                               |
+-----------------------------------------------+
```

- Suggested queries are clickable — each populates the search bar and submits

### 8.2 No Results

```
+-----------------------------------------------+
|                                               |
|  No results found for "xyz"                   |
|                                               |
|  Suggestions:                                 |
|  - Try Arabic script: type the name in        |
|    Arabic for more precise matching            |
|  - Check transliteration: Abu vs. Aboo,       |
|    al- vs. el-                                |
|  - Try semantic search: toggle to find         |
|    similar meanings                            |
|  - Broaden filters: you have 3 active         |
|    filters narrowing results                  |
|                                               |
|  [Clear all filters]                          |
|                                               |
+-----------------------------------------------+
```

- Suggestions adapt: "Broaden filters" only shown when filters are active
- "Try semantic search" only shown when in full-text mode

### 8.3 Loading State

```
+-----------------------------------------------+
| [skeleton bar ████████░░░░░░░░]               |
| [skeleton card ░░░░░░░░░░░░░░░░░░░░░░]        |
| [skeleton card ░░░░░░░░░░░░░░░░░░░░░░]        |
| [skeleton card ░░░░░░░░░░░░░░░░░░░░░░]        |
+-----------------------------------------------+
```

- Skeleton cards match the shape of result cards
- Filter sidebar remains interactive during search loading
- Search bar shows a subtle progress indicator (thin animated line below input)

### 8.4 Error State

```
+-----------------------------------------------+
|                                               |
|  Search failed. Please try again.             |
|  [Retry]                                      |
|                                               |
+-----------------------------------------------+
```

---

## 9. RTL and Bidirectional Text

### 9.1 Arabic Text in Results

- All Arabic strings wrapped in `<bdi dir="rtl" lang="ar">` for proper isolation
- Hadith matn text displayed in a `dir="rtl"` block with `--font-arabic` font stack
- Search highlights within Arabic text respect character joining (never break ligatures)

### 9.2 Mixed-Script Display

- Result cards display Arabic name/text above English equivalent — never side-by-side on the same line
- Search bar accepts mixed-script input; typeahead normalizes diacritics and alif/hamza variants
- Sort by Arabic name uses proper collation (alif before ba, etc.)

### 9.3 Font Stack

```css
--font-arabic: 'Noto Naskh Arabic', 'Geeza Pro', 'Traditional Arabic', serif;
--font-ui: system-ui, -apple-system, sans-serif;
```

---

## 10. Accessibility

### 10.1 Keyboard Navigation

| Key | Action |
|-----|--------|
| Tab | Move through: search input > mode toggle > filter sidebar > results > pagination |
| Enter | Submit search / select suggestion / activate button |
| Arrow keys | Navigate typeahead suggestions |
| Escape | Close typeahead dropdown |
| / | Focus search input from anywhere on page |

### 10.2 Screen Reader Support

- Search input: `role="combobox"` with `aria-expanded`, `aria-activedescendant`
- Typeahead dropdown: `role="listbox"` with grouped `role="option"` items
- Result cards: `role="article"` with `aria-label` summarizing entity type and name
- Filter groups: `role="group"` with `aria-labelledby` pointing to section heading
- Pagination: `nav` landmark with `aria-label="Search results pagination"`
- Live region announces: "142 results found for Abu Hurayra" on search completion

### 10.3 High Contrast Mode

- Result card borders become 2px solid black
- Relevance score uses text label, never color-only encoding
- Entity type badges use pattern fill in addition to color
- Focus ring: 3px solid with offset

### 10.4 Reduced Motion

- Skeleton loading animation replaced with static placeholder blocks
- Typeahead dropdown appears instantly (no slide animation)

---

## 11. Responsive Breakpoint Summary

| Feature | Desktop (>=1280) | Tablet (768-1279) | Mobile (<768) |
|---------|:---:|:---:|:---:|
| Nav sidebar | Visible (220px) | Hamburger overlay | Hamburger overlay |
| Filter sidebar | Visible (260px) | Modal | Full-screen modal |
| Search mode toggle | Inline text | Inline text | Compact pills |
| Result cards | Full detail | Full detail | Condensed |
| Typeahead | Grouped, 3/type | Grouped, 2/type | Simple list |
| Pagination | Full numbered | Numbered | Prev/Next only |
| Sort dropdown | Visible | Visible | Icon button |

---

## 12. Component Mapping

| Wireframe element | Component | Notes |
|-------------------|-----------|-------|
| Page shell | `SearchPage.tsx` | New page component |
| Search bar | `SearchBar` | Combobox with typeahead, debounced API calls |
| Mode toggle | `SearchModeToggle` | Radio group: full-text / semantic |
| Filter sidebar | `SearchFilters` | Checkbox groups, segmented toggles |
| Narrator card | `NarratorResultCard` | Shared card component |
| Hadith card | `HadithResultCard` | Includes matn preview, chain link |
| Collection card | `CollectionResultCard` | Compact metadata display |
| Pagination | `Pagination` | Shared component |
| Empty state | `SearchEmptyState` | Contextual suggestions |

---

## 13. Design Tokens

```css
/* Search */
--search-input-height: 48px;
--search-input-bg: #ffffff;
--search-input-border: #d0d0d0;
--search-input-border-focus: var(--color-accent, #1a73e8);

/* Result cards */
--card-bg: #ffffff;
--card-border: #e8e8e8;
--card-border-hover: #c0c0c0;
--card-shadow-hover: 0 2px 8px rgba(0, 0, 0, 0.08);
--card-padding: 16px;
--card-gap: 12px;

/* Relevance badge */
--relevance-high: oklch(60% 0.15 150);   /* green, >= 0.9 */
--relevance-mid: oklch(70% 0.15 60);     /* amber, 0.7-0.9 */
--relevance-low: oklch(55% 0.10 0);      /* gray, < 0.7 */

/* Filter sidebar */
--filter-width: 260px;
--filter-section-gap: 20px;
```

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-29 | Sable Nakamura-Whitfield | Initial wireframe specification |
