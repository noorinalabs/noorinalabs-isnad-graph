# Admin Panel — Wireframe Specification

**Author:** Sable Nakamura-Whitfield (Principal UX Designer)
**Issue:** #542
**Date:** 2026-03-29
**Status:** Draft

---

## 1. Design Intent

The admin panel is an internal operations dashboard for pipeline management, user administration, system health monitoring, and data quality oversight. Unlike the public-facing views, this page prioritizes information density and operational clarity over aesthetics. Every indicator must be glanceable — red/amber/green status at a glance, with drill-down for details.

Design principle: this is a control room, not a marketing page. No chrome, no decoration — just the data operators need to keep the platform running.

---

## 2. Page Layout

### 2.1 Desktop (>=1280px)

```
+-----------------------------------------------------------------------+
| HEADER: Isnad Graph > Admin                           [user avatar]   |
+-------+---------------------------------------------------------------+
| NAV   | ADMIN TABS                                                    |
| SIDE  | [Dashboard] [Users] [Pipeline] [Moderation] [Config]          |
| BAR   +---------------------------------------------------------------+
| (220) |                                                               |
|       |  +-------------------+  +-------------------+  +----------+  |
|       |  | SYSTEM HEALTH     |  | PIPELINE STATUS   |  | API USAGE|  |
|       |  | Neo4j: ● UP       |  | Last run: 2h ago  |  | Today:   |  |
|       |  | PostgreSQL: ● UP  |  | Status: ✓ Success |  | 12,847   |  |
|       |  | Redis: ● UP       |  | Duration: 4m 23s  |  | req/day  |  |
|       |  | API: ● UP         |  | Next: in 22h      |  |          |  |
|       |  +-------------------+  +-------------------+  +----------+  |
|       |                                                               |
|       |  +----------------------------------------------------------+ |
|       |  | DATA QUALITY METRICS                                     | |
|       |  | Narrators: 4,892  | Hadith: 38,421  | Chains: 52,103   | |
|       |  | Validation pass: 99.2%  | Rejected: 312 (0.8%)          | |
|       |  | Last validation: 2h ago | [View rejection log →]        | |
|       |  +----------------------------------------------------------+ |
|       |                                                               |
|       |  +----------------------------------------------------------+ |
|       |  | API USAGE (7-day)                                        | |
|       |  |  1200 ┤                          ╭─╮                     | |
|       |  |   800 ┤              ╭─╮   ╭─╮  │ │                     | |
|       |  |   400 ┤  ╭─╮  ╭─╮  │ │  │ │  │ │  ╭─╮                 | |
|       |  |     0 ┤──╯ ╰──╯ ╰──╯ ╰──╯ ╰──╯ ╰──╯ ╰──             | |
|       |  |        Mon  Tue  Wed  Thu  Fri  Sat  Sun               | |
|       |  +----------------------------------------------------------+ |
|       |                                                               |
|       |  +----------------------------------------------------------+ |
|       |  | RECENT AUDIT LOG                                         | |
|       |  | 14:23  admin@noorina  Pipeline triggered (manual)        | |
|       |  | 14:20  system         Validation completed (99.2% pass)  | |
|       |  | 12:01  admin@noorina  User role changed: tariq → editor  | |
|       |  | 11:45  system         Redis cache cleared                 | |
|       |  | [View full audit log →]                                  | |
|       |  +----------------------------------------------------------+ |
|       |                                                               |
+-------+---------------------------------------------------------------+
```

### 2.2 Tablet (768px–1279px)

```
+-----------------------------------------------------------------------+
| HEADER: Admin                          [hamburger] [user avatar]      |
+-----------------------------------------------------------------------+
| [Dashboard] [Users] [Pipeline] [Moderation] [Config]                  |
+-----------------------------------------------------------------------+
| +-------------------+  +-------------------+                          |
| | SYSTEM HEALTH     |  | PIPELINE STATUS   |                          |
| +-------------------+  +-------------------+                          |
| +-------------------+  +-------------------+                          |
| | DATA QUALITY      |  | API USAGE         |                          |
| +-------------------+  +-------------------+                          |
| +----------------------------------------------------------+         |
| | AUDIT LOG                                                 |         |
| +----------------------------------------------------------+         |
+-----------------------------------------------------------------------+
```

- Cards arranged in 2-column grid
- Charts compress to fit narrower viewport

### 2.3 Mobile (<768px)

