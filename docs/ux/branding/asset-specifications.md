# Isnad Graph — Asset Specifications

Detailed specifications for all visual assets. Each section describes the design intent, format requirements, and how the asset maps to the three brand proposals. Assets are delivered as descriptions and SVG source where possible; raster renders are generated from SVG masters.

---

## 1. Favicons

### Format Requirements

| Size | Format | Use |
|------|--------|-----|
| Any | SVG | Modern browsers, `<link rel="icon" type="image/svg+xml">` |
| 16x16 | PNG | Legacy fallback |
| 32x32 | PNG | Browser tabs, bookmarks |
| 180x180 | PNG | Apple Touch Icon |
| 192x192 | PNG | Android home screen |
| 512x512 | PNG | PWA splash screen, app stores |

All PNGs generated from the SVG master. Transparent background for PNG; SVG uses `currentColor` for automatic dark mode adaptation where supported.

### Design per Proposal

**Proposal A (Qalam):** The octagonal frame containing the 3-node directed graph. At 16x16, the octagon simplifies to a rounded square; the graph reduces to 3 dots and 2 lines. Colors: sienna nodes on parchment background, with a thin ink-colored octagonal border.

**Proposal B (Silsila):** The 5-node branching graph, no container. At 16x16, reduces to 3 nodes and 2 edges (the minimum readable graph). Colors: indigo-600 nodes on transparent background. Clean, recognizable at any size.

**Proposal C (Riwaya):** The 8-pointed star with graph intersections as nodes. At 16x16, the star simplifies to its outer silhouette with 3 visible interior nodes. Colors: teal-700 star outline and nodes on transparent background. The rounded square container appears only at 192x192+.

### SVG Master (Proposal C)

```
frontend/public/favicon.svg
```

The SVG uses `<symbol>` for reuse and `viewBox="0 0 32 32"` as the canonical coordinate space. Strokes use `stroke-width="2"` at 32x32 (scales proportionally). Node circles use `r="2.5"` at 32x32.

---

## 2. Open Graph Images

### Format Requirements

| Dimension | Format | Use |
|-----------|--------|-----|
| 1200x630 | PNG | `og:image`, Twitter card, Slack/Discord unfurl |

### Template Design

The OG image uses a structured layout rather than a single illustration:

- **Left 60%:** The platform name "isnad graph" set large in the brand typeface (Amiri + Source Sans 3 for Riwaya) against the background color. Below the name, a single-line descriptor: "Computational Hadith Analysis Platform." The text is vertically centered with generous padding.
- **Right 40%:** A simplified, decorative version of the brand icon (the 8-pointed star/graph for Riwaya) rendered at low opacity (15-20%) as a background element. This prevents the icon from competing with text when the image is displayed at small sizes in social feeds.
- **Bottom strip:** A 4px-high bar in `--color-primary` spanning the full width, grounding the composition.
- **Background:** `--color-background` (the warm white for Riwaya light mode).

The template is designed so that variant OG images (for specific pages like "Narrator: Al-Bukhari") can replace the descriptor line with contextual text without redesigning the layout.

### File Location

```
frontend/public/og-image.png
frontend/public/og-image-dark.png
```

A dark-mode variant uses `--color-background` dark values. Social platforms select based on context where supported.

---

## 3. Loading State Animations

### Principles

- **prefers-reduced-motion first:** All animations have a static fallback. When reduced motion is preferred, show a static skeleton screen with no animation.
- **Purpose-driven:** Animation communicates "data is loading" — it is not decorative.
- **Brand-consistent:** Uses brand colors and motifs.

### Skeleton Screens

The primary loading pattern is skeleton screens — placeholder shapes that mirror the layout of the content being loaded. This follows the principle that the best loading state is one that looks like the content it replaces.

**Skeleton token colors:**
- Light mode: `oklch(0.90 0.005 60)` base, `oklch(0.85 0.005 60)` shimmer highlight
- Dark mode: `oklch(0.25 0.005 60)` base, `oklch(0.30 0.005 60)` shimmer highlight

**Shimmer animation:** A subtle left-to-right gradient sweep at `var(--duration-slower)` (500ms), using `linear-gradient` and `translateX`. The gradient is barely perceptible — the goal is to distinguish "loading" from "empty" without drawing attention.

**Skeleton variants needed:**
1. **Graph skeleton:** A container with 5-7 faint circular nodes and connecting lines, suggesting the graph layout
2. **List skeleton:** 4-6 rows of varying-width rectangles (simulating text lines with hadith content)
3. **Card skeleton:** A rounded rectangle with a header bar, 3 text lines, and a badge-width rectangle
4. **Detail skeleton:** A two-column layout with a narrow left column (metadata) and wide right column (content)

### Graph-Specific Loading

When the force-directed graph visualization is loading, the skeleton shows a static arrangement of nodes and edges in the skeleton color. Once data arrives, nodes fade in at their computed positions over `var(--duration-slow)`.

