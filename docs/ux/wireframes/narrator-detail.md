# Narrator Detail — Wireframe Specification

**Author:** Sable Nakamura-Whitfield (Principal UX Designer)
**Issue:** #538
**Date:** 2026-03-29
**Status:** Draft

---

## 1. Design Intent

The narrator detail page is the comprehensive profile for an individual narrator. It must serve both quick-reference lookups (who was this person, are they reliable?) and deep scholarly analysis (network position, transmission patterns, cross-collection presence). The page is organized as a vertical scroll with distinct sections, each self-contained.

Arabic names are always primary — displayed larger and first — with English transliterations secondary. This respects the source language of the tradition while maintaining accessibility for non-Arabic readers.

---

## 2. Page Layout

### 2.1 Desktop (>=1280px)

```
+-----------------------------------------------------------------------+
| HEADER: Isnad Graph > Narrators > Abu Hurayra         [user avatar]   |
+-------+---------------------------------------------------------------+
| NAV   | PROFILE CARD                                                  |
| SIDE  +---------------------------------------------------------------+
| BAR   | +---------------------+  +----------------------------------+ |
| (220) | | BIOGRAPHY           |  | NETWORK PREVIEW                | |
|       | | (flex: 1)           |  | (400px, ego-graph)             | |
|       | |                     |  |                                | |
|       | |                     |  |        ●───●                   | |
|       | |                     |  |       / \   \                  | |
|       | |                     |  |      ●  [★]  ●                | |
|       | |                     |  |       \ /   /                  | |
|       | |                     |  |        ●───●                   | |
|       | |                     |  |                                | |
|       | |                     |  | [Open in Graph Explorer →]    | |
|       | +---------------------+  +----------------------------------+ |
|       +---------------------------------------------------------------+
|       | RELIABILITY RATINGS                                           |
|       +---------------------------------------------------------------+
|       | HADITH LIST                                                    |
|       +---------------------------------------------------------------+
|       | CHAIN VISUALIZATION                                           |
|       +---------------------------------------------------------------+
```

### 2.2 Tablet (768px–1279px)

```
+-----------------------------------------------------------------------+
| HEADER: Isnad Graph > Abu Hurayra      [hamburger] [user avatar]      |
+-----------------------------------------------------------------------+
| PROFILE CARD (full width)                                             |
+-----------------------------------------------------------------------+
| NETWORK PREVIEW (full width, 300px height)                            |
+-----------------------------------------------------------------------+
| BIOGRAPHY (full width)                                                |
+-----------------------------------------------------------------------+
| RELIABILITY RATINGS                                                   |
+-----------------------------------------------------------------------+
| HADITH LIST                                                           |
+-----------------------------------------------------------------------+
| CHAIN VISUALIZATION                                                   |
+-----------------------------------------------------------------------+
```

- Biography and network preview stack vertically
- All sections full-width

### 2.3 Mobile (<768px)

```
+-----------------------------------+
| HEADER          [ham] [avatar]    |
+-----------------------------------+
| PROFILE CARD (compact)            |
| ابو هريرة الدوسي                   |
| Abu Hurayra al-Dawsi              |
| Sahabi | d. 59 AH | Thiqah       |
+-----------------------------------+
| [Tab: Bio] [Network] [Hadith]    |
+-----------------------------------+
| (tab content, full width)         |
|                                   |
|                                   |
+-----------------------------------+
```

- Sections reorganized into tab navigation to reduce scroll depth
- Network preview is a simplified static image with "Open in Graph Explorer" link

---

## 3. Profile Card