```
+-----------------------------------+
| HEADER          [ham] [avatar]    |
+-----------------------------------+
| [Tab: Dash] [Users] [Pipeline]   |
+-----------------------------------+
| SYSTEM HEALTH                     |
| Neo4j: ● UP | PG: ● UP          |
| Redis: ● UP | API: ● UP         |
+-----------------------------------+
| PIPELINE: ✓ Success (2h ago)     |
+-----------------------------------+
| DATA QUALITY: 99.2% pass         |
+-----------------------------------+
| API: 12,847 req today            |
+-----------------------------------+
| AUDIT LOG (last 5)               |
| ...                               |
+-----------------------------------+
```

- Read-only on mobile — no pipeline triggers or user management actions
- Cards stack vertically, compact summaries only
- Tab navigation for admin sections

---

## 3. Dashboard Tab (Default)

### 3.1 System Health Cards

```
+-------------------------------------------+
| SYSTEM HEALTH                              |
+-------------------------------------------+
| Neo4j 5.x          ● UP    4,892 nodes    |
| PostgreSQL 16       ● UP    38,421 rows    |
| Redis 7.x          ● UP    1.2 GB used    |
| API (FastAPI)       ● UP    23ms avg resp  |
+-------------------------------------------+
```

- Status indicators: green circle (UP), red circle (DOWN), amber circle (DEGRADED)
- Each row shows: service name, version, status, key metric
- Click a row for detailed health view (connection pool, memory, query latency)
- Health checks poll every 30 seconds; last-checked timestamp in tooltip
- Status text always accompanies the color indicator (never color-only)

### 3.2 Pipeline Status Card

```
+-------------------------------------------+
| PIPELINE STATUS                            |
+-------------------------------------------+
| Last run:     2026-03-29 12:00 UTC         |
| Status:       ✓ Completed successfully     |
| Duration:     4m 23s                       |
| Next run:     2026-03-30 12:00 UTC (auto)  |
|                                            |
| Stage breakdown:                           |
| [✓] Acquire    ██████████  1m 02s          |
| [✓] Parse      ██████████  0m 48s          |
| [✓] Resolve    ██████████  1m 35s          |
| [✓] Load       ██████████  0m 38s          |
| [✓] Enrich     ██████████  0m 20s          |
|                                            |
| [Trigger manual run ▶]  [View logs]       |
+-------------------------------------------+
```

- Stage progress bars show relative time per stage
- Failed stages show [✗] in red with error message expandable
- "Trigger manual run" requires confirmation dialog
- "View logs" opens a scrollable log viewer (monospace, with timestamps)

### 3.3 Data Quality Metrics

```
+----------------------------------------------------------+
| DATA QUALITY                                              |
+----------------------------------------------------------+
| Entity counts:                                            |
| Narrators:  4,892    Hadith: 38,421    Chains: 52,103   |
| Collections: 14      Gradings: 87,204  Events: 234       |
|                                                           |
| Validation:                                               |
| Pass rate:     99.2% (38,109 / 38,421)                   |
| Rejected:      312 records (0.8%)                         |
| Last run:      2026-03-29 12:04 UTC                      |
|                                                           |
| Top rejection reasons:                                    |
| 1. Missing narrator ID (142)                              |
| 2. Duplicate chain hash (89)                              |
| 3. Invalid date range (54)                                |
| 4. Other (27)                                             |
|                                                           |
| [View rejection log →]  [Re-validate →]                  |
+----------------------------------------------------------+
```

### 3.4 API Usage Chart

```
+----------------------------------------------------------+
| API USAGE                                    [7d|30d|90d] |
+----------------------------------------------------------+
|                                                           |
|  1200 ┤                          ╭─╮                      |
|   800 ┤              ╭─╮   ╭─╮  │ │                      |
|   400 ┤  ╭─╮  ╭─╮  │ │  │ │  │ │  ╭─╮                  |
|     0 ┤──╯ ╰──╯ ╰──╯ ╰──╯ ╰──╯ ╰──╯ ╰──              |
|        Mon  Tue  Wed  Thu  Fri  Sat  Sun                  |
|                                                           |
| Total today: 12,847 requests                              |
| Top endpoints:                                            |
|   /api/v1/narrators    (4,231)                           |
|   /api/v1/hadith       (3,892)                           |
|   /api/v1/search       (2,104)                           |
|   /api/v1/graph        (1,820)                           |
+----------------------------------------------------------+
```

- Bar chart showing daily request volume
- Time range toggle: 7 days, 30 days, 90 days
- Top endpoints listed below chart
- Hover on bar shows exact count for that day

### 3.5 Audit Log