### CSS Implementation

```css
/* In a utilities or components layer */
@layer components {
  .skeleton {
    background: oklch(0.90 0.005 60);
    border-radius: var(--radius-md);
    animation: skeleton-shimmer var(--duration-slower) ease-in-out infinite;
  }

  @keyframes skeleton-shimmer {
    0% { opacity: 1; }
    50% { opacity: 0.6; }
    100% { opacity: 1; }
  }

  @media (prefers-reduced-motion: reduce) {
    .skeleton { animation: none; }
  }

  @media (prefers-color-scheme: dark) {
    .skeleton { background: oklch(0.25 0.005 60); }
  }
}
```

---

## 4. Empty State Illustrations

### Principles

- **Informative, not cute:** Empty states explain what should be here and how to get it. No cartoon mascots, no "sad robots."
- **Minimal ink:** Each illustration is a single-color line drawing using `--color-muted-foreground` at reduced opacity. Small enough to not dominate the viewport.
- **Actionable:** Each empty state includes a suggested action (text, not part of the illustration).

### Empty State Variants

#### 4a. No Search Results

**Visual:** A magnifying glass icon with a small "x" or empty circle where results would appear. Below the magnifying glass, three short dashed lines (suggesting absent result rows) that fade out from top to bottom.

**Text pattern:**
- Heading: "No results found"
- Body: "Try adjusting your search terms or filters."

**Size:** 120x120px illustration area, centered above text.

#### 4b. Empty Graph View

**Visual:** A single node (circle) at center with 3-4 faint, dashed edge lines radiating outward, ending in small open circles (suggesting unloaded/missing connected nodes). The composition references the brand icon but in an incomplete state.

**Text pattern:**
- Heading: "No graph data"
- Body: "Search for a narrator or hadith to explore the transmission network."

**Size:** 160x160px illustration area.

#### 4c. No Data Loaded

**Visual:** A simplified database/cylinder icon with an upward-pointing arrow, suggesting "import." The cylinder is drawn with dashed lines to indicate emptiness.

**Text pattern:**
- Heading: "No data loaded"
- Body: "Run the ingestion pipeline to populate the database."

**Size:** 120x120px illustration area.

#### 4d. Error: 404 Not Found

**Visual:** The brand icon (8-pointed star graph) with one node disconnected — its edge line broken with a visible gap. The disconnected node drifts slightly outside the star pattern.

**Text pattern:**
- Heading: "Page not found"
- Body: "The page you are looking for does not exist or has been moved."

**Size:** 140x140px illustration area.

#### 4e. Error: 500 Server Error

**Visual:** The brand icon with all edge lines rendered as jagged/broken segments (like a fractured pattern). Nodes remain intact but connections are disrupted.

**Text pattern:**
- Heading: "Something went wrong"
- Body: "An unexpected error occurred. Please try again."

**Size:** 140x140px illustration area.

#### 4f. Offline / Network Error

**Visual:** Two nodes with a single edge line between them. The edge line is interrupted by a small "break" icon (two opposing angle brackets like `><`). Communicates disconnection without being dramatic.

**Text pattern:**
- Heading: "Connection lost"
- Body: "Check your network connection and try again."

**Size:** 120x120px illustration area.

### Implementation Notes

All empty state illustrations are inline SVG components in React, not external image files. This allows:
- Dynamic theming via `currentColor` and CSS custom properties
- No additional HTTP requests
- Accessibility via `role="img"` and `aria-label`

---

## 5. Placeholder Avatar (Unknown Narrator)

**Visual:** A circle containing a simplified silhouette — not a generic "person" icon, but a figure holding a scroll or book (referencing the narrator's role as transmitter of hadith). The silhouette is rendered in `--color-muted-foreground` against `--color-muted`.

**Sizes:** 32x32, 48x48, 96x96 (for list items, cards, and detail views respectively).

**Format:** SVG with `viewBox="0 0 48 48"`, scales to all sizes.

**File location:**
```
frontend/public/avatar-placeholder.svg
```

---

## 6. File Manifest

```
frontend/public/
  favicon.svg              — SVG master favicon
  favicon-16x16.png        — Generated from SVG
  favicon-32x32.png        — Generated from SVG
  apple-touch-icon.png     — 180x180, generated from SVG
  icon-192x192.png         — Android/PWA icon
  icon-512x512.png         — PWA splash
  og-image.png             — 1200x630 Open Graph image (light)
  og-image-dark.png        — 1200x630 Open Graph image (dark)
  avatar-placeholder.svg   — Unknown narrator placeholder

docs/ux/branding/
  brand-proposals.md        — 3 brand direction proposals (#545)
  asset-specifications.md   — This document (#547)
```

Note: Empty state illustrations and skeleton components are implemented as React components, not standalone files, as described in section 4.
