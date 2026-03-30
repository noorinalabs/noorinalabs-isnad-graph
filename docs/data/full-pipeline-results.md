# Full Pipeline Run Results (Phase 1-2)

**Date:** 2026-03-30
**Issue:** #535
**Runner:** Elena Petrova
**Branch base:** `deployments/phase12/wave-1`

## Pipeline Overview

Phases 1-2 (acquire, parse, resolve) were executed locally. Phase 3 (Neo4j load) requires
infrastructure and was not run. The dedup step of resolve was skipped due to missing
`sentence-transformers` dependency in the local environment.

## Phase 1: Acquire

| Source | Status | Details |
|--------|--------|---------|
| lk (LK Hadith Corpus) | SUCCESS | 335 files, 117 MB (git clone) |
| sanadset | SUCCESS | Mendeley download, 1.4 GB |
| thaqalayn | SUCCESS | 67 files, 388 MB |
| fawaz | FAILED | `Expected >=10 English edition files, found 0` — upstream repo structure may have changed |
| sunnah (API) | SKIPPED | `SUNNAH_API_KEY` not set |
| sunnah_scraped | SUCCESS | 5 collections, 10,028 hadiths, 14 MB |
| open_hadith | SUCCESS | 18 files, 255 MB |
| muhaddithat | SUCCESS | 2 files, 292 KB |

**Result:** 6/8 sources acquired successfully. 1 failed (fawaz — upstream issue), 1 skipped (sunnah API — no key).

Total raw data size: ~2.2 GB

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
| hadiths_open_hadith.parquet | open_hadith | 124,320 | 1.2 MB |
| collections_thaqalayn.parquet | thaqalayn | 64 | 3.8 KB |
| collections_lk.parquet | lk | 335 | 3.8 KB |
| hadiths_fawaz.parquet | fawaz | 0 | 2.7 KB |
| collections_sunnah_scraped.parquet | sunnah_scraped | 5 | 2.3 KB |
| collections_fawaz.parquet | fawaz | 0 | 1.5 KB |

**Totals:** 13 staging files, 3,833,232 rows

### Parse Failures

- **muhaddithat**: Parser expects columns `(id, name)` but raw data has `(id, displayname, fullname, searchname, arabicname, ...)`. Needs parser update to map `displayname`/`fullname` to `name`.
- **fawaz**: Empty output (0 rows) — acquire failed upstream.

## Staging Validation

Overall: **FAILED** (2 empty fawaz files caused hard failures; all other files passed)

### Key Findings

| File | Status | Issues |
|------|--------|--------|
| collections_fawaz.parquet | FAIL | Empty file (0 rows) |
| hadiths_fawaz.parquet | FAIL | Empty file (0 rows) |
| collections_lk.parquet | PASS | 329 duplicate collection_id values (98.2%) |
| collections_sunnah_scraped.parquet | PASS | Clean |
| collections_thaqalayn.parquet | PASS | Row count drift +1180% vs baseline (64 vs 5) |
| hadiths_lk.parquet | PASS | 107 duplicate source_id (0.3%), minor null rates |
| hadiths_open_hadith.parquet | PASS | 100% empty matn_ar/matn_en — data stored in full_text columns only |
| hadiths_sanadset.parquet | PASS | 100% duplicate source_id, 99.99% Arabic coverage |
| hadiths_sunnah_scraped.parquet | PASS | 9,852 duplicate source_id (98.2%) |
| hadiths_thaqalayn.parquet | PASS | 100% empty matn_ar — text in full_text_ar only |
| narrator_mentions_lk.parquet | PASS | 55.4% null name_ar, 44.6% null name_en |
| narrator_mentions_sanadset.parquet | PASS | 100% null name_en, 99.1% null transmission_method |
| narrators_bio_kaggle.parquet | PASS | Clean |

### Validation Bug Fix

The `validate-staging` command crashed with `TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'` in `_hadith_checks()` when `pc.sum()` returned `None` for columns with all-null values. Fixed by adding `or 0` fallback for `blank_count` in both `empty_matn_ar` and `empty_matn_en` checks (`src/parse/validate.py:427,444`).