```
+----------------------------------------------------------+
| RECENT ACTIVITY                            [View full →] |
+----------------------------------------------------------+
| 14:23  admin@noorina   Pipeline triggered (manual)       |
| 14:20  system          Validation completed (99.2%)      |
| 12:01  admin@noorina   User role changed: tariq → editor |
| 11:45  system          Redis cache cleared               |
| 09:30  api-key-4a2f    Rate limit triggered (150 req/s)  |
+----------------------------------------------------------+
```

- Most recent 5 entries shown on dashboard
- Timestamp, actor, action description
- "View full" navigates to dedicated audit log viewer with filtering and search

---

## 4. Users Tab

```
+-----------------------------------------------------------------------+
| USERS                                    [Invite user +] [Export CSV] |
+-----------------------------------------------------------------------+
| [Search users...]                        [Role: All v] [Status: All v]|
+-----------------------------------------------------------------------+
| +-----+--------------------+----------+----------+-------------------+ |
| |     | Name               | Email    | Role     | Last active       | |
| +-----+--------------------+----------+----------+-------------------+ |
| | [✓] | Kwame Asante       | k@...    | Admin    | 2h ago            | |
| | [ ] | Tariq Al-Rashidi   | t@...    | Editor   | 1d ago            | |
| | [ ] | Mei-Lin Chang      | m@...    | Viewer   | 3d ago            | |
| | [ ] | api-key-4a2f       | —        | API      | 12m ago           | |
| +-----+--------------------+----------+----------+-------------------+ |
|                                                                       |
| Selected: 1                         [Edit role] [Disable] [Delete]   |
+-----------------------------------------------------------------------+
| API KEYS                                            [Generate key +]  |
+-----------------------------------------------------------------------+
| +--------------------+----------+-----------+------------------------+ |
| | Key                | Owner    | Created   | Last used              | |
| +--------------------+----------+-----------+------------------------+ |
| | key-4a2f...8e91    | system   | 2026-03-01| 12m ago               | |
| | key-7b3c...2d45    | tariq    | 2026-03-15| 1d ago                | |
| +--------------------+----------+-----------+------------------------+ |
| Selected: 0                                  [Revoke] [Regenerate]   |
+-----------------------------------------------------------------------+
```

- User table with sortable columns
- Bulk actions via checkbox selection
- Role options: Admin, Editor, Viewer, API
- Status indicators: active (green), disabled (gray)
- "Invite user" opens a modal with email input and role selector
- API keys section below user table
- Keys partially masked (first 8 + last 4 characters visible)
- "Generate key" opens modal with scope and expiry settings
- Destructive actions (Delete, Revoke) require confirmation dialog

---

## 5. Pipeline Tab

```
+-----------------------------------------------------------------------+
| PIPELINE MANAGEMENT                                                   |
+-----------------------------------------------------------------------+
| [Trigger full pipeline ▶]  [Select stages...] [Trigger selected ▶]   |
+-----------------------------------------------------------------------+
|                                                                       |
| RUN HISTORY                                                           |
+-----------------------------------------------------------------------+
| +----------+--------+----------+----------+--------------------------+ |
| | Run ID   | Status | Started  | Duration | Stages                   | |
| +----------+--------+----------+----------+--------------------------+ |
| | run-047  | ✓ Pass | 12:00    | 4m 23s   | All 5 stages            | |
| | run-046  | ✗ Fail | 00:00    | 2m 11s   | Failed at: Resolve      | |
| | run-045  | ✓ Pass | 12:00 y. | 4m 18s   | All 5 stages            | |
| +----------+--------+----------+----------+--------------------------+ |
|                                                                       |
| Expand run-046:                                                       |
| +---------------------------------------------------------------+    |
| | [✓] Acquire   1m 02s   12,847 records fetched                 |    |
| | [✓] Parse     0m 48s   12,847 → 12,501 parsed (346 skipped)  |    |
| | [✗] Resolve   0m 21s   ERROR: FAISS index corrupt             |    |
| |     Stack trace:                                               |    |
| |     > src/resolve/disambiguate.py:142                          |    |
| |     > faiss.read_index("data/staging/narrator.faiss")          |    |
| |     > RuntimeError: could not read index                       |    |
| | [—] Load      skipped                                         |    |
| | [—] Enrich    skipped                                         |    |
| |                                                                |    |
| | [Re-run from Resolve ▶]  [View full logs]                    |    |
| +---------------------------------------------------------------+    |
|                                                                       |
| SOURCE CONFIGURATION                                                  |
| +--------------------+----------+-----------------------------------+ |
| | Source             | Enabled  | Last fetch                        | |
| +--------------------+----------+-----------------------------------+ |
| | Sunnah.com API     | [x]      | 2026-03-29 12:00                 | |
| | Kaggle (Bukhari)   | [x]      | 2026-03-29 12:00                 | |
| | IslamWeb           | [x]      | 2026-03-29 12:01                 | |
| | al-Kafi (manual)   | [ ]      | 2026-03-15 (stale)               | |
| +--------------------+----------+-----------------------------------+ |
+-----------------------------------------------------------------------+
```

