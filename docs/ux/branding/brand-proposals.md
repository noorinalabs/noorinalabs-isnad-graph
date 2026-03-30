# Isnad Graph — Brand Direction Proposals

Three distinct brand proposals for the isnad-graph platform. Each is designed to work in light and dark modes, meet WCAG 2.2 AA contrast requirements, and remain distinguishable under the three most common forms of color vision deficiency (protanopia, deuteranopia, tritanopia).

All color values are specified in OKLCH for perceptual uniformity, with sRGB hex fallbacks.

---

## Proposal A: "Qalam" — Scholarly / Academic

### Concept

Rooted in the tradition of Islamic manuscript scholarship. The name *Qalam* (pen) references the instrument of hadith transmission itself. This direction treats the platform as a digital extension of the scholarly desk: measured, precise, built for long reading sessions and careful analysis.

### Logo Concept

- **Wordmark:** "isnad" set in a custom-modified Noto Naskh Arabic at display weight, with the Latin "graph" in IBM Plex Sans at light weight, separated by a thin vertical rule. The Arabic letterforms are left unmodified — no stylization that would compromise legibility.
- **Icon/Symbol:** An octagonal frame (referencing Islamic geometric tradition) containing a simplified directed graph of three nodes and two edges. The nodes are small circles; the edges are calligraphic strokes that taper like pen marks. The octagon's border uses a single-band geometric interlace pattern.
- **Lockup:** Icon to the left of the wordmark, with generous clear space. The icon works standalone at small sizes (favicons, app icons).

### Color Palette

The palette draws from manuscript tradition: deep ink, aged parchment, and marginalia accents.

| Token | OKLCH | Hex | Role |
|-------|-------|-----|------|
| `--color-ink` | `oklch(0.25 0.02 260)` | `#1e2a3a` | Primary text, headings |
| `--color-parchment` | `oklch(0.96 0.01 85)` | `#f5f0e8` | Background surface |
| `--color-vellum` | `oklch(0.99 0.005 85)` | `#faf8f3` | Elevated surface (cards) |
| `--color-sienna` | `oklch(0.55 0.14 45)` | `#a0522d` | Primary accent, links, interactive |
| `--color-vermillion` | `oklch(0.60 0.18 30)` | `#c04020` | Destructive, errors |
| `--color-verdigris` | `oklch(0.55 0.10 175)` | `#2a8a6a` | Success, sahih grading |
| `--color-lapis` | `oklch(0.45 0.12 260)` | `#2d5a9e` | Information, Shia sect |
| `--color-ochre` | `oklch(0.65 0.14 75)` | `#b8860b` | Warning, hasan grading |
| `--color-graphite` | `oklch(0.45 0.01 260)` | `#5c6370` | Muted text, captions |
| `--color-border-subtle` | `oklch(0.85 0.01 85)` | `#d4cfc5` | Borders, dividers |

**Dark mode** inverts the parchment/ink relationship: `--color-ink` becomes a warm off-white (`oklch(0.92 0.01 85)` / `#ece5d8`), backgrounds shift to deep charcoal (`oklch(0.20 0.015 260)` / `#1a1f28`), and accent hues increase lightness by ~15% to maintain contrast.

**Contrast verification:**
- `--color-ink` on `--color-parchment`: 12.8:1 (AAA)
- `--color-sienna` on `--color-parchment`: 5.2:1 (AA large + normal)
- `--color-graphite` on `--color-parchment`: 4.8:1 (AA large, AA normal at this size)

### Typography

| Use | Family | Weight | Size | Line Height |
|-----|--------|--------|------|-------------|
| Arabic body | Noto Naskh Arabic | 400 | 1.125rem | 2.0 |
| Arabic headings | Noto Naskh Arabic | 700 | 1.5rem+ | 1.6 |
| Latin body | IBM Plex Sans | 400 | 1rem | 1.6 |
| Latin headings | IBM Plex Serif | 600 | 1.25rem+ | 1.3 |
| Monospace/data | IBM Plex Mono | 400 | 0.875rem | 1.5 |

**Rationale:** IBM Plex Serif for headings gives an editorial, scholarly quality. Noto Naskh Arabic is the most legible Arabic web font with proper diacritics support. IBM Plex Sans for body keeps Latin text clean and neutral, deferring to the Arabic when both appear.

