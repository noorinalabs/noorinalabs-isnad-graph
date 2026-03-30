# Hadith Detail — Wireframe Specification

**Author:** Sable Nakamura-Whitfield (Principal UX Designer)
**Issue:** #539
**Date:** 2026-03-29
**Status:** Draft

---

## 1. Design Intent

The hadith detail page presents a single hadith in full scholarly context: complete Arabic text with translation, the isnad chain rendered as a navigable visualization, grading assessments from multiple scholars, collection attribution, and parallel hadith across collections. The page should feel like a well-typeset critical edition — the text is primary, everything else supports close reading.

---

## 2. Page Layout

### 2.1 Desktop (>=1280px)

```
+-----------------------------------------------------------------------+
| HEADER: Isnad Graph > Bukhari > Book 1 > Hadith 1    [user avatar]   |
+-------+---------------------------------------------------------------+
| NAV   | HADITH TEXT (Arabic + Translation)                             |
| SIDE  +-------------------------------+-------------------------------+
| BAR   | ISNAD CHAIN VISUALIZATION     | GRADING & METADATA            |
| (220) | (flex: 1)                     | (360px)                       |
|       |                               |                               |
|       |  Prophet ──→ Umar ──→ ...     | Collection: Bukhari           |
|       |                               | Book: بدء الوحي (Revelation)   |
|       |                               | Number: 1                     |
|       |                               | Grade: Sahih                  |
|       |                               |                               |
|       +-------------------------------+-------------------------------+
|       | PARALLEL HADITH                                                |
|       +---------------------------------------------------------------+
|       | TOPICS & CLASSIFICATION                                        |
|       +---------------------------------------------------------------+
|       | CITATION & SHARE                                               |
|       +---------------------------------------------------------------+
```

### 2.2 Tablet (768px–1279px)

```
+-----------------------------------------------------------------------+
| HEADER                                 [hamburger] [user avatar]      |
+-----------------------------------------------------------------------+
| HADITH TEXT (full width)                                              |
+-----------------------------------------------------------------------+
| ISNAD CHAIN VISUALIZATION (full width)                                |
+-----------------------------------------------------------------------+
| GRADING & METADATA (full width)                                       |
+-----------------------------------------------------------------------+
| PARALLEL HADITH                                                       |
+-----------------------------------------------------------------------+
| TOPICS | CITATION                                                     |
+-----------------------------------------------------------------------+
```

### 2.3 Mobile (<768px)

```
+-----------------------------------+
| HEADER          [ham] [avatar]    |
+-----------------------------------+
| HADITH TEXT (compact)             |
+-----------------------------------+
| [Tab: Chain] [Grading] [Parallel] |
+-----------------------------------+
| (tab content)                     |
+-----------------------------------+
| CITATION (sticky bottom bar)     |
+-----------------------------------+
```

- Sections below hadith text reorganized into tabs to reduce scroll
- Citation/share as a sticky bottom bar for easy access

---

## 3. Hadith Text Section

```
+-----------------------------------------------------------------------+
|                                                                       |
|  بسم الله الرحمن الرحيم                                                 |  <- dir="rtl"
|                                                                       |
|  حدثنا الحميدي عبد الله بن الزبير قال حدثنا سفيان قال حدثنا           |
|  يحيى بن سعيد الأنصاري قال أخبرني محمد بن إبراهيم التيمي أنه          |
|  سمع علقمة بن وقاص الليثي يقول سمعت عمر بن الخطاب رضي الله            |
|  عنه على المنبر قال سمعت رسول الله صلى الله عليه وسلم يقول             |
|  إنما الأعمال بالنيات وإنما لكل امرئ ما نوى فمن كانت هجرته إلى        |
|  دنيا يصيبها أو إلى امرأة ينكحها فهجرته إلى ما هاجر إليه             |
|                                                                       |
|  ─────────────────────────────────────────────────────────────────     |
|                                                                       |
|  Narrated 'Umar bin Al-Khattab: I heard Allah's Messenger say,       |
|  "The reward of deeds depends upon the intentions and every           |
|  person will get the reward according to what he has intended.         |
|  So whoever emigrated for worldly benefits or for a woman to          |
|  marry, his emigration was for what he emigrated for."                |
|                                                                       |
+-----------------------------------------------------------------------+
```