- "Trigger full pipeline" runs all 5 stages sequentially
- "Select stages" allows cherry-picking specific stages to run
- Run history table with expandable rows for stage details
- Failed runs show error details, stack trace, and "Re-run from [stage]" button
- Source configuration table with enable/disable toggles

---

## 6. Moderation Tab

```
+-----------------------------------------------------------------------+
| MODERATION QUEUE (7 pending)                                          |
+-----------------------------------------------------------------------+
| [All (7)] [Narrator edits (3)] [Hadith corrections (2)] [Reports (2)]|
+-----------------------------------------------------------------------+
|                                                                       |
| +-------------------------------------------------------------------+ |
| | NARRATOR EDIT REQUEST                      Submitted: 2h ago      | |
| | User: tariq@noorina  |  Type: Name correction                    | |
| |                                                                   | |
| | Current:  Abu Hurairah (ابو هريرة)                                 | |
| | Proposed: Abu Hurayra al-Dawsi (ابو هريرة الدوسي)                   | |
| | Reason: "Adding full nisba for disambiguation"                     | |
| |                                                                   | |
| | [Approve ✓]  [Reject ✗]  [Edit & approve]                        | |
| +-------------------------------------------------------------------+ |
|                                                                       |
| +-------------------------------------------------------------------+ |
| | HADITH CORRECTION                          Submitted: 5h ago      | |
| | User: mei@noorina  |  Type: Translation fix                      | |
| |                                                                   | |
| | Current:  "Deeds are by intentions..."                            | |
| | Proposed: "Actions are judged by intentions..."                    | |
| | Reason: "More accurate translation per Lane's Lexicon"             | |
| |                                                                   | |
| | [Approve ✓]  [Reject ✗]  [Edit & approve]                        | |
| +-------------------------------------------------------------------+ |
|                                                                       |
+-----------------------------------------------------------------------+
```

- Queue items categorized by type
- Each item shows: current vs proposed state, submitter, reason
- Three actions: Approve, Reject (with required reason), Edit & Approve
- Rejected items notify the submitter with the rejection reason
- Queue count shown in tab badge

---

## 7. Config Tab

```
+-----------------------------------------------------------------------+
| CONFIGURATION                                                         |
+-----------------------------------------------------------------------+
|                                                                       |
| GENERAL                                                               |
| +-------------------------------------------------------------------+ |
| | Site name:          [Isnad Graph                              ]   | |
| | Default language:   [English v]                                   | |
| | API rate limit:     [150    ] requests/second                     | |
| | Session timeout:    [30     ] minutes                             | |
| +-------------------------------------------------------------------+ |
|                                                                       |
| PIPELINE                                                              |
| +-------------------------------------------------------------------+ |
| | Auto-run schedule:  [Daily at 12:00 UTC v]                        | |
| | Node count limit:   [5000   ] (max for graph explorer)            | |
| | Similarity threshold: [0.80 ] (parallel detection cutoff)          | |
| | Validation strictness: [Standard v]                                | |
| +-------------------------------------------------------------------+ |
|                                                                       |
| CACHE                                                                 |
| +-------------------------------------------------------------------+ |
| | Redis TTL:          [3600   ] seconds                             | |
| | Cache warming:      [x] Enabled                                   | |
| | [Clear all cache]                                                  | |
| +-------------------------------------------------------------------+ |
|                                                                       |
|                                   [Save changes]  [Revert to saved]  |
+-----------------------------------------------------------------------+
```

- Form-based configuration with current values pre-filled
- "Save changes" validates inputs and persists
- "Revert to saved" resets form to last-saved state
- Destructive actions (Clear cache) require confirmation
- Changes to pipeline config take effect on next run

---

## 8. RTL and Bidirectional Text

### 8.1 Admin Content

- Arabic text in moderation queue items uses `dir="rtl"` blocks
- Narrator names in user/audit tables show English only (admin context)
- Moderation items show both Arabic and English with proper bidi isolation

### 8.2 Layout Direction