## Phase 2: Resolve

### NER (Named Entity Recognition)

| Source | Mentions | Notes |
|--------|----------|-------|
| sanadset | 2,789,517 | Pre-extracted from staging |
| thaqalayn | 405,360 | Extracted from Arabic isnads, 3.57 mentions/hadith |
| lk | 86,162 | Pre-extracted from staging |
| sunnah_scraped | 15,116 | Extracted from English isnads, 1.51 mentions/hadith |
| open_hadith | 0 | 100% null isnads — no extraction possible |
| fawaz | 0 | No data |
| muhaddithat | 0 | Skipped (no raw isnads) |

**Total NER mentions:** 3,296,155
**Output:** `data/curated/narrator_mentions_resolved.parquet` (247 MB, 3.3M rows)

### Disambiguation

- Loaded 24,326 biographical candidates from narrators_bio_kaggle
- Could not find mentions file at `data/staging/narrator_mentions_resolved.parquet` — the NER step writes to `data/curated/`, but disambiguate looks in `data/staging/`
- **Result:** 0 canonical narrators resolved (path mismatch bug)

### Dedup (Hadith Parallel Detection)

- Loaded 157,264 hadiths for comparison (775,559 skipped — missing text)
- **Skipped:** `sentence-transformers` or `numpy` not installed in environment
- **Result:** 0 parallel links detected (empty output)

### Summary

| Metric | Value |
|--------|-------|
| NER mentions extracted | 3,296,155 |
| Canonical narrators | 0 (disambiguate path bug) |
| Ambiguous mentions | 0 |
| Parallel links | 0 (dedup deps missing) |
| Output files | 3 |

## Issues Found

### Bugs

1. **validate-staging crash** — `pc.sum().as_py()` returns `None` for all-null columns, causing `TypeError` in arithmetic. **Fixed** in this PR.
2. **Disambiguate path mismatch** — NER writes `narrator_mentions_resolved.parquet` to `data/curated/` but disambiguate looks for it in `data/staging/`. Needs alignment.

### Data Quality Concerns

3. **Fawaz acquire failure** — upstream repo may have restructured; English edition file discovery logic needs update.
4. **Muhaddithat parse failure** — column name mismatch (`displayname`/`fullname` vs expected `name`).
5. **Open Hadith missing text** — 124,320 hadiths have 100% null `matn_ar`/`matn_en`/`full_text_ar`/`full_text_en`; data appears to be metadata-only.
6. **High duplicate rates** — sanadset (100% duplicate source_id), sunnah_scraped (98%), thaqalayn (99.95%). These are likely cross-chapter duplicates from the source data structure.
7. **Baseline drift** — several files exceed 30% drift tolerance vs baselines (sanadset: +6410%, thaqalayn hadiths: +656%, collections_thaqalayn: +1180%). Baselines need recalibration.

### Missing Dependencies

8. **sentence-transformers** not in project deps — needed for dedup step.

## Recommendations for Phase 3 (Load into Neo4j)

1. **Fix disambiguate path** so it reads from `data/curated/` where NER actually writes.
2. **Add `sentence-transformers`** to project dependencies for dedup.
3. **Fix fawaz downloader** to handle current upstream repo structure.
4. **Fix muhaddithat parser** to accept actual column names from source data.
5. **Recalibrate validation baselines** — current baselines were set from early test runs with much smaller datasets.
6. **Deduplicate source_ids** before loading into Neo4j — decide on merge strategy for cross-chapter hadith duplicates.
7. **Investigate open_hadith text extraction** — 124K hadiths are currently metadata-only shells.
8. **Load order:** narrators_bio_kaggle (24K biographical nodes) first, then hadiths (932K across sources), then narrator_mentions_resolved (3.3M mention edges).
9. **Expected graph size estimate:**
   - NARRATOR nodes: ~24,326 (from bio data, plus disambiguation candidates)
   - HADITH nodes: ~932,823 (sum of non-empty hadith files)
   - COLLECTION nodes: ~404 (lk: 335, thaqalayn: 64, sunnah: 5)
   - Narrator mention edges: ~3,296,155
