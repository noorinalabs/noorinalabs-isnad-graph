# Playwright E2E Test Plan

This document defines the end-to-end test plan for the isnad-graph frontend using
[Playwright](https://playwright.dev/) via the
[pytest-playwright](https://playwright.dev/python/docs/test-runners) Python integration.

> **Status:** Draft -- pending review before implementation (issue F2).
>
> **Coordination note:** Coordinate with Yara Hadid (Security Engineer) on security-related
> test scenarios to avoid duplication with dedicated security tests.

---

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Test Data Requirements](#2-test-data-requirements)
3. [Test Scenarios](#3-test-scenarios)
   - 3.1 [Authentication Flows](#31-authentication-flows)
   - 3.2 [Navigation and Routing](#32-navigation-and-routing)
   - 3.3 [Narrators Pages](#33-narrators-pages)
   - 3.4 [Hadiths Pages](#34-hadiths-pages)
   - 3.5 [Collections Pages](#35-collections-pages)
   - 3.6 [Search Page](#36-search-page)
   - 3.7 [Timeline Page](#37-timeline-page)
   - 3.8 [Comparative Page](#38-comparative-page)
   - 3.9 [Graph Explorer Page](#39-graph-explorer-page)
   - 3.10 [Admin Panel](#310-admin-panel)
   - 3.11 [Error States and Edge Cases](#311-error-states-and-edge-cases)
   - 3.12 [Accessibility](#312-accessibility)
4. [CI Integration Plan](#4-ci-integration-plan)
5. [Priority Matrix](#5-priority-matrix)

---

## 1. Environment Setup

### Prerequisites

- Python 3.14+ with `uv` package manager
- Node.js (for the Vite frontend dev server)
- Docker Compose (for Neo4j, PostgreSQL, Redis)
- Playwright browsers installed

### Local Setup

```bash
# Install project deps (includes pytest-playwright)
make setup

# Install Playwright browsers
uv run playwright install --with-deps chromium

# Start infrastructure services
make infra

# Seed test data (see Section 2)
uv run python scripts/seed_e2e_data.py

# Start the API server (background)
uv run uvicorn src.api.app:app --port 8000 &

# Start the frontend dev server (background)
cd frontend && npm run dev &

# Run E2E tests
E2E_BASE_URL=http://localhost:3000 uv run pytest tests/e2e/ -m e2e --headed
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `E2E_BASE_URL` | `http://localhost:3000` | Frontend URL for tests |
| `E2E_API_URL` | `http://localhost:8000` | API URL for direct setup calls |
| `E2E_ADMIN_EMAIL` | (from seed) | Pre-seeded admin user email |
| `E2E_ADMIN_TOKEN` | (from seed) | Pre-seeded admin JWT for setup |
| `E2E_USER_EMAIL` | (from seed) | Pre-seeded regular user email |
| `E2E_USER_TOKEN` | (from seed) | Pre-seeded regular user JWT |

### Existing Fixtures

The project already has E2E scaffolding in `tests/e2e/`:

- `conftest.py` -- session-scoped browser context (1280x720 viewport, base URL from env)
- `test_smoke.py` -- basic page-load assertions for all public routes
- `test_navigation.py` -- sidebar link traversal and drill-down navigation

New tests should extend this structure rather than duplicate it.

---

## 2. Test Data Requirements

### Seed Data

All E2E tests require a deterministic seed dataset loaded before the test session.
The seed script (`scripts/seed_e2e_data.py`, to be created) must be **idempotent** and
provision:

| Entity | Minimum Count | Notes |
|--------|---------------|-------|
| Narrators | 10 | Mix of Sunni/Shia, varying trustworthiness |
| Hadiths | 20 | Include parallels, multiple grades |
| Collections | 4 | At least one Sunni and one Shia canonical |
| Chains | 15 | Mix of complete and incomplete |
| Parallel pairs | 5 | Cross-sect and same-sect variants |
| Users | 3 | 1 admin, 1 regular, 1 suspended |
| Moderation items | 3 | pending, approved, rejected |

### Auth Tokens

For tests that require authentication, inject tokens via `localStorage` using
Playwright's `addInitScript` or `evaluate` before navigation:

```python
def inject_auth_token(page: Page, token: str) -> None:
    """Set access_token in localStorage before page load."""
    page.add_init_script(f"window.localStorage.setItem('access_token', '{token}');")
```

### Test Isolation

- Each test class should assume seed data exists but must **not mutate shared state**
  unless the test explicitly verifies a write operation.
- Write-operation tests (admin user updates, moderation actions) must use unique
  entity IDs or restore original state in teardown.

---

## 3. Test Scenarios

Each scenario follows the format:

> **ID** | **Description** | **Preconditions** | **Steps** | **Expected Results** | **Priority**

### 3.1 Authentication Flows

#### AUTH-001: OAuth Login Initiation (Google)

| Field | Value |
|-------|-------|
| Description | Verify that clicking "Login with Google" initiates the OAuth flow |
| Preconditions | User is not authenticated (no token in localStorage) |
| Steps | 1. Navigate to the login page or trigger login action 2. Click "Login with Google" button 3. Observe the redirect |
| Expected Results | Browser redirects to Google OAuth authorization URL with correct `client_id`, `redirect_uri`, `state`, and PKCE `code_challenge` parameters |
| Priority | P0 -- Critical |

#### AUTH-002: OAuth Login Initiation (GitHub)

| Field | Value |
|-------|-------|
| Description | Verify that clicking "Login with GitHub" initiates the OAuth flow |
| Preconditions | User is not authenticated |
| Steps | 1. Navigate to the login page 2. Click "Login with GitHub" button 3. Observe the redirect |
| Expected Results | Browser redirects to GitHub OAuth authorization URL with correct parameters |
| Priority | P0 -- Critical |

#### AUTH-003: OAuth Callback -- Successful Token Exchange

| Field | Value |
|-------|-------|
| Description | Simulate a successful OAuth callback returning access and refresh tokens |
| Preconditions | Mock OAuth provider response or use a test provider stub |
| Steps | 1. Navigate to `/api/v1/auth/callback/{provider}?code=VALID&state=VALID` (mocked) 2. Verify tokens are stored in localStorage/cookies 3. Verify redirect to the main app |
| Expected Results | `access_token` stored in localStorage, `refresh_token` set as httpOnly cookie, user redirected to `/narrators` |
| Priority | P0 -- Critical |

#### AUTH-004: OAuth Callback -- Invalid Code

| Field | Value |
|-------|-------|
| Description | Verify error handling when the OAuth code exchange fails |
| Preconditions | Mock OAuth provider to reject the code |
| Steps | 1. Navigate to callback URL with an invalid code 2. Observe error display |
| Expected Results | User sees an error message, is not authenticated, can retry login |
| Priority | P1 -- High |

#### AUTH-005: OAuth Callback -- Unsupported Provider

| Field | Value |
|-------|-------|
| Description | Verify error when an unsupported provider is requested |
| Preconditions | None |
| Steps | 1. Navigate to `/api/v1/auth/login/unsupported` |
| Expected Results | API returns 400 with "Unsupported provider" detail |
| Priority | P2 -- Medium |

#### AUTH-006: Token Refresh

| Field | Value |
|-------|-------|
| Description | Verify that an expired access token triggers a silent refresh |
| Preconditions | User has valid refresh token in cookie, access token is expired |
| Steps | 1. Inject expired access token and valid refresh cookie 2. Navigate to an authenticated page 3. Observe network requests |
| Expected Results | App calls `/api/v1/auth/refresh`, receives new tokens, page loads normally without login prompt |
| Priority | P0 -- Critical |

#### AUTH-007: Token Refresh -- Expired Refresh Token

| Field | Value |
|-------|-------|
| Description | Verify behavior when both tokens are expired |
| Preconditions | Expired access token, expired/revoked refresh token |
| Steps | 1. Inject expired tokens 2. Navigate to any page 3. Observe redirect |
| Expected Results | User is redirected to login, old tokens cleared from storage |
| Priority | P1 -- High |

#### AUTH-008: Logout Flow

| Field | Value |
|-------|-------|
| Description | Verify that logout clears session and redirects |
| Preconditions | User is authenticated |
| Steps | 1. Inject valid auth token 2. Navigate to any page 3. Click logout button/link 4. Observe state change |
| Expected Results | `access_token` removed from localStorage, refresh cookie cleared, API call to `/api/v1/auth/logout` made, user redirected to login |
| Priority | P0 -- Critical |

#### AUTH-009: /auth/me Endpoint

| Field | Value |
|-------|-------|
| Description | Verify the current-user endpoint returns correct data |
| Preconditions | User is authenticated with valid token |
| Steps | 1. Inject valid token 2. Observe AuthProvider fetch on page load |
| Expected Results | `useAuth` hook populates `user` with `id`, `email`, `name`, `is_admin` fields |
| Priority | P1 -- High |

#### AUTH-010: /auth/me -- Invalid Token

| Field | Value |
|-------|-------|
| Description | Verify that an invalid or tampered token results in unauthenticated state |
| Preconditions | Inject a malformed JWT in localStorage |
| Steps | 1. Set `access_token` to a garbage string 2. Navigate to any page |
| Expected Results | AuthProvider sets `user` to null, app behaves as unauthenticated |
| Priority | P1 -- High |

---

### 3.2 Navigation and Routing

#### NAV-001: Home Redirects to Narrators

| Field | Value |
|-------|-------|
| Description | Verify that `/` redirects to `/narrators` |
| Preconditions | None |
| Steps | 1. Navigate to `/` |
| Expected Results | URL changes to `/narrators`, Narrators page content is visible |
| Priority | P0 -- Critical |

#### NAV-002: Sidebar Links Navigate Correctly

| Field | Value |
|-------|-------|
| Description | Verify all 7 sidebar links navigate to their pages |
| Preconditions | None |
| Steps | 1. Navigate to `/` 2. For each sidebar link (Narrators, Hadiths, Collections, Search, Timeline, Compare, Graph Explorer): click and verify page loads |
| Expected Results | Each click updates the URL and renders the correct page heading |
| Priority | P0 -- Critical |

#### NAV-003: Active Sidebar Link Styling

| Field | Value |
|-------|-------|
| Description | Verify that the currently active sidebar link is visually highlighted |
| Preconditions | None |
| Steps | 1. Navigate to `/hadiths` 2. Inspect sidebar link styles |
| Expected Results | Hadiths link has `font-weight: 700` and `color: #1a73e8` |
| Priority | P2 -- Medium |

#### NAV-004: Admin Link Visible Only for Admins

| Field | Value |
|-------|-------|
| Description | Verify the "Admin Dashboard" link appears only for admin users |
| Preconditions | Two test runs: one with admin token, one with regular user token |
| Steps | 1. (Admin) Inject admin token, navigate, check sidebar 2. (Regular) Inject regular token, navigate, check sidebar |
| Expected Results | Admin sees "Admin Dashboard" link below separator; regular user does not |
| Priority | P0 -- Critical |

#### NAV-005: Auth-Gated Admin Route -- Unauthenticated

| Field | Value |
|-------|-------|
| Description | Verify unauthenticated users are redirected away from `/admin/*` |
| Preconditions | No auth token |
| Steps | 1. Navigate directly to `/admin/users` |
| Expected Results | User is redirected to `/narrators` |
| Priority | P0 -- Critical |

#### NAV-006: Auth-Gated Admin Route -- Non-Admin User

| Field | Value |
|-------|-------|
| Description | Verify non-admin authenticated users are redirected away from admin routes |
| Preconditions | Inject regular user token (is_admin=false) |
| Steps | 1. Navigate directly to `/admin/users` |
| Expected Results | User is redirected to `/narrators` |
| Priority | P0 -- Critical |

#### NAV-007: Admin Index Redirects to Users

| Field | Value |
|-------|-------|
| Description | Verify `/admin` redirects to `/admin/users` |
| Preconditions | Authenticated as admin |
| Steps | 1. Navigate to `/admin` |
| Expected Results | URL changes to `/admin/users` |
| Priority | P1 -- High |

#### NAV-008: Deep Link Navigation

| Field | Value |
|-------|-------|
| Description | Verify direct URL entry for detail pages works |
| Preconditions | Seed data with known IDs |
| Steps | 1. Navigate directly to `/narrators/{known_id}` 2. Navigate directly to `/hadiths/{known_id}` 3. Navigate directly to `/collections/{known_id}` |
| Expected Results | Each detail page loads with correct entity data |
| Priority | P1 -- High |

#### NAV-009: 404 Handling -- Unknown Route

| Field | Value |
|-------|-------|
| Description | Verify behavior when navigating to a non-existent route |
| Preconditions | None |
| Steps | 1. Navigate to `/nonexistent-page` |
| Expected Results | Either a 404 page or redirect to home (verify current behavior and document) |
| Priority | P2 -- Medium |

#### NAV-010: Browser Back/Forward Navigation

| Field | Value |
|-------|-------|
| Description | Verify browser history navigation works correctly with React Router |
| Preconditions | None |
| Steps | 1. Navigate: `/narrators` -> `/hadiths` -> `/search` 2. Click browser Back twice 3. Click browser Forward once |
| Expected Results | Back returns to `/narrators`, Forward goes to `/hadiths` |
| Priority | P1 -- High |

---

### 3.3 Narrators Pages

#### NAR-001: Narrators List Page Loads

| Field | Value |
|-------|-------|
| Description | Verify the narrators listing page renders a table of narrators |
| Preconditions | Seed data with narrators |
| Steps | 1. Navigate to `/narrators` 2. Wait for network idle |
| Expected Results | Page heading contains "Narrator", table/list shows narrator entries with names |
| Priority | P0 -- Critical |

#### NAR-002: Narrators List -- Pagination

| Field | Value |
|-------|-------|
| Description | Verify pagination controls work on the narrators list |
| Preconditions | Seed data with > 20 narrators |
| Steps | 1. Navigate to `/narrators` 2. Click next page 3. Verify new results load |
| Expected Results | Different set of narrators displayed, page indicator updates |
| Priority | P1 -- High |

#### NAR-003: Narrators List -- Search/Filter

| Field | Value |
|-------|-------|
| Description | Verify searching narrators by name filters the list |
| Preconditions | Seed data includes narrators with known Arabic/English names |
| Steps | 1. Navigate to `/narrators` 2. Enter a search term (e.g., "Bukhari") 3. Submit/trigger search |
| Expected Results | List filters to show only matching narrators |
| Priority | P1 -- High |

#### NAR-004: Narrator Detail Page

| Field | Value |
|-------|-------|
| Description | Verify clicking a narrator row navigates to the detail page |
| Preconditions | Seed data |
| Steps | 1. Navigate to `/narrators` 2. Click on a narrator row 3. Wait for detail page |
| Expected Results | URL changes to `/narrators/{id}`, detail page shows name, kunya, nisba, generation, trustworthiness, and graph metrics (centrality, PageRank) |
| Priority | P0 -- Critical |

#### NAR-005: Narrator Detail -- Chain List

| Field | Value |
|-------|-------|
| Description | Verify the narrator detail page shows chains the narrator participates in |
| Preconditions | Seed data with chains for the narrator |
| Steps | 1. Navigate to `/narrators/{id}` 2. Locate chains section |
| Expected Results | List of chains displayed with hadith text preview and grade |
| Priority | P1 -- High |

---

### 3.4 Hadiths Pages

#### HAD-001: Hadiths List Page Loads

| Field | Value |
|-------|-------|
| Description | Verify the hadiths listing page renders |
| Preconditions | Seed data |
| Steps | 1. Navigate to `/hadiths` |
| Expected Results | Page heading contains "Hadith", list shows hadith entries with matn preview |
| Priority | P0 -- Critical |

#### HAD-002: Hadiths List -- Pagination

| Field | Value |
|-------|-------|
| Description | Verify pagination on hadiths list |
| Preconditions | Seed data with > 20 hadiths |
| Steps | 1. Navigate to `/hadiths` 2. Click next page |
| Expected Results | New page of hadiths loads |
| Priority | P1 -- High |

#### HAD-003: Hadith Detail Page

| Field | Value |
|-------|-------|
| Description | Verify hadith detail page shows full content |
| Preconditions | Seed data |
| Steps | 1. Navigate to `/hadiths/{id}` |
| Expected Results | Page shows Arabic matn, English translation (if available), grade, topic tags, source corpus |
| Priority | P0 -- Critical |

#### HAD-004: Hadith Detail -- Parallel Hadiths

| Field | Value |
|-------|-------|
| Description | Verify parallel hadiths section on detail page |
| Preconditions | Seed data with parallel pairs |
| Steps | 1. Navigate to a hadith known to have parallels 2. Locate parallels section |
| Expected Results | Parallels listed with similarity score, variant type, and cross-sect indicator |
| Priority | P1 -- High |

---

### 3.5 Collections Pages

#### COL-001: Collections List Page Loads

| Field | Value |
|-------|-------|
| Description | Verify the collections listing page renders |
| Preconditions | Seed data |
| Steps | 1. Navigate to `/collections` |
| Expected Results | Page heading contains "Collection", list shows collection names, compiler, sect |
| Priority | P0 -- Critical |

#### COL-002: Collection Detail Page

| Field | Value |
|-------|-------|
| Description | Verify collection detail page shows metadata and hadiths |
| Preconditions | Seed data |
| Steps | 1. Navigate to `/collections/{id}` |
| Expected Results | Page shows collection name (Arabic/English), compiler, compilation year, sect, total hadiths, book count |
| Priority | P0 -- Critical |

---

### 3.6 Search Page

#### SRC-001: Search Page Loads

| Field | Value |
|-------|-------|
| Description | Verify the search page renders with an input field |
| Preconditions | None |
| Steps | 1. Navigate to `/search` |
| Expected Results | Search input is visible and focusable |
| Priority | P0 -- Critical |

#### SRC-002: Text Search Returns Results

| Field | Value |
|-------|-------|
| Description | Verify text search returns matching narrators, hadiths, and collections |
| Preconditions | Seed data |
| Steps | 1. Navigate to `/search` 2. Type "Bukhari" 3. Press Enter |
| Expected Results | Results displayed with type indicator (narrator/hadith/collection), title, and relevance score |
| Priority | P0 -- Critical |

#### SRC-003: Semantic Search

| Field | Value |
|-------|-------|
| Description | Verify semantic search toggle/mode returns vector-similarity results |
| Preconditions | Seed data with embeddings, semantic search enabled |
| Steps | 1. Navigate to `/search` 2. Switch to semantic search mode (if toggle exists) 3. Enter a query 4. Submit |
| Expected Results | Results ranked by semantic similarity rather than keyword match |
| Priority | P1 -- High |

#### SRC-004: Search Result Navigation

| Field | Value |
|-------|-------|
| Description | Verify clicking a search result navigates to the detail page |
| Preconditions | Seed data |
| Steps | 1. Perform a search 2. Click the first result |
| Expected Results | Navigates to the correct detail page (`/narrators/{id}`, `/hadiths/{id}`, or `/collections/{id}`) based on result type |
| Priority | P1 -- High |

#### SRC-005: Empty Search Results

| Field | Value |
|-------|-------|
| Description | Verify appropriate message for zero results |
| Preconditions | None |
| Steps | 1. Search for "zzzznonexistent999" |
| Expected Results | "No results found" or equivalent message displayed |
| Priority | P2 -- Medium |

---

### 3.7 Timeline Page

#### TML-001: Timeline Page Loads

| Field | Value |
|-------|-------|
| Description | Verify the timeline page renders with entries |
| Preconditions | Seed data with narrators having birth/death years |
| Steps | 1. Navigate to `/timeline` |
| Expected Results | Page heading contains "Timeline", entries displayed chronologically |
| Priority | P0 -- Critical |

#### TML-002: Timeline Range Filter

| Field | Value |
|-------|-------|
| Description | Verify filtering timeline by year range |
| Preconditions | Seed data spanning multiple centuries AH |
| Steps | 1. Navigate to `/timeline` 2. Set start year and end year filters 3. Apply |
| Expected Results | Only entries within the specified AH year range are displayed |
| Priority | P1 -- High |

#### TML-003: Timeline Entry Click

| Field | Value |
|-------|-------|
| Description | Verify clicking a timeline entry navigates to the narrator detail |
| Preconditions | Seed data |
| Steps | 1. Navigate to `/timeline` 2. Click an entry |
| Expected Results | Navigates to the narrator detail page |
| Priority | P2 -- Medium |

---

### 3.8 Comparative Page

#### CMP-001: Comparative Page Loads

| Field | Value |
|-------|-------|
| Description | Verify the comparative/parallel analysis page renders |
| Preconditions | Seed data with parallel pairs |
| Steps | 1. Navigate to `/compare` |
| Expected Results | Page heading contains "Compar", parallel pairs listed with similarity scores |
| Priority | P0 -- Critical |

#### CMP-002: Comparative -- Cross-Sect Filter

| Field | Value |
|-------|-------|
| Description | Verify filtering for cross-sectarian parallels |
| Preconditions | Seed data with both cross-sect and same-sect parallels |
| Steps | 1. Navigate to `/compare` 2. Enable cross-sect filter |
| Expected Results | Only cross-sectarian parallel pairs displayed |
| Priority | P1 -- High |

#### CMP-003: Comparative -- Pagination

| Field | Value |
|-------|-------|
| Description | Verify pagination on the comparisons list |
| Preconditions | Seed data with > 20 parallel pairs |
| Steps | 1. Navigate to `/compare` 2. Click next page |
| Expected Results | New page of parallel pairs loads |
| Priority | P2 -- Medium |

---

### 3.9 Graph Explorer Page

#### GRX-001: Graph Explorer Page Loads

| Field | Value |
|-------|-------|
| Description | Verify the graph explorer page renders with the force-directed graph |
| Preconditions | Seed data |
| Steps | 1. Navigate to `/graph` |
| Expected Results | Page heading contains "Graph", canvas/SVG element visible for the force graph |
| Priority | P0 -- Critical |

#### GRX-002: Graph -- Narrator Network Visualization

| Field | Value |
|-------|-------|
| Description | Verify selecting a narrator renders their teacher/student network |
| Preconditions | Seed data with narrator networks |
| Steps | 1. Navigate to `/graph` 2. Select or search for a narrator 3. Wait for graph to render |
| Expected Results | Graph displays nodes (narrators) and edges (transmission relationships), with teacher/student counts shown |
| Priority | P1 -- High |

#### GRX-003: Graph -- Depth Control

| Field | Value |
|-------|-------|
| Description | Verify changing network depth updates the graph |
| Preconditions | Seed data |
| Steps | 1. Navigate to `/graph` 2. Select a narrator 3. Change depth from 1 to 2 |
| Expected Results | Graph expands to show second-degree connections |
| Priority | P2 -- Medium |

#### GRX-004: Graph -- Node Click Navigation

| Field | Value |
|-------|-------|
| Description | Verify clicking a node in the graph navigates to that narrator's detail |
| Preconditions | Graph loaded with nodes |
| Steps | 1. Navigate to `/graph` 2. Load a network 3. Click a node |
| Expected Results | Navigates to `/narrators/{id}` for the clicked narrator |
| Priority | P2 -- Medium |

---

### 3.10 Admin Panel

#### ADM-001: Admin Layout Loads for Admin User

| Field | Value |
|-------|-------|
| Description | Verify admin layout renders with sidebar navigation |
| Preconditions | Authenticated as admin |
| Steps | 1. Inject admin token 2. Navigate to `/admin` |
| Expected Results | Admin header visible with "Isnad Graph" title and "Admin Dashboard" label, sidebar shows User Management, System Health, Content Stats, Usage Analytics links |
| Priority | P0 -- Critical |

#### ADM-002: Admin -- Back to Main Site

| Field | Value |
|-------|-------|
| Description | Verify "Back to main site" link works |
| Preconditions | Authenticated as admin, on admin page |
| Steps | 1. Click "Back to main site" link in admin sidebar |
| Expected Results | Navigates to `/` (which redirects to `/narrators`) |
| Priority | P1 -- High |

#### ADM-003: User Management -- List Users

| Field | Value |
|-------|-------|
| Description | Verify user management page lists all users |
| Preconditions | Authenticated as admin, seed data with users |
| Steps | 1. Navigate to `/admin/users` |
| Expected Results | Table of users showing email, name, provider, role, admin status, suspended status |
| Priority | P0 -- Critical |

#### ADM-004: User Management -- Search Users

| Field | Value |
|-------|-------|
| Description | Verify searching users by name or email |
| Preconditions | Authenticated as admin |
| Steps | 1. Navigate to `/admin/users` 2. Enter search term 3. Submit |
| Expected Results | User list filters to matching entries |
| Priority | P1 -- High |

#### ADM-005: User Management -- Filter by Role

| Field | Value |
|-------|-------|
| Description | Verify filtering users by role |
| Preconditions | Authenticated as admin, seed data with varied roles |
| Steps | 1. Navigate to `/admin/users` 2. Select a role filter |
| Expected Results | Only users with the selected role are shown |
| Priority | P2 -- Medium |

#### ADM-006: User Management -- Update User Role

| Field | Value |
|-------|-------|
| Description | Verify an admin can change a user's role |
| Preconditions | Authenticated as admin |
| Steps | 1. Navigate to `/admin/users` 2. Click edit on a user 3. Change role 4. Save |
| Expected Results | PATCH request sent to `/api/v1/admin/users/{id}`, user role updated in list |
| Priority | P1 -- High |

#### ADM-007: User Management -- Suspend User

| Field | Value |
|-------|-------|
| Description | Verify an admin can suspend a user |
| Preconditions | Authenticated as admin |
| Steps | 1. Navigate to `/admin/users` 2. Toggle suspend on a user 3. Confirm |
| Expected Results | User marked as suspended, visual indicator updated |
| Priority | P1 -- High |

#### ADM-008: User Management -- Grant/Revoke Admin

| Field | Value |
|-------|-------|
| Description | Verify an admin can toggle another user's admin status |
| Preconditions | Authenticated as admin |
| Steps | 1. Navigate to `/admin/users` 2. Toggle admin status on a user 3. Confirm |
| Expected Results | PATCH request updates `is_admin`, UI reflects change |
| Priority | P1 -- High |

#### ADM-009: System Health Page

| Field | Value |
|-------|-------|
| Description | Verify system health page shows service status |
| Preconditions | Authenticated as admin |
| Steps | 1. Navigate to `/admin/health` |
| Expected Results | Page displays overall status, individual checks for Neo4j, PostgreSQL, Redis (green/red indicators) |
| Priority | P0 -- Critical |

#### ADM-010: Content Stats Page

| Field | Value |
|-------|-------|
| Description | Verify content statistics page shows counts |
| Preconditions | Authenticated as admin |
| Steps | 1. Navigate to `/admin/stats` |
| Expected Results | Page displays hadith count, narrator count, collection count, coverage percentage |
| Priority | P1 -- High |

#### ADM-011: Usage Analytics Page

| Field | Value |
|-------|-------|
| Description | Verify usage analytics page shows metrics |
| Preconditions | Authenticated as admin |
| Steps | 1. Navigate to `/admin/analytics` |
| Expected Results | Page displays search volume, API call count, popular narrators list |
| Priority | P1 -- High |

#### ADM-012: Moderation Page

| Field | Value |
|-------|-------|
| Description | Verify moderation page lists flagged content |
| Preconditions | Authenticated as admin, seed data with moderation items |
| Steps | 1. Navigate to `/admin/moderation` |
| Expected Results | List of moderation items with entity type, reason, status, timestamps |
| Priority | P1 -- High |

#### ADM-013: Moderation -- Update Item Status

| Field | Value |
|-------|-------|
| Description | Verify an admin can approve or reject a moderation item |
| Preconditions | Authenticated as admin, pending moderation item exists |
| Steps | 1. Navigate to `/admin/moderation` 2. Click approve/reject on a pending item 3. Optionally add notes |
| Expected Results | PATCH request sent, item status updated in list |
| Priority | P1 -- High |

#### ADM-014: Reports Page

| Field | Value |
|-------|-------|
| Description | Verify reports page shows system reports |
| Preconditions | Authenticated as admin |
| Steps | 1. Navigate to `/admin/reports` |
| Expected Results | Page displays pipeline metrics, disambiguation metrics, dedup metrics, graph validation, topic coverage |
| Priority | P1 -- High |

#### ADM-015: Config Page

| Field | Value |
|-------|-------|
| Description | Verify config page renders |
| Preconditions | Authenticated as admin |
| Steps | 1. Navigate to `/admin/config` |
| Expected Results | Configuration settings displayed |
| Priority | P2 -- Medium |

---

### 3.11 Error States and Edge Cases

#### ERR-001: API Unavailable -- Network Error

| Field | Value |
|-------|-------|
| Description | Verify graceful handling when the API is unreachable |
| Preconditions | Block API requests via Playwright route interception |
| Steps | 1. Intercept all `/api/v1/*` requests and abort them 2. Navigate to `/narrators` |
| Expected Results | Error message displayed (not a blank page or unhandled exception) |
| Priority | P1 -- High |

#### ERR-002: API Returns 500

| Field | Value |
|-------|-------|
| Description | Verify handling of server errors |
| Preconditions | Mock API to return 500 |
| Steps | 1. Intercept API calls, respond with 500 2. Navigate to `/narrators` |
| Expected Results | Error state shown with retry option or descriptive message |
| Priority | P1 -- High |

#### ERR-003: Detail Page -- Entity Not Found (404)

| Field | Value |
|-------|-------|
| Description | Verify handling when a detail page entity does not exist |
| Preconditions | None |
| Steps | 1. Navigate to `/narrators/nonexistent-id-12345` |
| Expected Results | "Not found" message or redirect, not an unhandled crash |
| Priority | P1 -- High |

#### ERR-004: Admin API Returns 401/403

| Field | Value |
|-------|-------|
| Description | Verify handling when admin API rejects credentials |
| Preconditions | Mock admin API to return 401 |
| Steps | 1. Inject expired admin token 2. Navigate to `/admin/users` |
| Expected Results | Error message displayed, not a blank page. Ideally redirects to login. |
| Priority | P1 -- High |

#### ERR-005: Empty Data State

| Field | Value |
|-------|-------|
| Description | Verify pages handle zero-result datasets gracefully |
| Preconditions | Mock API to return empty lists |
| Steps | 1. Navigate to `/narrators` with API returning `{ items: [], total: 0, page: 1, limit: 20 }` |
| Expected Results | "No narrators found" or equivalent empty-state message |
| Priority | P2 -- Medium |

#### ERR-006: Slow Network -- Loading States

| Field | Value |
|-------|-------|
| Description | Verify loading indicators appear during slow API responses |
| Preconditions | Delay API responses by 3+ seconds via route interception |
| Steps | 1. Navigate to `/narrators` with delayed API 2. Observe page during loading |
| Expected Results | Loading spinner or skeleton visible until data arrives |
| Priority | P2 -- Medium |

#### ERR-007: React Query Retry

| Field | Value |
|-------|-------|
| Description | Verify TanStack Query retries on transient failure |
| Preconditions | QueryClient configured with `retry: 1` |
| Steps | 1. Mock API to fail once, then succeed 2. Navigate to page |
| Expected Results | Data loads after retry without user intervention |
| Priority | P2 -- Medium |

#### ERR-008: Arabic Text Rendering

| Field | Value |
|-------|-------|
| Description | Verify Arabic text renders correctly with proper RTL direction |
| Preconditions | Seed data with Arabic content |
| Steps | 1. Navigate to a narrator or hadith detail page with Arabic text |
| Expected Results | Arabic text displays right-to-left, no garbled characters, diacritics visible |
| Priority | P1 -- High |

---

### 3.12 Accessibility

All accessibility tests use Playwright's built-in accessibility testing via
`@axe-core/playwright` or manual ARIA checks.

#### A11Y-001: Page Landmark Structure

| Field | Value |
|-------|-------|
| Description | Verify all pages have proper landmark regions |
| Preconditions | None |
| Steps | 1. For each page: run axe accessibility scan 2. Check for `<main>`, `<nav>`, `<header>` landmarks |
| Expected Results | Each page has at least `main`, `navigation`, and `banner` landmarks |
| Priority | P1 -- High |

#### A11Y-002: Keyboard Navigation -- Sidebar

| Field | Value |
|-------|-------|
| Description | Verify sidebar can be navigated entirely via keyboard |
| Preconditions | None |
| Steps | 1. Navigate to `/` 2. Tab through sidebar links 3. Press Enter to activate a link |
| Expected Results | Focus moves through all sidebar links in order, Enter activates navigation |
| Priority | P1 -- High |

#### A11Y-003: Keyboard Navigation -- Tables

| Field | Value |
|-------|-------|
| Description | Verify data tables are keyboard-accessible |
| Preconditions | Seed data |
| Steps | 1. Navigate to `/narrators` 2. Tab into the table 3. Navigate rows |
| Expected Results | Focus is visible, rows can be selected/activated via keyboard |
| Priority | P1 -- High |

#### A11Y-004: Color Contrast

| Field | Value |
|-------|-------|
| Description | Verify text meets WCAG 2.1 AA contrast ratio (4.5:1 for normal text) |
| Preconditions | None |
| Steps | 1. Run axe scan on each major page |
| Expected Results | No contrast violations at AA level |
| Priority | P2 -- Medium |

#### A11Y-005: Form Labels -- Search

| Field | Value |
|-------|-------|
| Description | Verify search inputs have associated labels or aria-label |
| Preconditions | None |
| Steps | 1. Navigate to `/search` 2. Inspect search input for label association |
| Expected Results | Input has an associated `<label>` element or `aria-label` attribute |
| Priority | P1 -- High |

#### A11Y-006: Admin Form Labels

| Field | Value |
|-------|-------|
| Description | Verify admin panel form controls have accessible labels |
| Preconditions | Authenticated as admin |
| Steps | 1. Navigate to `/admin/users` 2. Open edit dialog 3. Check form field labels |
| Expected Results | All form controls have associated labels |
| Priority | P1 -- High |

#### A11Y-007: Focus Management After Navigation

| Field | Value |
|-------|-------|
| Description | Verify focus is managed properly after client-side navigation |
| Preconditions | None |
| Steps | 1. Navigate from `/narrators` to `/hadiths` via sidebar 2. Check focus position |
| Expected Results | Focus moves to the main content area or page heading after navigation |
| Priority | P2 -- Medium |

#### A11Y-008: Screen Reader -- Graph Explorer

| Field | Value |
|-------|-------|
| Description | Verify graph explorer provides accessible alternatives for visual graph |
| Preconditions | Seed data |
| Steps | 1. Navigate to `/graph` 2. Check for aria labels, role attributes on graph container 3. Check for text-based alternative (e.g., teacher/student count summary) |
| Expected Results | Graph container has `role="img"` or equivalent with `aria-label`, summary data available as text |
| Priority | P2 -- Medium |

---

## 4. CI Integration Plan

### GitHub Actions Workflow

E2E tests will run in a dedicated GitHub Actions workflow triggered on:

- Pull requests targeting `main` or `deployments/*` branches
- Nightly schedule (to catch regressions from upstream API changes)

### Workflow Steps

```yaml
name: E2E Tests
on:
  pull_request:
    branches: [main, 'deployments/**']
  schedule:
    - cron: '0 3 * * *'  # Daily at 03:00 UTC

jobs:
  e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    services:
      neo4j:
        image: neo4j:5-community
        ports: ['7687:7687']
        env:
          NEO4J_AUTH: neo4j/testpassword
      postgres:
        image: pgvector/pgvector:pg16
        ports: ['5432:5432']
        env:
          POSTGRES_DB: isnad_test
          POSTGRES_PASSWORD: testpassword
      redis:
        image: redis:7-alpine
        ports: ['6379:6379']

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install dependencies
        run: make setup

      - name: Install Playwright
        run: uv run playwright install --with-deps chromium

      - name: Seed test data
        run: uv run python scripts/seed_e2e_data.py

      - name: Start API server
        run: uv run uvicorn src.api.app:app --port 8000 &

      - name: Build and serve frontend
        run: |
          cd frontend && npm ci && npm run build
          npx serve -s dist -l 3000 &

      - name: Run E2E tests
        run: uv run pytest tests/e2e/ -m e2e --browser chromium
        env:
          E2E_BASE_URL: http://localhost:3000
          E2E_API_URL: http://localhost:8000

      - name: Upload test artifacts
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-traces
          path: test-results/
```

### Artifact Collection

On failure, Playwright traces and screenshots are uploaded as build artifacts for
debugging. Configure in `pytest.ini` or `conftest.py`:

```python
@pytest.fixture(scope="session")
def browser_context_args():
    return {
        "viewport": {"width": 1280, "height": 720},
        "record_video_dir": "test-results/videos",
    }
```

### Parallelism

Tests are organized into independent classes (Auth, Nav, Admin, etc.) that can run
in parallel using `pytest-xdist`:

```bash
uv run pytest tests/e2e/ -m e2e -n 4
```

### Flaky Test Handling

The existing `conftest.py` already applies `pytest.mark.flaky(reruns=2, reruns_delay=1)`
to all E2E tests. This should remain to handle transient network/rendering timing issues.

---

## 5. Priority Matrix

| Priority | Count | Description |
|----------|-------|-------------|
| P0 -- Critical | 15 | Must pass before any release. Blocks deployment. |
| P1 -- High | 26 | Should pass. Regressions here are bugs. |
| P2 -- Medium | 13 | Nice to have. Can defer if timeline is tight. |

### P0 Tests (must implement first)

- AUTH-001, AUTH-002, AUTH-003, AUTH-006, AUTH-008
- NAV-001, NAV-002, NAV-004, NAV-005, NAV-006
- NAR-001, NAR-004
- HAD-001, COL-001, SRC-001, SRC-002, TML-001, CMP-001, GRX-001
- ADM-001, ADM-003, ADM-009

### Implementation Order

1. **Wave 1:** Smoke tests extension (already partially done), auth flows (AUTH-*)
2. **Wave 2:** Navigation and routing (NAV-*), error states (ERR-*)
3. **Wave 3:** Data pages -- narrators, hadiths, collections, search (NAR-*, HAD-*, COL-*, SRC-*)
4. **Wave 4:** Advanced pages -- timeline, compare, graph (TML-*, CMP-*, GRX-*)
5. **Wave 5:** Admin panel (ADM-*)
6. **Wave 6:** Accessibility (A11Y-*)