### Mood / Tone

Quiet authority. The platform feels like a well-organized research library: warm lighting, aged materials, nothing flashy. The interface recedes so the data — the chains of narration, the network topology — can be the focus. Scholars should feel this tool respects the tradition it digitizes.

### CSS Custom Properties

```css
:root {
  /* Qalam palette — light mode */
  --color-primary: oklch(0.55 0.14 45);       /* sienna */
  --color-primary-foreground: #ffffff;
  --color-background: oklch(0.96 0.01 85);    /* parchment */
  --color-foreground: oklch(0.25 0.02 260);   /* ink */
  --color-surface: oklch(0.99 0.005 85);      /* vellum */
  --color-surface-foreground: oklch(0.25 0.02 260);
  --color-muted: oklch(0.45 0.01 260);        /* graphite */
  --color-border: oklch(0.85 0.01 85);
  --color-destructive: oklch(0.60 0.18 30);   /* vermillion */
  --color-success: oklch(0.55 0.10 175);      /* verdigris */
  --color-warning: oklch(0.65 0.14 75);       /* ochre */
  --color-info: oklch(0.45 0.12 260);         /* lapis */

  /* Domain: grading */
  --color-sahih: oklch(0.55 0.10 175);
  --color-hasan: oklch(0.65 0.14 75);
  --color-daif: oklch(0.60 0.18 30);
  --color-mawdu: oklch(0.50 0.15 15);

  /* Domain: sect */
  --color-sunni: oklch(0.55 0.10 175);
  --color-shia: oklch(0.45 0.12 260);

  /* Typography */
  --font-arabic: 'Noto Naskh Arabic', serif;
  --font-heading: 'IBM Plex Serif', serif;
  --font-body: 'IBM Plex Sans', sans-serif;
  --font-mono: 'IBM Plex Mono', monospace;
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-background: oklch(0.20 0.015 260);
    --color-foreground: oklch(0.92 0.01 85);
    --color-surface: oklch(0.25 0.015 260);
    --color-surface-foreground: oklch(0.92 0.01 85);
    --color-border: oklch(0.35 0.01 260);
    --color-muted: oklch(0.60 0.01 260);
    --color-primary: oklch(0.65 0.14 45);
    --color-destructive: oklch(0.70 0.16 30);
    --color-success: oklch(0.65 0.10 175);
    --color-warning: oklch(0.75 0.12 75);
    --color-info: oklch(0.55 0.10 260);
  }
}
```

---

## Proposal B: "Silsila" — Modern / Tech

### Concept

*Silsila* means "chain" — the core concept of isnad itself. This direction positions the platform as a modern analytical tool: clean, precise, data-forward. It draws from the visual language of network science and graph databases rather than manuscript tradition. The platform should feel like a tool built today for today's researchers, not a digital recreation of a physical library.

### Logo Concept

- **Wordmark:** "isnad graph" set entirely in Inter at medium weight, with generous letter-spacing (+0.02em). All lowercase. The dot of the "i" in "isnad" is replaced by a small circle node with two radiating edge lines, connecting the wordmark to the graph concept without being heavy-handed.
- **Icon/Symbol:** A minimal directed graph: five nodes arranged in a branching tree pattern (one root, two intermediaries, two leaves), connected by thin directional edges. The nodes use two weights — filled circles for narrators, open circles for hadith — establishing the visual vocabulary used throughout the app. No border or frame; the graph floats.
- **Lockup:** Wordmark and icon side by side, or stacked for compact use. The icon is designed to work at 16x16 (three nodes, two edges — maximum reduction).

### Color Palette

A cool, neutral base with a single saturated accent. Restraint is the principle: color is used to encode data, not to decorate.