```
+-----------------------------------------------------------------------+
|                                                                       |
|  ابو هريرة الدوسي                                                      |  <- dir="rtl", 28px
|  Abu Hurayra al-Dawsi                                                 |  <- 20px
|                                                                       |
|  +-------------------+-------------------+-------------------+        |
|  | Full name         | عبد الرحمن بن صخر الدوسي                |        |
|  | Kunya             | Abu Hurayra (ابو هريرة)                |        |
|  | Nisba             | al-Dawsi (الدوسي)                      |        |
|  | Laqab             | —                                     |        |
|  +-------------------+-------------------+-------------------+        |
|  | Generation        | Sahabi (Companion)                    |        |
|  | Birth             | Unknown                               |        |
|  | Death             | 59 AH (678 CE)                        |        |
|  | Location          | Medina                                |        |
|  | Sect              | Sunni                                 |        |
|  +-------------------+-------------------+-------------------+        |
|                                                                       |
+-----------------------------------------------------------------------+
```

- Arabic name rendered first, largest, RTL
- Metadata in a definition-list layout (term: value pairs)
- Dual dating (AH / CE) where both are known
- Missing values displayed as em dash, not hidden — absence of data is itself informative

---

## 4. Biography Section

```
+-----------------------------------------------------------------------+
| BIOGRAPHY                                                             |
+-----------------------------------------------------------------------+
|                                                                       |
| Abu Hurayra was a companion of the Prophet Muhammad and one of the    |
| most prolific narrators of hadith. He accepted Islam in the 7th year  |
| of Hijra and remained in close company with the Prophet until the     |
| latter's death. He is credited with narrating over 5,000 hadith,     |
| more than any other companion.                                        |
|                                                                       |
| He served as governor of Bahrain under the caliphate of Umar ibn     |
| al-Khattab and later settled in Medina, where he taught numerous     |
| students.                                                             |
|                                                                       |
| [Show more ▼] (if text exceeds 200 words)                            |
|                                                                       |
+-----------------------------------------------------------------------+
```

- Biography text sourced from curated database field
- Collapsed to ~200 words by default with "Show more" toggle
- If no biography available: "No biographical information available for this narrator."

---

## 5. Reliability Ratings

```
+-----------------------------------------------------------------------+
| RELIABILITY RATINGS                                                    |
+-----------------------------------------------------------------------+
|                                                                       |
| AGGREGATE: Thiqah (Trustworthy)     ████████████████████░  4.8/5.0   |
|                                                                       |
| +---------------------+-------------+-----------------------------+  |
| | Scholar             | Rating      | Notes                       |  |
| +---------------------+-------------+-----------------------------+  |
| | Ibn Hajar           | Thiqah      | "Sahabi, no criticism req." |  |
| | al-Dhahabi          | Thiqah      | "Most prolific narrator"    |  |
| | Ibn Hibban          | Thiqah      | —                           |  |
| | al-'Ijli            | Thiqah      | —                           |  |
| | Abu Hatim           | Thiqah      | "His hadith are accepted"   |  |
| +---------------------+-------------+-----------------------------+  |
|                                                                       |
| Rating scale: Thiqah > Saduq > Maqbul > Da'if > Matruk > Kadhdhab   |
|                                                                       |
+-----------------------------------------------------------------------+
```