- Arabic matn displayed in full, `dir="rtl"`, `lang="ar"`, using `--font-arabic` at 18px
- Horizontal divider separates Arabic from translation
- English translation below in `--font-ui` at 16px
- Isnad portion (chain of narration) visually distinguished from matn (text body) — the isnad text uses a slightly lighter color (#555) while the matn proper uses full black
- No truncation — full text always visible

---

## 4. Isnad Chain Visualization

### 4.1 Linear Chain View

```
+-----------------------------------------------+
| ISNAD CHAIN                    [Linear|Graph]  |
+-----------------------------------------------+
|                                               |
|  Prophet Muhammad                              |
|       │                                       |
|       ▼                                       |
|  Umar ibn al-Khattab                          |
|  Sahabi | Thiqah                ── click →     |
|       │                                       |
|       ▼                                       |
|  Alqama ibn Waqqas al-Laythi                  |
|  Tabi'i | Thiqah                              |
|       │                                       |
|       ▼                                       |
|  Muhammad ibn Ibrahim al-Taymi                |
|  Tabi' al-Tabi'in | Thiqah                    |
|       │                                       |
|       ▼                                       |
|  Yahya ibn Sa'id al-Ansari                    |
|  Tabi' al-Tabi'in | Thiqah                    |
|       │                                       |
|       ▼                                       |
|  Sufyan ibn 'Uyayna                           |
|  3rd gen. | Thiqah                            |
|       │                                       |
|       ▼                                       |
|  al-Humaydi                                   |
|  3rd gen. | Thiqah                            |
|       │                                       |
|       ▼                                       |
|  [al-Bukhari]  ── Compiler                    |
|                                               |
+-----------------------------------------------+
```

- Top-to-bottom flow: Prophet at top, compiler at bottom
- Each narrator node is clickable (navigates to narrator detail page)
- Node shows: name, generation, reliability — inline and compact
- Connector lines are 2px with directional arrows
- Reliability color-coded: green dot for Thiqah, amber for Saduq/Maqbul, red for Da'if — always with text label

### 4.2 Graph View

```
+-----------------------------------------------+
| ISNAD CHAIN                    [Linear|Graph]  |
+-----------------------------------------------+
|                                               |
|         ●                                     |
|        / \                                    |
|       ●   ●                                   |
|       |   |                                   |
|       ●   ●                                   |
|        \ /                                    |
|         ●                                     |
|         |                                     |
|         ●                                     |
|                                               |
+-----------------------------------------------+
```

- Toggle between linear and mini force-directed graph view
- Graph view useful when the hadith has multiple chains (e.g., mutawatir hadith)
- Same rendering engine as Graph Explorer ego-graph
- Nodes colored by generation

---

## 5. Grading & Metadata

```
+---------------------------------------+
| GRADING                               |
+---------------------------------------+
|                                       |
| PRIMARY GRADE: Sahih                  |
| ████████████████████████████░  Sahih  |
|                                       |
| +------------------+--------+         |
| | Scholar          | Grade  |         |
| +------------------+--------+         |
| | al-Bukhari       | Sahih  |         |
| | al-Albani        | Sahih  |         |
| | Shu'ayb Arna'ut  | Sahih  |         |
| +------------------+--------+         |
|                                       |
+---------------------------------------+
| METADATA                              |
+---------------------------------------+
|                                       |
| Collection:  Sahih al-Bukhari         |
|              (صحيح البخاري)            |
| Book:        كتاب بدء الوحي            |
|              (Book of Revelation)      |
| Chapter:     1                        |
| Hadith No.:  1                        |
| Volume:      1                        |
| Narrators:   7                        |
| Chain type:  Singular (ahad)          |
|                                       |
+---------------------------------------+
```

- Primary grade displayed prominently with a colored status bar
- Grade colors: green (Sahih), amber-green (Hasan), amber (Da'if), red (Mawdu') — always with text label
- Individual scholar grades in a compact table
- Metadata in definition-list format
- Collection name links to collection browse view
- Arabic book/chapter names displayed RTL

---

## 6. Parallel Hadith Section

```
+-----------------------------------------------------------------------+
| PARALLEL HADITH (4 found)                          [Sort: Similarity v]|
+-----------------------------------------------------------------------+
|                                                                       |
| +-------------------------------------------------------------------+ |
| | Muslim 1907                              Similarity: 0.96         | |
| | إنما الأعمال بالنيات...                                              | |
| | "Actions are judged by intentions..."                              | |
| | Grade: Sahih  |  Chain: 6 narrators  |  3 shared narrators        | |
| | [Compare →]                                                        | |
| +-------------------------------------------------------------------+ |
|                                                                       |
| +-------------------------------------------------------------------+ |
| | Abu Dawud 2201                           Similarity: 0.89         | |
| | إنما الأعمال بالنيات...                                              | |
| | "Deeds are only by intentions..."                                  | |
| | Grade: Sahih  |  Chain: 5 narrators  |  2 shared narrators        | |
| | [Compare →]                                                        | |
| +-------------------------------------------------------------------+ |
|                                                                       |
| +-------------------------------------------------------------------+ |
| | Nasa'i 75                                Similarity: 0.84         | |
| | ...                                                                | |
| +-------------------------------------------------------------------+ |
|                                                                       |
| +-------------------------------------------------------------------+ |
| | Ibn Majah 4227                           Similarity: 0.81         | |
| | ...                                                                | |
| +-------------------------------------------------------------------+ |
|                                                                       |
+-----------------------------------------------------------------------+
```

- Parallel hadith detected via Phase 4 semantic similarity (CAMeLBERT embeddings)
- Similarity score (cosine similarity) displayed prominently
- Shared narrator count shows chain overlap
- "Compare" button navigates to comparative view with these two hadith pre-loaded
- Sort options: Similarity (default), Collection, Grade

---

## 7. Topics & Classification

```
+-----------------------------------------------------------------------+
| TOPICS                                                                |
+-----------------------------------------------------------------------+
|                                                                       |
|  [Worship]  [Intention]  [Ethics]  [Migration]                        |
|                                                                       |
|  Theme: The role of intention (niyyah) in determining the             |
|  spiritual value of actions.                                          |
|                                                                       |
+-----------------------------------------------------------------------+
```

- Topic tags as clickable pills — clicking navigates to search filtered by that topic
- Brief thematic summary from Phase 4 topic classification
- Tags use neutral background colors with text labels

---

## 8. Citation & Share

```
+-----------------------------------------------------------------------+
| CITATION                                                              |
+-----------------------------------------------------------------------+
|                                                                       |
| Sahih al-Bukhari, Book 1, Hadith 1. Narrated by 'Umar ibn            |
| al-Khattab.                                                          |
|                                                                       |
| [Copy citation]  [Copy Arabic text]  [Copy translation]  [Share ↗]  |
|                                                                       |
+-----------------------------------------------------------------------+
```

- Pre-formatted citation string for academic use
- Copy buttons for: citation, Arabic matn, English translation
- Share button copies permalink URL to clipboard
- Success feedback: brief inline "Copied!" text replacing button label for 2 seconds

---

## 9. RTL and Bidirectional Text

### 9.1 Arabic Hadith Text

- Full matn rendered in `dir="rtl"` block, `lang="ar"`, `--font-arabic` at 18px
- Line height: 1.8 for Arabic text readability
- Isnad portion uses lighter color to distinguish from matn body
- Diacritics preserved in display (not stripped)

### 9.2 Mixed-Script Display

- Arabic and English texts in separate blocks, never interleaved on the same line
- Book and chapter names show Arabic first (RTL), English parenthetical after
- Collection names show both scripts

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
| Tab | Move through: hadith text > chain nodes > grading table > parallels > citation buttons |
| Enter | Activate links, chain node navigation, copy buttons |
| Arrow keys | Navigate chain nodes (up/down in linear view), parallel list |
| Escape | Close any dropdowns |

### 10.2 Screen Reader Support

- Page title: `<title>Bukhari 1 — Hadith Detail — Isnad Graph</title>`
- Hadith text section: `aria-label="Hadith text"` with Arabic announced via `lang="ar"`
- Chain visualization: rendered as `<ol>` with `aria-label="Isnad chain, 7 narrators from Prophet Muhammad to al-Bukhari"`
- Each chain node: "Umar ibn al-Khattab, Sahabi, trustworthiness Thiqah, link to narrator detail"
- Parallel section: `aria-label="4 parallel hadith found"`, each card as `role="article"`
- Copy button feedback: `aria-live="polite"` region announces "Citation copied to clipboard"

### 10.3 High Contrast Mode

- Chain connector lines become 2px solid black
- Grade status bar uses pattern fill in addition to color
- Parallel hadith card borders become 2px solid black
- Reliability dots replaced with icon + text

### 10.4 Reduced Motion

- Chain view toggle between linear/graph is instant
- Copy confirmation is text-only (no fade animation)

---

## 11. Responsive Breakpoint Summary

| Feature | Desktop (>=1280) | Tablet (768-1279) | Mobile (<768) |
|---------|:---:|:---:|:---:|
| Nav sidebar | Visible (220px) | Hamburger overlay | Hamburger overlay |
| Hadith text | Full width, 18px AR | Full width, 18px AR | Full width, 16px AR |
| Chain + Grading | Side by side | Stacked | Tab view |
| Chain visualization | Linear + Graph toggle | Linear + Graph toggle | Linear only |
| Parallel hadith | Card list | Card list | Condensed cards |
| Citation bar | Inline | Inline | Sticky bottom bar |

---

## 12. Component Mapping

| Wireframe element | Component | Notes |
|-------------------|-----------|-------|
| Page shell | `HadithDetailPage.tsx` | New page, route: `/hadith/:collection/:number` |
| Hadith text | `HadithTextDisplay` | RTL Arabic + LTR translation |
| Chain visualization | `ChainVisualization` | Shared with narrator detail page |
| Grading panel | `GradingPanel` | Table + status bar |
| Parallel list | `ParallelHadithList` | Cards with similarity scores |
| Topics | `TopicTags` | Clickable pill components |
| Citation | `CitationBar` | Copy buttons + share |

---

## 13. Design Tokens

```css
/* Hadith text */
--hadith-ar-font-size: 18px;
--hadith-ar-line-height: 1.8;
--hadith-en-font-size: 16px;
--hadith-en-line-height: 1.6;
--hadith-isnad-color: #555555;
--hadith-matn-color: #111111;

/* Grading */
--grade-sahih: oklch(60% 0.15 150);     /* green */
--grade-hasan: oklch(65% 0.12 120);     /* yellow-green */
--grade-daif: oklch(70% 0.15 60);       /* amber */
--grade-mawdu: oklch(55% 0.15 25);      /* red */

/* Parallel cards */
--parallel-card-bg: #ffffff;
--parallel-card-border: #e8e8e8;
--similarity-high: oklch(60% 0.15 150); /* >= 0.9 */
--similarity-mid: oklch(70% 0.15 60);   /* 0.7-0.9 */
--similarity-low: oklch(55% 0.10 0);    /* < 0.7 */
```

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-29 | Sable Nakamura-Whitfield | Initial wireframe specification |