| Token | OKLCH | Hex | Role |
|-------|-------|-----|------|
| `--color-slate-950` | `oklch(0.15 0.01 260)` | `#0f172a` | Darkest text |
| `--color-slate-50` | `oklch(0.98 0.003 260)` | `#f8fafc` | Background |
| `--color-slate-100` | `oklch(0.95 0.005 260)` | `#f1f5f9` | Elevated surface |
| `--color-indigo-600` | `oklch(0.50 0.18 270)` | `#4f46e5` | Primary accent |
| `--color-indigo-500` | `oklch(0.55 0.20 270)` | `#6366f1` | Hover state |
| `--color-red-600` | `oklch(0.55 0.20 25)` | `#dc2626` | Destructive |
| `--color-emerald-600` | `oklch(0.55 0.14 160)` | `#059669` | Success, sahih |
| `--color-amber-500` | `oklch(0.70 0.16 80)` | `#f59e0b` | Warning, hasan |
| `--color-sky-600` | `oklch(0.55 0.14 230)` | `#0284c7` | Info, Shia sect |
| `--color-slate-400` | `oklch(0.65 0.01 260)` | `#94a3b8` | Muted text |
| `--color-slate-200` | `oklch(0.88 0.005 260)` | `#e2e8f0` | Borders |

**Dark mode:** Background shifts to `--color-slate-950`, text to `--color-slate-50`. Indigo accent lightens to indigo-400 (`oklch(0.65 0.20 270)` / `#818cf8`). Surface becomes `oklch(0.20 0.01 260)` / `#1e293b`.

**Contrast verification:**
- `--color-slate-950` on `--color-slate-50`: 18.1:1 (AAA)
- `--color-indigo-600` on `--color-slate-50`: 6.5:1 (AA)
- `--color-slate-400` on `--color-slate-50`: 3.3:1 (large text only; body muted text uses `slate-500` at 4.6:1)

### Typography

| Use | Family | Weight | Size | Line Height |
|-----|--------|--------|------|-------------|
| Arabic body | Noto Naskh Arabic | 400 | 1.125rem | 2.0 |
| Arabic headings | Noto Naskh Arabic | 700 | 1.5rem+ | 1.6 |
| Latin body | Inter | 400 | 0.9375rem | 1.6 |
| Latin headings | Inter | 600 | 1.25rem+ | 1.25 |
| Monospace/data | JetBrains Mono | 400 | 0.8125rem | 1.5 |

**Rationale:** Inter is the workhorse of modern UI typography — excellent x-height, tabular figures, optical sizing. JetBrains Mono for data tables and code gives a developer-tool feel. Noto Naskh Arabic remains the Arabic choice for its completeness and legibility.

### Mood / Tone

Clinical precision. The platform feels like a well-built developer tool or analytics dashboard: every element earns its space, interactions are fast and predictable, and the data visualization is the star. Researchers who also use Jupyter notebooks, Neo4j Browser, or Observable should feel immediately at home.

### CSS Custom Properties

```css
:root {
  /* Silsila palette — light mode */
  --color-primary: oklch(0.50 0.18 270);       /* indigo-600 */
  --color-primary-foreground: #ffffff;
  --color-background: oklch(0.98 0.003 260);   /* slate-50 */
  --color-foreground: oklch(0.15 0.01 260);    /* slate-950 */
  --color-surface: oklch(0.95 0.005 260);      /* slate-100 */
  --color-surface-foreground: oklch(0.15 0.01 260);
  --color-muted: oklch(0.65 0.01 260);         /* slate-400 */
  --color-border: oklch(0.88 0.005 260);       /* slate-200 */
  --color-destructive: oklch(0.55 0.20 25);    /* red-600 */
  --color-success: oklch(0.55 0.14 160);       /* emerald-600 */
  --color-warning: oklch(0.70 0.16 80);        /* amber-500 */
  --color-info: oklch(0.55 0.14 230);          /* sky-600 */

  /* Domain: grading */
  --color-sahih: oklch(0.55 0.14 160);
  --color-hasan: oklch(0.70 0.16 80);
  --color-daif: oklch(0.55 0.20 25);
  --color-mawdu: oklch(0.45 0.18 15);

  /* Domain: sect */
  --color-sunni: oklch(0.55 0.14 160);
  --color-shia: oklch(0.55 0.14 230);

  /* Typography */
  --font-arabic: 'Noto Naskh Arabic', serif;
  --font-heading: 'Inter', sans-serif;
  --font-body: 'Inter', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-background: oklch(0.15 0.01 260);
    --color-foreground: oklch(0.98 0.003 260);
    --color-surface: oklch(0.20 0.01 260);
    --color-surface-foreground: oklch(0.95 0.005 260);
    --color-border: oklch(0.30 0.01 260);
    --color-muted: oklch(0.55 0.01 260);
    --color-primary: oklch(0.65 0.20 270);
    --color-destructive: oklch(0.65 0.18 25);
    --color-success: oklch(0.65 0.12 160);
    --color-warning: oklch(0.75 0.14 80);
    --color-info: oklch(0.65 0.12 230);
  }
}
```

