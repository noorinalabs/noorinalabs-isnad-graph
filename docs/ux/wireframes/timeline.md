# Timeline — Wireframe Specification

**Author:** Sable Nakamura-Whitfield (Principal UX Designer)
**Issue:** #540
**Date:** 2026-03-29
**Status:** Draft

---

## 1. Design Intent

The timeline view provides a chronological lens on hadith transmission. Narrators appear as horizontal lifespan bars, transmission events as connections between them, and historical events as contextual markers. This is a Tufte-style small-multiples timeline: dense with data, rewarding close reading, with zoom levels that support both macro patterns (centuries of transmission) and micro analysis (individual lifespans and overlaps).

The primary scholarly question this view answers: "When did narrators live, who could plausibly have met whom, and how does the transmission network unfold across time?"

---

## 2. Page Layout

### 2.1 Desktop (>=1280px)

```
+-----------------------------------------------------------------------+
| HEADER: Isnad Graph > Timeline                       [user avatar]    |
+-------+---------------------------------------------------------------+
| NAV   | TOOLBAR                                                       |
| SIDE  | [Search narrator...] [Zoom: Century|Decade|Year]              |
| BAR   | [Era filter v] [School filter v]         [Reset] [Export v]   |
| (220) +---------------------------------------------------------------+
|       |              TIMELINE CANVAS                                  |
|       |                                                               |
|       |  1 AH         50 AH        100 AH       150 AH       200 AH  |
|       |  |────────────|────────────|────────────|────────────|         |
|       |                                                               |
|       |  ████████████████  Prophet Muhammad (d. 11 AH)                |
|       |     ████████████████████████████  Abu Hurayra (d. 59 AH)      |
|       |        ████████████████████████████████  Ibn Abbas (d. 68 AH) |
|       |              ──→──→──→  (transmission links)                  |
|       |                    ████████████████████████  al-Zuhri (d.124) |
|       |                          ████████████████████  Malik (d.179)  |
|       |                                                               |
|       |  ◆ Battle of Badr (2 AH)                                     |
|       |         ◆ Conquest of Mecca (8 AH)                            |
|       |                    ◆ Fall of Umayyads (132 AH)                |
|       |                                                               |
|       +---------------------------------------------------------------+
|       | STATUS: 47 narrators, 3 events | Range: 1-250 AH | Zoom: Dec.|
|       +---------------------------------------------------------------+
```

### 2.2 Tablet (768px–1279px)

```
+-----------------------------------------------------------------------+
| HEADER                                 [hamburger] [user avatar]      |
+-----------------------------------------------------------------------+
| TOOLBAR (two rows)                                                    |
| [Search...] [Zoom: Century|Decade|Year]                               |
| [Era filter v] [School filter v]              [Reset]                 |
+-----------------------------------------------------------------------+
|                    TIMELINE CANVAS (full width)                        |
|                    (horizontal scroll enabled)                         |
+-----------------------------------------------------------------------+
| STATUS BAR                                                            |
+-----------------------------------------------------------------------+
```

- Horizontal scroll for timeline when zoomed to decade/year level
- Touch: pinch-to-zoom, two-finger pan

### 2.3 Mobile (<768px)

```
+-----------------------------------+
| HEADER          [ham] [avatar]    |
+-----------------------------------+
| [Search...] [Zoom] [Filters]     |
+-----------------------------------+
|                                   |
|   TIMELINE CANVAS                 |
|   (vertical orientation,          |
|    time flows top-to-bottom)      |
|                                   |
|   ── 1 AH ──                     |
|   ████ Prophet Muhammad           |
|   ████████ Abu Hurayra            |
|   ── 50 AH ──                    |
|   ...                             |
|                                   |
+-----------------------------------+
| 47 narrators           [+] [-]   |
+-----------------------------------+
```

- Timeline rotates to vertical orientation (time flows top-to-bottom)
- Narrators as horizontal bars extending right from the time axis
- Single-finger vertical scroll, pinch-to-zoom

---

## 3. Toolbar Controls

### 3.1 Search

```
+----------------------------------------------+
| [magnifier] Search narrator to highlight...  |
+----------------------------------------------+
```

- Typeahead search (same pattern as Graph Explorer)
- Selecting a narrator scrolls the timeline to center on their lifespan bar and highlights it
- Does not filter — other narrators remain visible but the matched narrator pulses briefly then retains accent styling

### 3.2 Zoom Level

```
  Zoom: [ Century | Decade | Year ]
```

- **Century**: Each division = 100 years AH. Macro view. Shows all major narrator generations as layered bars. Best for overview of transmission eras.
- **Decade**: Each division = 10 years AH. Shows individual narrator lifespans with readable labels. Best for analyzing contemporaries and plausible transmission windows.
- **Year**: Each division = 1 year AH. Shows exact birth/death dates, event markers, fine-grained overlap analysis.
- Segmented button group, all options visible
- Zooming re-renders the axis; narrator bars scale proportionally
- Mouse wheel zoom supported (continuous, snapping to nearest level)

### 3.3 Era Filter

