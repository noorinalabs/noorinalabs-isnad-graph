/**
 * Pure pagination arithmetic for the search results page (ig#1147).
 *
 * The results page shows `resultsPerPage` (10) hits per display page but fetches
 * a larger server-side batch (`batchSize`: 50 semantic / 100 full-text) so the
 * client-side facet/sort operate over a meaningful window. A display page beyond
 * the first batch maps to a LATER server page rather than hard-capping at the
 * batch — that batch cap was the flat "5 pages of 10" (50-result) ceiling this
 * fixes.
 *
 * These helpers are extracted verbatim from the previously inline SearchPage
 * arithmetic (behaviour-preserving) so the batch<->page mapping — the exact spot
 * where an off-by-one silently re-caps or skips a whole batch with nothing
 * catching it — is unit-testable in isolation (Marisol, PR #1149 review).
 */

/** Display pages contained in one server batch (>= 1). */
export function pagesPerBatch(batchSize: number, resultsPerPage: number): number {
  return Math.max(1, Math.floor(batchSize / resultsPerPage))
}

/** 1-based server page to fetch for a given 1-based display page. */
export function serverPageFor(
  displayPage: number,
  batchSize: number,
  resultsPerPage: number,
): number {
  return Math.floor((displayPage - 1) / pagesPerBatch(batchSize, resultsPerPage)) + 1
}

/** 1-based page WITHIN the fetched batch for a given 1-based display page. */
export function localPageFor(
  displayPage: number,
  batchSize: number,
  resultsPerPage: number,
): number {
  return ((displayPage - 1) % pagesPerBatch(batchSize, resultsPerPage)) + 1
}

/**
 * Total display pages from the SERVER total (not the fetched batch length), so
 * the pager offers exactly the pages the corpus supports and stops there — no
 * phantom empty page past the real total. Capped at `maxDisplayPages` so a deep
 * next-click never requests a server page beyond the backend's MAX_SEARCH_PAGE.
 */
export function pageCountFromTotal(
  total: number,
  resultsPerPage: number,
  maxDisplayPages: number,
): number {
  return Math.min(maxDisplayPages, Math.ceil(total / resultsPerPage))
}