- Admin layout remains LTR throughout — this is an internal operations interface
- Arabic content within moderation items and data quality examples uses inline RTL blocks

### 8.3 Font Stack

```css
--font-arabic: 'Noto Naskh Arabic', 'Geeza Pro', 'Traditional Arabic', serif;
--font-ui: system-ui, -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;  /* logs, stack traces */
```

---

## 9. Accessibility

### 9.1 Keyboard Navigation

| Key | Action |
|-----|--------|
| Tab | Move through tab bar, then through cards/tables within active tab |
| Arrow left/right | Switch between admin tabs |
| Arrow up/down | Navigate table rows |
| Enter | Expand table row, activate buttons |
| Space | Toggle checkboxes |
| Escape | Close modals, cancel actions |

### 9.2 Screen Reader Support

- Tab bar: `role="tablist"` with `aria-selected` on active tab
- Status indicators: "Neo4j: status UP" (never just the color)
- Pipeline stages: "Acquire: completed, duration 1 minute 2 seconds"
- Moderation queue: `aria-label="Moderation queue, 7 pending items"`
- Charts: accessible data table alternative below each chart
- Audit log: `role="log"` with `aria-live="polite"` for new entries

### 9.3 High Contrast Mode

- Status indicator circles gain 2px black outlines
- Chart bars gain 2px black outlines and pattern fills
- Table row borders become 1px solid black
- Focus ring: 3px solid with offset on all interactive elements

### 9.4 Reduced Motion

- Health check polling indicators are static (no pulse animation)
- Chart transitions are instant
- Log entries appear without slide-in animation

---

## 10. Responsive Breakpoint Summary

| Feature | Desktop (>=1280) | Tablet (768-1279) | Mobile (<768) |
|---------|:---:|:---:|:---:|
| Nav sidebar | Visible (220px) | Hamburger overlay | Hamburger overlay |
| Admin tabs | Horizontal tab bar | Horizontal tab bar | Scrollable tabs |
| Dashboard cards | 3-column grid | 2-column grid | Single column |
| User management | Full table + actions | Full table, actions in menu | Read-only list |
| Pipeline controls | Full controls | Full controls | Read-only status |
| Moderation queue | Full cards + actions | Full cards + actions | Read-only cards |
| Charts | Full size | Compressed | Sparkline only |
| Config panel | Full form | Full form | Read-only display |
| Audit log | 5 entries + full view | 5 entries + full view | 3 entries |

---

## 11. Component Mapping

| Wireframe element | Component | Notes |
|-------------------|-----------|-------|
| Page shell | `AdminPage.tsx` | New page, route: `/admin`, requires admin role |
| Tab navigation | `AdminTabs` | Horizontal tab bar with badge counts |
| System health | `SystemHealthCards` | Polling health check display |
| Pipeline status | `PipelineStatus` | Stage breakdown, trigger controls |
| Data quality | `DataQualityMetrics` | Entity counts, validation stats |
| API usage chart | `ApiUsageChart` | Bar chart with time range toggle |
| Audit log | `AuditLog` | Timestamped event list, filterable |
| User table | `UserManagement` | CRUD table with role management |
| API key manager | `ApiKeyManager` | Generate, revoke, list keys |
| Moderation queue | `ModerationQueue` | Review cards with approve/reject |
| Config form | `AdminConfig` | Form with validation and save |

---

## 12. Design Tokens

```css
/* Status indicators */
--status-up: oklch(60% 0.15 150);        /* green */
--status-down: oklch(55% 0.15 25);       /* red */
--status-degraded: oklch(70% 0.15 60);   /* amber */
--status-unknown: oklch(55% 0.05 0);     /* gray */

/* Admin cards */
--admin-card-bg: #ffffff;
--admin-card-border: #e0e0e0;
--admin-card-padding: 16px;
--admin-card-radius: 6px;

/* Charts */
--chart-bar-fill: oklch(65% 0.15 250);   /* blue */
--chart-bar-hover: oklch(55% 0.18 250);  /* darker blue */
--chart-grid: #f0f0f0;
--chart-axis: #333333;

/* Log entries */
--log-font: var(--font-mono);
--log-font-size: 13px;
--log-timestamp-color: #888888;
--log-actor-color: #1a73e8;

/* Moderation */
--mod-approve: oklch(60% 0.15 150);
--mod-reject: oklch(55% 0.15 25);
--mod-pending-bg: oklch(95% 0.02 60);    /* light amber tint */
```

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-29 | Sable Nakamura-Whitfield | Initial wireframe specification |