```
  [Era filter v]
  +---------------------------------------+
  | [ ] Pre-Islamic (before 1 AH)        |
  | [x] Prophetic era (1-11 AH)          |
  | [x] Rightly-guided (11-41 AH)        |
  | [x] Umayyad (41-132 AH)             |
  | [x] Early Abbasid (132-247 AH)      |
  | [ ] Later periods (247+ AH)          |
  |                                       |
  | [ Apply ]  [ Clear ]                 |
  +---------------------------------------+
```

- Checkbox group filtering by historical era
- Filters both narrators (by active lifetime) and events

### 3.4 School Filter

```
  [School filter v]
  +---------------------------------------+
  | [x] Medinan                           |
  | [x] Meccan                            |
  | [x] Kufan                             |
  | [x] Basran                            |
  | [ ] Syrian                            |
  | [ ] Egyptian                          |
  |                                       |
  | [ Apply ]  [ Clear ]                 |
  +---------------------------------------+
```

- Filters narrators by scholarly school/geographic tradition
- Useful for studying regional transmission networks

---

## 4. Timeline Canvas

### 4.1 Time Axis

```
  1 AH         50 AH        100 AH       150 AH       200 AH       250 AH
  |────────────|────────────|────────────|────────────|────────────|
```

- Horizontal axis with labeled divisions
- Century gridlines: 1px solid #e0e0e0
- Decade gridlines: 1px dashed #f0f0f0 (visible at decade/year zoom)
- Year gridlines: 1px dotted #f5f5f5 (visible at year zoom only)
- Axis labels centered on divisions

### 4.2 Narrator Lifespan Bars

```
  ████████████████████████████████  Abu Hurayra (d. 59 AH)
  ^                              ^
  birth (unknown, estimated)     death
```

- Horizontal bars representing narrator lifespans
- Bar height: 20px with 4px gap between bars
- Bar color: by generation (same palette as Graph Explorer era overlay)
  - Sahabi: oklch(65% 0.15 250) — blue
  - Tabi'i: oklch(70% 0.15 150) — green
  - Tabi' al-Tabi'in: oklch(65% 0.15 60) — amber
  - Later: oklch(55% 0.15 0) — gray
- Bars sorted vertically by death date (earliest at top)
- Label shows name + death date, positioned to the right of the bar (or inside if bar is wide enough)
- Unknown birth dates: bar starts with a tapered/faded left edge
- Hover: bar darkens, tooltip appears

### 4.3 Narrator Hover Tooltip

```
+----------------------------------+
| Abu Hurayra (ابو هريرة)          |
| Born: unknown | Died: 59 AH      |
| Generation: Sahabi               |
| Location: Medina                 |
| 342 transmissions                |
| [View narrator detail →]        |
+----------------------------------+
```

### 4.4 Transmission Links

```
  ████████████████  Narrator A
                ──→
  ████████████████████  Narrator B
```