- Aggregate rating shown as a horizontal bar with numeric score
- Individual scholar ratings in a table
- Rating scale legend shown below table for reference
- Bar color: green (Thiqah/Saduq), amber (Maqbul), red (Da'if and below) — with text label always visible, never color-only

---

## 6. Network Preview

### 6.1 Ego-Graph

```
+----------------------------------+
|                                  |
|          ●  ●                    |
|         / \ |                    |
|        ●  [★]  ●                 |  <- ★ = selected narrator
|         \ / \ /                  |
|          ●   ●                   |
|          |                       |
|          ●                       |
|                                  |
| Teachers: 12 | Students: 342    |
| [Open in Graph Explorer →]      |
+----------------------------------+
```

- Depth-1 ego-graph rendered with the same force-directed engine as Graph Explorer
- Selected narrator centered and visually distinguished (star/accent ring)
- Nodes colored by community (same palette as Graph Explorer)
- Interactive: hover shows tooltip, click navigates to that narrator's detail page
- "Open in Graph Explorer" navigates to Graph Explorer with this narrator pre-selected

### 6.2 Network Statistics

```
+----------------------------------+
| NETWORK STATISTICS               |
+----------------------------------+
| Teachers (in-degree):        12  |
| Students (out-degree):      342  |
| Total connections:          354  |
| Betweenness centrality:  0.087  |
| PageRank:                0.0042  |
| Community:          7 (● Blue)   |
| Closeness centrality:    0.034  |
+----------------------------------+
```

- Displayed below the ego-graph
- Tooltips on each metric name explaining what it measures
- Community shown with color swatch matching the graph palette

---

## 7. Hadith List

```
+-----------------------------------------------------------------------+
| HADITH NARRATED (5,374 total)                  [Filter by collection v]|
+-----------------------------------------------------------------------+
|                                                                       |
| +-------------------------------------------------------------------+ |
| | Bukhari 1 — كتاب بدء الوحي                                         | |
| | إنما الأعمال بالنيات...                                              | |
| | "Actions are judged by intentions..."                              | |
| | Grade: Sahih  |  Chain: 7 narrators  |  Topics: Worship           | |
| +-------------------------------------------------------------------+ |
|                                                                       |
| +-------------------------------------------------------------------+ |
| | Muslim 23 — كتاب الإيمان                                           | |
| | الدين النصيحة...                                                    | |
| | "The religion is sincerity..."                                     | |
| | Grade: Sahih  |  Chain: 5 narrators  |  Topics: Ethics            | |
| +-------------------------------------------------------------------+ |
|                                                                       |
| +-------------------------------------------------------------------+ |
| | Abu Dawud 4 — كتاب الصلاة                                          | |
| | ...                                                                | |
| +-------------------------------------------------------------------+ |
|                                                                       |
| Showing 1-10 of 5,374          [1] [2] [3] ... [538] [Next →]        |
+-----------------------------------------------------------------------+
```

- Each hadith shows: collection + number, book name (Arabic), matn preview (Arabic + English), grade, chain length, topics
- Arabic text in RTL blocks
- Collection filter dropdown to narrow by source
- Paginated (10 per page)
- Click navigates to hadith detail page

---

## 8. Chain Visualization

```
+-----------------------------------------------------------------------+
| CHAIN VISUALIZATION                              [Select a chain v]   |
+-----------------------------------------------------------------------+
|                                                                       |
|  Chain for Bukhari 1:                                                 |
|                                                                       |
|  Prophet Muhammad                                                     |
|       │                                                               |
|       ▼                                                               |
|  Umar ibn al-Khattab  ─── Sahabi, Thiqah                             |
|       │                                                               |
|       ▼                                                               |
|  Alqama ibn Waqqas  ─── Tabi'i, Thiqah                               |
|       │                                                               |
|       ▼                                                               |
|  Muhammad ibn Ibrahim  ─── Tabi' al-Tabi'in, Thiqah                  |
|       │                                                               |
|       ▼                                                               |
|  Yahya ibn Sa'id  ─── Tabi' al-Tabi'in, Thiqah                       |
|       │                                                               |
|       ▼                                                               |
| [★ Abu Hurayra]  ─── Sahabi, Thiqah                                  |
|       │                                                               |
|       ▼                                                               |
|  al-Bukhari  ─── Compiler                                            |
|                                                                       |
+-----------------------------------------------------------------------+
```

- Linear top-to-bottom chain rendering
- Each narrator node is clickable (navigates to their detail page)
- Current narrator highlighted with accent styling
- Chain selector dropdown to switch between different chains involving this narrator
- Generation and reliability shown inline with each narrator
- On mobile: horizontal scroll if chain is very long

---

## 9. RTL and Bidirectional Text

### 9.1 Name Display

- Arabic name always displayed first (top), larger font, `dir="rtl"` and `lang="ar"`
- English transliteration below, standard LTR
- In the profile card, name variants (kunya, nisba, laqab) show both scripts side by side using bidi isolation: `English (عربي)`

### 9.2 Hadith Text

- Matn text always rendered in a `dir="rtl"` block with Arabic font stack
- Translation follows in a separate `dir="ltr"` block
- Book/chapter names displayed in Arabic with `dir="rtl"`

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
| Tab | Move through sections: profile > biography > ratings > network > hadith list > chains |
| Enter | Expand collapsed sections, activate links, select chain |
| Arrow keys | Navigate table rows in ratings, hadith list |
| Escape | Close dropdowns |

### 10.2 Screen Reader Support

- Page title: `<title>Abu Hurayra — Narrator Detail — Isnad Graph</title>`
- Profile card: `aria-label="Narrator profile: Abu Hurayra al-Dawsi"` with Arabic name announced via `lang="ar"` attribute
- Reliability aggregate: "Trustworthiness rating: 4.8 out of 5, Thiqah (Trustworthy)"
- Network preview: `aria-label="Transmission network preview showing 12 teachers and 342 students"`
- Ego-graph has a "View as table" alternative listing teachers and students
- Chain visualization: ordered list (`<ol>`) with `aria-label="Isnad chain for Bukhari hadith 1"`

### 10.3 High Contrast Mode

- Profile card border becomes 2px solid black
- Rating bar uses pattern fill in addition to color
- Chain connector lines become 2px solid black
- Network graph nodes gain 2px black outlines

### 10.4 Reduced Motion

- Ego-graph force simulation completes instantly
- Section expand/collapse is instant (no slide animation)

---

## 11. Responsive Breakpoint Summary

| Feature | Desktop (>=1280) | Tablet (768-1279) | Mobile (<768) |
|---------|:---:|:---:|:---:|
| Nav sidebar | Visible (220px) | Hamburger overlay | Hamburger overlay |
| Profile card | Full width | Full width | Compact |
| Bio + Network | Side by side | Stacked | Tab view |
| Reliability table | Full table | Full table | Card layout |
| Hadith list | Full cards | Full cards | Condensed cards |
| Chain visualization | Full vertical | Full vertical | Horizontal scroll |
| Network preview | Interactive graph | Interactive graph | Static image + link |

---

## 12. Component Mapping

| Wireframe element | Component | Notes |
|-------------------|-----------|-------|
| Page shell | `NarratorDetailPage.tsx` | New page, route: `/narrators/:id` |
| Profile card | `NarratorProfileCard` | Reusable across search results and detail |
| Biography | `NarratorBiography` | Collapsible text block |
| Reliability ratings | `ReliabilityRatings` | Table + aggregate bar |
| Network preview | `EgoGraph` | Shares rendering engine with Graph Explorer |
| Network stats | `NetworkStatistics` | Metric list with tooltips |
| Hadith list | `NarratorHadithList` | Paginated, filterable |
| Chain visualization | `ChainVisualization` | Linear chain renderer, reused on hadith detail |

---

## 13. Design Tokens

```css
/* Profile card */
--profile-name-ar-size: 28px;
--profile-name-en-size: 20px;
--profile-meta-size: 14px;

/* Reliability bar */
--rating-bar-height: 8px;
--rating-bar-bg: #e8e8e8;
--rating-bar-fill-high: oklch(60% 0.15 150);   /* green */
--rating-bar-fill-mid: oklch(70% 0.15 60);     /* amber */
--rating-bar-fill-low: oklch(55% 0.15 25);     /* red */

/* Chain visualization */
--chain-connector-width: 2px;
--chain-connector-color: #cccccc;
--chain-node-size: 12px;
--chain-node-active: var(--color-accent, #1a73e8);

/* Ego graph */
--ego-graph-height: 350px;
--ego-graph-bg: #fafafa;
```

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-29 | Sable Nakamura-Whitfield | Initial wireframe specification |