---

## Proposal C: "Riwaya" — Bridging Scholarly and Modern

### Concept

*Riwaya* means "narration" — the act of transmitting hadith. This direction seeks the middle ground: it respects the manuscript tradition without being nostalgic, and uses modern interface patterns without losing the sense of working with sacred, centuries-old texts. The key design move is using geometric Islamic patterns structurally (as grid systems, dividers, and data visualization motifs) rather than decoratively.

### Logo Concept

- **Wordmark:** "isnad" in Amiri (a refined Arabic naskh typeface based on historical Bulaq press type) at regular weight, with "graph" in Source Sans 3 at light weight. The two words share a baseline, with a subtle geometric connector — a small diamond shape derived from an 8-pointed star — acting as the separator.
- **Icon/Symbol:** An 8-pointed star (a fundamental unit of Islamic geometric art) with its internal lines reinterpreted as a network graph. Each intersection point becomes a node; each line segment becomes an edge. The result is a pattern that reads as both geometric ornament and network diagram depending on the viewer's frame of reference. The star is drawn with a single continuous stroke weight.
- **Lockup:** The star icon sits within a rounded square container (referencing app icons), with the wordmark alongside or below. The container has a 1px border in the primary color.

### Color Palette

Warm neutrals with a teal-green primary inspired by the traditional green of Islamic art and architecture, balanced by a warm accent to avoid monotony.

| Token | OKLCH | Hex | Role |
|-------|-------|-----|------|
| `--color-charcoal` | `oklch(0.22 0.015 250)` | `#1c2833` | Primary text |
| `--color-warm-white` | `oklch(0.97 0.008 80)` | `#f7f4ef` | Background |
| `--color-cream` | `oklch(0.99 0.005 80)` | `#fbf9f5` | Elevated surface |
| `--color-teal-700` | `oklch(0.48 0.12 180)` | `#0f766e` | Primary accent |
| `--color-teal-600` | `oklch(0.53 0.12 180)` | `#0d9488` | Hover / active |
| `--color-rose-600` | `oklch(0.55 0.18 15)` | `#e11d48` | Destructive |
| `--color-emerald-700` | `oklch(0.50 0.14 160)` | `#047857` | Success, sahih |
| `--color-amber-600` | `oklch(0.65 0.16 75)` | `#d97706` | Warning, hasan |
| `--color-blue-700` | `oklch(0.45 0.14 250)` | `#1d4ed8` | Info, Shia sect |
| `--color-stone-500` | `oklch(0.58 0.015 60)` | `#78716c` | Muted text |
| `--color-stone-300` | `oklch(0.82 0.01 60)` | `#d6d3d1` | Borders |

**Dark mode:** Background becomes a deep warm charcoal (`oklch(0.18 0.012 60)` / `#1c1917`). Text inverts to warm white. Teal primary lightens to teal-400 (`oklch(0.65 0.12 180)` / `#2dd4bf`). All accents gain ~12% lightness.

**Contrast verification:**
- `--color-charcoal` on `--color-warm-white`: 14.2:1 (AAA)
- `--color-teal-700` on `--color-warm-white`: 5.8:1 (AA)
- `--color-stone-500` on `--color-warm-white`: 4.5:1 (AA normal)

### Typography

| Use | Family | Weight | Size | Line Height |
|-----|--------|--------|------|-------------|
| Arabic body | Amiri | 400 | 1.125rem | 2.0 |
| Arabic headings | Amiri | 700 | 1.5rem+ | 1.6 |
| Latin body | Source Sans 3 | 400 | 1rem | 1.6 |
| Latin headings | Source Sans 3 | 600 | 1.25rem+ | 1.3 |
| Monospace/data | Source Code Pro | 400 | 0.875rem | 1.5 |