- Shown when a narrator is selected (clicked)
- Lines connect the selected narrator's bar to their teachers (upward) and students (downward)
- Arrow direction indicates transmission flow (teacher → student)
- Line opacity: 0.6 for general links, 1.0 for selected chain
- Line color: accent color (#1a73e8) for direct links
- Only shown for the selected narrator to avoid visual chaos

### 4.5 Historical Event Markers

```
  ◆ Battle of Badr (2 AH)
  ◆ Conquest of Mecca (8 AH)
  ◆ Death of Prophet (11 AH)
  ◆ First Fitna (35 AH)
  ◆ Fall of Umayyads (132 AH)
```

- Diamond markers positioned on the time axis
- Vertical dashed line extends from marker across the full timeline height
- Label below the axis
- Click to see event detail popover:

```
+----------------------------------+
| Battle of Badr (2 AH / 624 CE)  |
| Major military engagement in     |
| early Islamic history. Several   |
| key narrators participated.      |
|                                  |
| Related narrators: 12            |
| [Highlight related narrators]   |
+----------------------------------+
```

- "Highlight related narrators" temporarily colors the bars of narrators associated with the event

### 4.6 Overlap Analysis

When two narrator bars overlap temporally, the overlap region represents the window when transmission could plausibly have occurred. At year zoom level, this overlap is highlighted:

```
  ████████████████████████ Narrator A (d. 80 AH)
                ████████████████████████████ Narrator B (b. 60 AH)
                ████████  <- overlap: 60-80 AH (highlighted region)
```

- Overlap highlight: subtle background stripe (5% opacity of accent color) between the two bars
- Only shown when two narrators are compared (shift-click second narrator)

---

## 5. Event Cards

```
+-----------------------------------------------+
| EVENTS IN VIEW (5)                             |
+-----------------------------------------------+
| ◆ 2 AH   Battle of Badr                       |
| ◆ 8 AH   Conquest of Mecca                    |
| ◆ 11 AH  Death of Prophet Muhammad             |
| ◆ 35 AH  First Fitna begins                   |
| ◆ 61 AH  Battle of Karbala                     |
+-----------------------------------------------+
```

- Collapsible panel listing events currently visible in the viewport
- Clicking an event scrolls the timeline to center on it
- Events sourced from HISTORICAL_EVENT nodes in the graph

---

## 6. RTL and Bidirectional Text

### 6.1 Arabic Names

- Narrator hover tooltip shows Arabic name (RTL) above English name (LTR)
- Event card text uses bidi isolation for mixed-script content
- Timeline bar labels are English-only at default zoom; Arabic names appear in tooltips and detail popovers

### 6.2 Layout Direction

- Timeline canvas and page layout remain LTR (time flows left-to-right, matching scholarly convention)
- Arabic text within tooltips and popovers uses `dir="rtl"` block-level direction
- On mobile vertical orientation, time flows top-to-bottom (not reversed for RTL)

### 6.3 Font Stack

```css
--font-arabic: 'Noto Naskh Arabic', 'Geeza Pro', 'Traditional Arabic', serif;
--font-ui: system-ui, -apple-system, sans-serif;
```

---

## 7. Accessibility

### 7.1 Keyboard Navigation

| Key | Action |
|-----|--------|
| Tab | Move through: search > zoom toggle > filters > timeline canvas > event list |
| Arrow left/right | In canvas: pan timeline by one division |
| Arrow up/down | In canvas: move focus between narrator bars |
| Enter | Select focused narrator bar (shows transmission links) |
| + / - | Zoom in / out |
| Escape | Deselect narrator, close popovers |
| / | Focus search input |

### 7.2 Screen Reader Support

- Timeline canvas: `role="application"` with `aria-label="Chronological timeline of hadith narrators"`
- On narrator bar focus: "{name}, {generation}, born {birth} AH, died {death} AH, {transmissions} transmissions"
- On event marker focus: "{event name}, {year} AH"
- Timeline has a "View as table" alternative:

**Narrators table:**
| Name | Generation | Birth (AH) | Death (AH) | Location | Transmissions |

**Events table:**
| Event | Year (AH) | Year (CE) | Related Narrators |

### 7.3 High Contrast Mode

- Narrator bars gain 2px black outlines
- Generation colors are supplemented with pattern fills (hatching for Sahabi, dots for Tabi'i, stripes for later)
- Event markers become 2px solid black diamonds
- Gridlines become more visible (darker)

### 7.4 Reduced Motion

- Zoom level transitions are instant (no animated axis rescaling)
- Narrator bar hover effects are instant
- Scroll-to-narrator on search is instant (no smooth scroll)

---

## 8. Responsive Breakpoint Summary

| Feature | Desktop (>=1280) | Tablet (768-1279) | Mobile (<768) |
|---------|:---:|:---:|:---:|
| Nav sidebar | Visible (220px) | Hamburger overlay | Hamburger overlay |
| Timeline orientation | Horizontal | Horizontal (scroll) | Vertical |
| Zoom control | Segmented buttons | Segmented buttons | Dropdown |
| Filters | Dropdown panels | Modal | Full-screen modal |
| Narrator labels | Inline on bars | Inline on bars | Tooltip only |
| Event markers | Inline + list | Inline + list | List only |
| Overlap analysis | Shift-click | Long-press | Not available |
| Transmission links | On click | On click | On tap |
| Touch gestures | n/a | Pinch/pan | Pinch/pan/scroll |
| Export | PNG/SVG/CSV | PNG/CSV | PNG only |

---

## 9. Component Mapping

| Wireframe element | Component | Notes |
|-------------------|-----------|-------|
| Page shell | `TimelinePage.tsx` | New page, route: `/timeline` |
| Timeline canvas | `TimelineCanvas` | HTML5 Canvas or SVG, custom renderer |
| Time axis | `TimeAxis` | Responsive divisions based on zoom level |
| Narrator bar | `NarratorBar` | Horizontal lifespan bar, interactive |
| Event marker | `EventMarker` | Diamond glyph + vertical line |
| Narrator tooltip | `NarratorTooltip` | Shared with Graph Explorer tooltip |
| Event popover | `EventPopover` | Detail card for historical events |
| Zoom control | `ZoomControl` | Segmented button group |
| Filter panels | `TimelineFilters` | Era + school checkbox groups |
| Table alternative | `TimelineTableView` | Accessible alternative rendering |

---

## 10. Design Tokens

```css
/* Timeline canvas */
--timeline-bg: #fafafa;
--timeline-axis-color: #333333;
--timeline-grid-century: #e0e0e0;
--timeline-grid-decade: #f0f0f0;

/* Narrator bars */
--bar-height: 20px;
--bar-gap: 4px;
--bar-radius: 3px;
--bar-sahabi: oklch(65% 0.15 250);
--bar-tabii: oklch(70% 0.15 150);
--bar-tabi-tabiin: oklch(65% 0.15 60);
--bar-later: oklch(55% 0.15 0);

/* Event markers */
--event-marker-size: 10px;
--event-marker-color: #d32f2f;
--event-line-color: #d32f2f;
--event-line-opacity: 0.3;

/* Overlap highlight */
--overlap-bg: rgba(26, 115, 232, 0.05);
```

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-29 | Sable Nakamura-Whitfield | Initial wireframe specification |
