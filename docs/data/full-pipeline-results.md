# Full Pipeline Run Results (Phase 1-2) — Wave 3 Re-run

**Date:** 2026-03-30
**Issue:** #544 (pipeline bug fixes and tuning)
**Runner:** Elena Petrova
**Branch base:** `deployments/phase12/cleanup`
**Bug fixes verified:** #570, #571, #572, #573, #574

## Pipeline Overview

Phases 1-2 (acquire, parse, validate-staging, resolve) were re-run after Wave 2 bug fixes.
Phase 3 (Neo4j load) and Phase 4 (enrich) were not run (require infrastructure).

## Comparison with Wave 1 Results

| Area | Wave 1 | Wave 3 | Change |
|------|--------|--------|--------|
| Acquire: fawaz | FAILED (upstream CDN) | SUCCESS (20 ara + 10 eng files) | Fixed (#570) |
| Parse: fawaz | 0 rows | 0 rows | **Still broken** (see below) |
| Parse: muhaddithat | FAILED (column mismatch) | SUCCESS (113 bios, 330 edges) | Fixed (#571) |
| Parse: open_hadith | 124,320 rows | 62,160 rows | Improved (dedup, #574) |
| Validate: crash on null columns | TypeError crash | No crash | Fixed |
| Resolve: disambiguate path | Looked in staging, NER wrote to curated | Reads from curated | Fixed (#572) |
| Resolve: disambiguate completion | 0 narrators (path bug) | OOM/timeout (killed after ~60min) | Path fixed, but perf issue |
| Resolve: dedup deps | Missing sentence-transformers | Installed (#573) | Fixed (not tested — dedup runs after disambiguate) |
| Staging files | 13 | 15 | +2 new muhaddithat files |
| Total staging rows | 3,833,232 | 3,771,515 | -61,717 (open_hadith dedup) |

## Phase 1: Acquire

| Source | Status | Details |
|--------|--------|---------|
| lk (LK Hadith Corpus) | SUCCESS | 335 files, git clone |
| sanadset | SUCCESS | Mendeley download, 3 files |
| thaqalayn | SUCCESS | 67 files, git clone |
| fawaz | SUCCESS | 20 Arabic + 10 English + editions.json + info.json (32 files) |
| sunnah (API) | SKIPPED | `SUNNAH_API_KEY` not set |
| sunnah_scraped | SUCCESS | 5 collections, 10,028 hadiths |
| open_hadith | SUCCESS | 18 files |
| muhaddithat | SUCCESS | 2 files |

**Result:** 7/8 sources acquired successfully. 1 skipped (sunnah API — no key).

**Improvement over Wave 1:** Fawaz acquire now works (fix #570 — CDN URL update).

## Phase 1: Parse

| Staging File | Source | Rows | Size |
|-------------|--------|------|------|
| hadiths_sanadset.parquet | sanadset | 650,986 | 489 MB |
| hadiths_thaqalayn.parquet | thaqalayn | 113,401 | 84 MB |
| narrator_mentions_sanadset.parquet | sanadset | 2,789,517 | 61 MB |
| hadiths_lk.parquet | lk | 34,088 | 36 MB |
| hadiths_sunnah_scraped.parquet | sunnah_scraped | 10,028 | 9.1 MB |
| narrator_mentions_lk.parquet | lk | 86,162 | 5.3 MB |
| narrators_bio_kaggle.parquet | kaggle | 24,326 | 1.7 MB |
| hadiths_open_hadith.parquet | open_hadith | 62,160 | 738 KB |
| narrators_bio_muhaddithat.parquet | muhaddithat | 113 | 9.5 KB |
| network_edges_muhaddithat.parquet | muhaddithat | 330 | 7.8 KB |
| collections_thaqalayn.parquet | thaqalayn | 64 | 3.8 KB |
| collections_lk.parquet | lk | 335 | 3.8 KB |
| hadiths_fawaz.parquet | fawaz | 0 | 2.7 KB |
| collections_sunnah_scraped.parquet | sunnah_scraped | 5 | 2.3 KB |
| collections_fawaz.parquet | fawaz | 0 | 1.5 KB |

**Totals:** 15 staging files, 3,771,515 rows

### Parse Improvements (Wave 3)

- **muhaddithat** (fix #571): Now produces 2 new files — `narrators_bio_muhaddithat.parquet` (113 female narrator bios) and `network_edges_muhaddithat.parquet` (330 transmission edges, avg chain length 4.4, 100% bio match rate).
- **open_hadith** (fix #574): Row count decreased from 124,320 to 62,160, suggesting deduplication improvements. However, all text columns remain 100% null — this source provides metadata only.

### Remaining Parse Issues

- **fawaz**: Acquire now succeeds (32 files downloaded), but the parser produces 0 rows. Root cause: `editions.json` uses collection-level keys (e.g., `bukhari`, `abudawud`) but the parser's `run()` function filters for keys starting with `eng-` (line 166: `eng_keys = sorted(k for k in editions_data if k.startswith("eng-"))`). The individual edition files (`eng-bukhari.json`, `ara-bukhari.json`) exist and contain valid data, but the enumeration logic doesn't find them. **New bug — needs a follow-up fix.**

## Staging Validation

Overall: **FAILED** (2 empty fawaz files)

| File | Status | Issues |
|------|--------|--------|
| collections_fawaz.parquet | FAIL | Empty file (0 rows) |
| collections_lk.parquet | PASS | 329 duplicate collection_id (98.2%) |
| collections_sunnah_scraped.parquet | PASS | Clean |
| collections_thaqalayn.parquet | PASS | Row count drift +1180% vs baseline |
| hadiths_fawaz.parquet | FAIL | Empty file (0 rows) |
| hadiths_lk.parquet | PASS | 107 duplicate source_id (0.3%) |
| hadiths_open_hadith.parquet | PASS | 100% empty matn_ar/matn_en |
| hadiths_sanadset.parquet | PASS | 100% duplicate source_id, row drift +6410% |
| hadiths_sunnah_scraped.parquet | PASS | 9,852 duplicate source_id (98.2%), row drift -75% |
| hadiths_thaqalayn.parquet | PASS | 100% empty matn_ar, row drift +656% |
| narrator_mentions_lk.parquet | PASS | 236 duplicate mention_id (0.3%) |
| narrator_mentions_sanadset.parquet | PASS | 2,789,372 duplicate mention_id (99.99%) |
| narrators_bio_kaggle.parquet | PASS | Clean |
| narrators_bio_muhaddithat.parquet | PASS | 0% Arabic chars in name_ar (names stored in transliteration) |
| network_edges_muhaddithat.parquet | PASS | Clean |

**Improvement over Wave 1:** Validation no longer crashes on all-null columns (the `pc.sum()` fix from Wave 1 holds). Two new muhaddithat files both pass validation.

## Phase 2: Resolve

### NER (Named Entity Recognition)

| Source | Mentions | Notes |
|--------|----------|-------|
| sanadset | 2,789,517 | Pre-extracted from staging |
| thaqalayn | 405,360 | Extracted from Arabic isnads, 3.57 mentions/hadith |
| lk | 86,162 | Pre-extracted from staging |
| sunnah_scraped | 15,116 | Extracted from English isnads, 1.51 mentions/hadith |
| open_hadith | 0 | 100% null isnads — no extraction possible |
| fawaz | 0 | Parser produced 0 hadiths (parse bug) |
| muhaddithat | 0 | Skipped (no raw isnads — transmission data in network_edges) |

**Total NER mentions:** 3,296,155 (unchanged from Wave 1)
**Output:** `data/curated/narrator_mentions_resolved.parquet` (247 MB, 3.3M rows)

### Disambiguation

- Loaded 24,439 biographical candidates from 2 bio files (kaggle: 24,326 + muhaddithat: 113)
- Successfully loaded 3,296,155 mentions from `data/curated/narrator_mentions_resolved.parquet` (fix #572 confirmed — path mismatch resolved)
- **Result:** Process killed after ~60 minutes of CPU-intensive matching (93% CPU, 3.3GB RAM)
- **No output files produced** — disambiguation did not complete

**Improvement over Wave 1:** The path mismatch bug (#572) is fixed — disambiguate now correctly reads from `data/curated/` instead of `data/staging/`. However, the computation itself is too expensive for this environment (3.3M mentions x 24K candidates).

### Dedup (Hadith Parallel Detection)

- Not reached — the dedup step runs after disambiguate, which did not complete
- `sentence-transformers` dependency is now installed (fix #573)

### Resolve Summary

| Metric | Wave 1 | Wave 3 |
|--------|--------|--------|
| NER mentions extracted | 3,296,155 | 3,296,155 |
| Bio candidates | 24,326 | 24,439 (+113 muhaddithat) |
| Canonical narrators | 0 (path bug) | 0 (OOM/timeout) |
| Ambiguous mentions | 0 | 0 |
| Parallel links | 0 (missing deps) | 0 (not reached) |

## Outstanding Issues

### Bugs

1. **Fawaz parser enumeration** (NEW): `editions.json` uses collection-level keys (`bukhari`) but parser filters for `eng-` prefixed keys. Acquire works, parse produces 0 rows. Needs parser update to enumerate edition files from the directory or from the nested `collection` arrays in `editions.json`.

### Performance

2. **Disambiguate timeout**: Processing 3.3M mentions against 24K candidates exceeds available compute. Needs optimization:
   - Batch processing with progress logging
   - Pre-filter mentions by name similarity (blocking/indexing)
   - Consider approximate matching (e.g., locality-sensitive hashing)
   - Add memory-efficient streaming instead of loading all mentions at once

### Data Quality

3. **Open Hadith empty text**: 62,160 hadiths have 100% null text fields — metadata-only.
4. **Muhaddithat transliterated names**: `narrators_bio_muhaddithat.parquet` has 0% Arabic characters in `name_ar` — names are stored as transliterations, not Arabic script.
5. **High duplicate rates**: sanadset (100% duplicate source_id), sunnah_scraped (98%), collections_lk (98%). These are cross-chapter duplicates from source data structure.
6. **Baseline drift**: Multiple files exceed 30% drift tolerance. Baselines need recalibration to reflect actual dataset sizes.

## Recommendations

1. **Fix fawaz parser** — update enumeration to scan directory for `eng-*.json` / `ara-*.json` files instead of relying on `editions.json` keys.
2. **Optimize disambiguate** — add blocking/indexing to reduce comparison space; add progress logging; consider chunked processing.
3. **Recalibrate validation baselines** — current baselines were set from early test runs with much smaller datasets.
4. **Test dedup independently** — sentence-transformers is installed but dedup was never reached. Run it separately to verify #573 fix.