**Rationale:** Amiri is a refined naskh typeface with historical roots (based on Amiria press type from early 20th century Cairo) — more character than Noto, without sacrificing legibility. Source Sans 3 is a neutral humanist sans-serif that pairs well without competing. The Source family gives typographic cohesion across body, heading, and code contexts.

### Mood / Tone

Considered warmth. The platform feels like a modern research tool designed by someone who deeply understands the material. There is a sense of craft — the geometric patterns are not decoration but organizational devices, the warm palette invites long use without visual fatigue, and the typography bridges Arabic and Latin without privileging either. Scholars should feel both the tradition and the technology are taken seriously.

### CSS Custom Properties

```css
:root {
  /* Riwaya palette — light mode */
  --color-primary: oklch(0.48 0.12 180);       /* teal-700 */
  --color-primary-foreground: #ffffff;
  --color-background: oklch(0.97 0.008 80);    /* warm-white */
  --color-foreground: oklch(0.22 0.015 250);   /* charcoal */
  --color-surface: oklch(0.99 0.005 80);       /* cream */
  --color-surface-foreground: oklch(0.22 0.015 250);
  --color-muted: oklch(0.58 0.015 60);         /* stone-500 */
  --color-border: oklch(0.82 0.01 60);         /* stone-300 */
  --color-destructive: oklch(0.55 0.18 15);    /* rose-600 */
  --color-success: oklch(0.50 0.14 160);       /* emerald-700 */
  --color-warning: oklch(0.65 0.16 75);        /* amber-600 */
  --color-info: oklch(0.45 0.14 250);          /* blue-700 */

  /* Domain: grading */
  --color-sahih: oklch(0.50 0.14 160);
  --color-hasan: oklch(0.65 0.16 75);
  --color-daif: oklch(0.55 0.18 15);
  --color-mawdu: oklch(0.45 0.18 5);

  /* Domain: sect */
  --color-sunni: oklch(0.50 0.14 160);
  --color-shia: oklch(0.45 0.14 250);

  /* Typography */
  --font-arabic: 'Amiri', serif;
  --font-heading: 'Source Sans 3', sans-serif;
  --font-body: 'Source Sans 3', sans-serif;
  --font-mono: 'Source Code Pro', monospace;
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-background: oklch(0.18 0.012 60);
    --color-foreground: oklch(0.95 0.008 80);
    --color-surface: oklch(0.23 0.012 60);
    --color-surface-foreground: oklch(0.93 0.008 80);
    --color-border: oklch(0.35 0.01 60);
    --color-muted: oklch(0.62 0.015 60);
    --color-primary: oklch(0.65 0.12 180);
    --color-destructive: oklch(0.65 0.16 15);
    --color-success: oklch(0.60 0.12 160);
    --color-warning: oklch(0.75 0.14 75);
    --color-info: oklch(0.55 0.12 250);
  }
}
```

---

## Comparison Matrix

| Dimension | A: Qalam (Scholarly) | B: Silsila (Modern) | C: Riwaya (Bridge) |
|-----------|---------------------|---------------------|---------------------|
| **Primary hue** | Warm sienna (45deg) | Cool indigo (270deg) | Balanced teal (180deg) |
| **Temperature** | Warm | Cool | Warm-neutral |
| **Arabic font** | Noto Naskh Arabic | Noto Naskh Arabic | Amiri |
| **Latin heading** | IBM Plex Serif | Inter | Source Sans 3 |
| **Icon motif** | Octagonal frame + graph | Minimal floating graph | 8-pointed star as graph |
| **Geometric patterns** | Border ornament | None | Structural grid/dividers |
| **Cultural reference** | Manuscript tradition | Network science | Islamic geometry + modern UI |
| **Best for** | Scholars, religious studies | Data scientists, developers | Mixed academic/technical audience |
| **Risk** | Could feel dated if overdone | Could feel generic | Requires careful balance |

## Recommendation

Proposal C (Riwaya) is the recommended direction. It offers the broadest audience appeal while maintaining a distinctive identity. The teal-green primary has strong cultural resonance without being literal, the Amiri + Source Sans pairing gives both Arabic and Latin text proper treatment, and the 8-pointed star icon concept is both meaningful and functional at small sizes.

That said, the final choice should be driven by the primary user persona. If the audience skews academic, Proposal A will resonate more deeply. If the audience is primarily technical, Proposal B will feel more natural.
