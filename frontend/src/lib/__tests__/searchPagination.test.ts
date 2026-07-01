import { describe, it, expect } from 'vitest'
import {
  pagesPerBatch,
  serverPageFor,
  localPageFor,
  pageCountFromTotal,
} from '../searchPagination'

// Mirror the SearchPage constants so the tests exercise the exact production
// mapping (batch sizes = the two SEARCH_MAX_LIMIT values, 10 per display page).
const RESULTS_PER_PAGE = 10
const SEMANTIC_BATCH = 50 // SEMANTIC_SEARCH_MAX_LIMIT
const FULLTEXT_BATCH = 100 // SEARCH_MAX_LIMIT
const MAX_DISPLAY_PAGES = 1000

describe('searchPagination batch mapping (ig#1147, Marisol #1)', () => {
  it('semantic: 5 display pages per 50-result batch', () => {
    expect(pagesPerBatch(SEMANTIC_BATCH, RESULTS_PER_PAGE)).toBe(5)
  })

  it('full-text: 10 display pages per 100-result batch', () => {
    expect(pagesPerBatch(FULLTEXT_BATCH, RESULTS_PER_PAGE)).toBe(10)
  })

  it('semantic: display page 6 crosses into server page 2 (results 51-60)', () => {
    // This is the exact regression: the old flat cap stopped at 5 pages of 10.
    expect(serverPageFor(6, SEMANTIC_BATCH, RESULTS_PER_PAGE)).toBe(2)
    expect(localPageFor(6, SEMANTIC_BATCH, RESULTS_PER_PAGE)).toBe(1)
  })

  it('semantic: the last page of batch 1 stays in server page 1', () => {
    expect(serverPageFor(5, SEMANTIC_BATCH, RESULTS_PER_PAGE)).toBe(1)
    expect(localPageFor(5, SEMANTIC_BATCH, RESULTS_PER_PAGE)).toBe(5)
  })

  it('full-text: page 11 is the off-by-one boundary -> server page 2, local page 1', () => {
    expect(serverPageFor(11, FULLTEXT_BATCH, RESULTS_PER_PAGE)).toBe(2)
    expect(localPageFor(11, FULLTEXT_BATCH, RESULTS_PER_PAGE)).toBe(1)
  })

  it('full-text: page 10 is the last page of batch 1 (local page 10)', () => {
    expect(serverPageFor(10, FULLTEXT_BATCH, RESULTS_PER_PAGE)).toBe(1)
    expect(localPageFor(10, FULLTEXT_BATCH, RESULTS_PER_PAGE)).toBe(10)
  })

  it('every display page maps back to a contiguous global result window', () => {
    // Guards against an off-by-one that would re-cap or skip a whole batch:
    // reconstructing (serverPage-1)*batch + (localPage-1)*rpp must equal the
    // global 0-based offset of the display page for BOTH batch sizes.
    for (const batch of [SEMANTIC_BATCH, FULLTEXT_BATCH]) {
      for (let displayPage = 1; displayPage <= 40; displayPage++) {
        const sp = serverPageFor(displayPage, batch, RESULTS_PER_PAGE)
        const lp = localPageFor(displayPage, batch, RESULTS_PER_PAGE)
        const reconstructed = (sp - 1) * batch + (lp - 1) * RESULTS_PER_PAGE
        expect(reconstructed).toBe((displayPage - 1) * RESULTS_PER_PAGE)
      }
    }
  })
})

describe('searchPagination pager stops at server total (ig#1147, Marisol #2)', () => {
  it('a partial final page counts as a page but adds no phantom page past it', () => {
    // 55 matches at 10/page => 6 pages (page 6 holds results 51-55). NOT 7.
    expect(pageCountFromTotal(55, RESULTS_PER_PAGE, MAX_DISPLAY_PAGES)).toBe(6)
  })

  it('an exact multiple of the page size yields no trailing empty page', () => {
    expect(pageCountFromTotal(50, RESULTS_PER_PAGE, MAX_DISPLAY_PAGES)).toBe(5)
    expect(pageCountFromTotal(51, RESULTS_PER_PAGE, MAX_DISPLAY_PAGES)).toBe(6)
  })

  it('zero matches yields zero pages (pager hidden, no empty page 1)', () => {
    expect(pageCountFromTotal(0, RESULTS_PER_PAGE, MAX_DISPLAY_PAGES)).toBe(0)
  })

  it('page count is driven by the server total, not the fetched batch size', () => {
    // total far exceeds a single 100-result batch -> many pages are reachable.
    expect(pageCountFromTotal(1234, RESULTS_PER_PAGE, MAX_DISPLAY_PAGES)).toBe(124)
  })

  it('is capped at MAX_DISPLAY_PAGES so deep next-clicks stay within backend bounds', () => {
    expect(pageCountFromTotal(10_000_000, RESULTS_PER_PAGE, MAX_DISPLAY_PAGES)).toBe(
      MAX_DISPLAY_PAGES,
    )
  })
})
