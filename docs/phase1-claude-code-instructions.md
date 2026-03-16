# Phase 1: Data Acquisition & Parsing — Claude Code Instruction Set

> **Status (2026-03-15):** Phase 1 is complete. All 7 data sources are acquired and parsed into staging Parquet files.

## PROJECT CONTEXT

You are continuing work on `isnad-graph`, a computational hadith analysis platform. Phase 0 is complete: the repository scaffold, Pydantic models, Docker infrastructure, Arabic utilities, and database clients are all in place.

Phase 1 has two objectives:
1. **Acquire** — Download all 7 data sources into `data/raw/`.
2. **Parse** — Transform raw files into normalized Parquet staging tables in `data/staging/` conforming to the Pydantic models defined in `src/models/`.

After Phase 1, every hadith, narrator mention, and collection record from every source should exist as a validated, schema-conformant Parquet file ready for entity resolution in Phase 2.

Read the existing codebase before making changes. Understand the Pydantic models in `src/models/`, the enums in `src/models/enums.py`, the Arabic utilities in `src/utils/arabic.py`, and the config in `src/config.py`. Your new code must use these existing types — do not redefine them.

---

## STEP 1: New Dependencies

Add these to `pyproject.toml` core dependencies (they should not already be present from Phase 0):

```
kaggle >= 1.6
beautifulsoup4 >= 4.12
lxml >= 5.1
tqdm >= 4.66
tenacity >= 8.2
```

Run `uv sync` after updating.

---

## STEP 2: Shared Acquisition Utilities (src/acquire/base.py)

Create a base module with reusable download helpers:

```python
"""Shared utilities for data acquisition."""

import hashlib
from pathlib import Path
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from src.utils.logging import get_logger

logger = get_logger(__name__)


def ensure_dir(path: Path) -> Path:
    """Create directory if it doesn't exist, return the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
def download_file(url: str, dest: Path, *, overwrite: bool = False) -> Path:
    """Download a file from URL to dest path. Retry on failure.
    Skip if file exists and overwrite=False. Log progress."""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
def fetch_json(url: str, *, headers: dict | None = None, timeout: float = 30.0) -> dict | list:
    """Fetch JSON from URL with retry logic. Return parsed JSON."""


def fetch_json_paginated(
    base_url: str,
    *,
    headers: dict | None = None,
    page_param: str = "page",
    limit_param: str = "limit",
    limit: int = 50,
    max_pages: int = 1000,
    data_key: str = "data",
    total_key: str = "total",
) -> list[dict]:
    """Fetch all pages from a paginated JSON API. Return concatenated results list.
    Stop when: accumulated results >= total, or empty page returned, or max_pages reached.
    Log progress every 10 pages."""


def clone_repo(repo_url: str, dest: Path, *, shallow: bool = True, overwrite: bool = False) -> Path:
    """Clone a git repository. Use --depth 1 if shallow=True. Skip if dest exists and overwrite=False."""


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hash of a file for integrity verification."""


def write_manifest(dest_dir: Path, files: list[Path]) -> Path:
    """Write a manifest.json listing all acquired files with their sizes and SHA-256 hashes.
    Useful for verifying data integrity between runs."""
```

All functions must be fully implemented. The `download_file` function should use `httpx` with streaming for large files and log download progress via `tqdm` or simple byte-count logging. Set a default timeout of 60 seconds for large file downloads.

---

## STEP 3: Individual Downloaders

Each downloader is a module in `src/acquire/` with a `def run(raw_dir: Path) -> Path` entry point that downloads its source into a subdirectory of `raw_dir` and returns the path to that subdirectory. Each must be idempotent — skip downloads if files already exist (check by existence + non-zero size).

### src/acquire/lk_corpus.py

**Source:** `https://github.com/ShathaTm/LK-Hadith-Corpus`
**Method:** Shallow git clone.
**Output directory:** `data/raw/lk/`
**Expected contents:** One CSV per book (Bukhari, Muslim, AbuDawud, Tirmidhi, Nasai, IbnMajah), plus starter.py and README.
**Post-download validation:** Assert at least 6 CSV files exist. Log file count and total size.

```python
def run(raw_dir: Path) -> Path:
    dest = ensure_dir(raw_dir / "lk")
    clone_repo("https://github.com/ShathaTm/LK-Hadith-Corpus.git", dest)
    csv_files = list(dest.rglob("*.csv"))
    assert len(csv_files) >= 6, f"Expected ≥6 CSVs, found {len(csv_files)}"
    logger.info("LK corpus acquired", file_count=len(csv_files))
    write_manifest(dest, csv_files)
    return dest
```

### src/acquire/sanadset.py

**Source:** Kaggle dataset `fahd09/hadith-dataset`
**Method:** Kaggle CLI via `subprocess` — `kaggle datasets download -d fahd09/hadith-dataset -p {dest} --unzip`
**Output directory:** `data/raw/sanadset/`
**Prerequisite:** `KAGGLE_USERNAME` and `KAGGLE_KEY` must be set in env (or `~/.kaggle/kaggle.json` must exist). Check for this and raise a clear error if missing.
**Post-download validation:** Assert CSV files exist and total row count exceeds 600,000.

Also download the narrators dataset in the same module:
`kaggle datasets download -d fahd09/hadith-narrators -p {dest}/narrators --unzip`

### src/acquire/thaqalayn.py

**Source:** ThaqalaynAPI — `https://www.thaqalayn-api.net/api/v2/allbooks` for book list, then per-book hadith fetches.
**Method:** REST API. No auth required.
**Output directory:** `data/raw/thaqalayn/`
**Strategy:**
1. Fetch `allbooks` endpoint → save as `allbooks.json`.
2. For each book, fetch all hadiths: `https://www.thaqalayn-api.net/api/v2/hadith/{bookId}` (paginated or full).
3. Save each book's hadiths as `book_{bookId}.json`.
4. Rate limit: 500ms delay between requests. Use `tenacity` retry on HTTP errors.
**Post-download validation:** Assert ≥15 book JSON files. Log total hadith count across all files.

**Important:** The ThaqalaynAPI may return hadiths in a single response per book (no pagination). Inspect the response structure on the first fetch and adapt accordingly. If the endpoint supports a range parameter, use it. Otherwise fetch the full book in one call.

Also attempt to fetch the pre-scraped JSON dump from the GitHub repo as a fallback:
`https://github.com/MohammedArab1/ThaqalaynAPI` — the `ThaqalaynData/` directory contains pre-scraped JSON files. Clone the repo if API fetching fails or is too slow.

### src/acquire/fawaz.py

**Source:** `https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions.json`
**Method:** Static CDN download. No auth.
**Output directory:** `data/raw/fawaz/`
**Strategy:**
1. Download `editions.json` → parse to get list of available editions.
2. Filter to English editions only (keys starting with `eng-`).
3. For each English edition, download the full JSON: `https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/{edition_key}.json`
4. Also download `info.json` for grading metadata.
**Post-download validation:** Assert ≥10 edition JSON files exist (there should be ~15+ English editions).

### src/acquire/sunnah_api.py

**Source:** `https://api.sunnah.com/v1/`
**Method:** REST API with `X-API-Key` header.
**Output directory:** `data/raw/sunnah/`
**Prerequisite:** `SUNNAH_API_KEY` must be set in env. If missing, log a warning and skip (don't fail the pipeline — this source is supplementary).
**Strategy:**
1. Fetch `/collections` → save as `collections.json`.
2. For each collection, fetch `/collections/{name}/hadiths?limit=100&page={n}` (paginated) using `fetch_json_paginated`.
3. Save each collection's hadiths as `{collection_name}_hadiths.json`.
4. Rate limit: 200ms between requests.
**Post-download validation:** Log collection count and total hadith count.

### src/acquire/open_hadith.py

**Source:** `https://github.com/mhashim6/Open-Hadith-Data`
**Method:** Shallow git clone.
**Output directory:** `data/raw/open_hadith/`
**Expected contents:** CSV files for 9 books, in two variants (with/without diacritics).
**Post-download validation:** Assert ≥9 CSV files with diacritics.

### src/acquire/muhaddithat.py

**Source:** `https://github.com/muhaddithat/isnad-datasets`
**Method:** Shallow git clone.
**Output directory:** `data/raw/muhaddithat/`
**Expected contents:** `hadiths.csv`, narrator CSV files, Jupyter notebooks.
**Post-download validation:** Assert `hadiths.csv` exists.

---

## STEP 4: Acquisition Orchestrator (src/acquire/__init__.py)

Create a `run_all(raw_dir: Path) -> dict[str, Path]` function that:
1. Calls each downloader's `run()` function in sequence.
2. Wraps each call in a try/except — log errors but continue to the next source.
3. Returns a dict mapping source names to their output directories.
4. Prints a summary table at the end: source name, status (✅/❌), file count, total size.

```python
from src.acquire import lk_corpus, sanadset, thaqalayn, fawaz, sunnah_api, open_hadith, muhaddithat

SOURCES = [
    ("lk", lk_corpus),
    ("sanadset", sanadset),
    ("thaqalayn", thaqalayn),
    ("fawaz", fawaz),
    ("sunnah", sunnah_api),
    ("open_hadith", open_hadith),
    ("muhaddithat", muhaddithat),
]

def run_all(raw_dir: Path) -> dict[str, Path]:
    ...
```

---

## STEP 5: Staging Table Schemas

Before writing parsers, define the exact Parquet schemas as intermediate representations. These are NOT the final Pydantic models (those are the graph nodes) — these are staging tables optimized for columnar processing. Create `src/parse/schemas.py`:

```python
"""Parquet staging table schemas.

These define the intermediate representation between raw source files and
final graph nodes. Each source parser outputs one or more of these tables.
Entity resolution in Phase 2 will consume these and produce canonical records.
"""

import pyarrow as pa

# ─── Hadith staging table ───
# One row per hadith per source. A hadith appearing in multiple sources
# will have multiple rows here; dedup happens in Phase 2.
HADITH_SCHEMA = pa.schema([
    pa.field("source_id", pa.string(), nullable=False),       # Unique within source, e.g., "lk:bukhari:1:1"
    pa.field("source_corpus", pa.string(), nullable=False),    # Matches SourceCorpus enum
    pa.field("collection_name", pa.string(), nullable=False),  # e.g., "bukhari", "alkafi"
    pa.field("book_number", pa.int32(), nullable=True),
    pa.field("chapter_number", pa.int32(), nullable=True),
    pa.field("hadith_number", pa.int32(), nullable=True),
    pa.field("matn_ar", pa.string(), nullable=True),
    pa.field("matn_en", pa.string(), nullable=True),
    pa.field("isnad_raw_ar", pa.string(), nullable=True),
    pa.field("isnad_raw_en", pa.string(), nullable=True),
    pa.field("full_text_ar", pa.string(), nullable=True),      # Complete hadith (isnad + matn) in Arabic
    pa.field("full_text_en", pa.string(), nullable=True),      # Complete hadith in English
    pa.field("grade", pa.string(), nullable=True),             # Raw grade string from source
    pa.field("chapter_name_ar", pa.string(), nullable=True),
    pa.field("chapter_name_en", pa.string(), nullable=True),
    pa.field("sect", pa.string(), nullable=False),             # "sunni" or "shia"
])

# ─── Narrator mention staging table ───
# One row per narrator mention extracted from an isnad string.
# NOT yet disambiguated — the same physical person may appear as multiple rows
# with variant name spellings. Disambiguation happens in Phase 2.
NARRATOR_MENTION_SCHEMA = pa.schema([
    pa.field("mention_id", pa.string(), nullable=False),       # Unique mention ID
    pa.field("source_hadith_id", pa.string(), nullable=False), # FK to HADITH_SCHEMA.source_id
    pa.field("source_corpus", pa.string(), nullable=False),
    pa.field("position_in_chain", pa.int32(), nullable=False), # 0-indexed position
    pa.field("name_ar", pa.string(), nullable=True),
    pa.field("name_en", pa.string(), nullable=True),
    pa.field("name_ar_normalized", pa.string(), nullable=True),# After normalize_arabic()
    pa.field("transmission_method", pa.string(), nullable=True),
])

# ─── Narrator bio staging table ───
# One row per narrator from biographical sources. Will be merged with
# mention data during disambiguation.
NARRATOR_BIO_SCHEMA = pa.schema([
    pa.field("bio_id", pa.string(), nullable=False),           # Source-specific ID
    pa.field("source", pa.string(), nullable=False),           # "kaggle_narrators", "thehadith", "muhaddithat"
    pa.field("name_ar", pa.string(), nullable=True),
    pa.field("name_en", pa.string(), nullable=True),
    pa.field("name_ar_normalized", pa.string(), nullable=True),
    pa.field("kunya", pa.string(), nullable=True),
    pa.field("nisba", pa.string(), nullable=True),
    pa.field("laqab", pa.string(), nullable=True),
    pa.field("birth_year_ah", pa.int32(), nullable=True),
    pa.field("death_year_ah", pa.int32(), nullable=True),
    pa.field("birth_location", pa.string(), nullable=True),
    pa.field("death_location", pa.string(), nullable=True),
    pa.field("generation", pa.string(), nullable=True),
    pa.field("gender", pa.string(), nullable=True),
    pa.field("trustworthiness", pa.string(), nullable=True),   # Raw grade string
    pa.field("bio_text", pa.string(), nullable=True),          # Full biographical note
    pa.field("external_id", pa.string(), nullable=True),       # muslimscholars.info ID or similar
])

# ─── Collection staging table ───
COLLECTION_SCHEMA = pa.schema([
    pa.field("collection_id", pa.string(), nullable=False),
    pa.field("name_ar", pa.string(), nullable=True),
    pa.field("name_en", pa.string(), nullable=False),
    pa.field("compiler_name", pa.string(), nullable=True),
    pa.field("compilation_year_ah", pa.int32(), nullable=True),
    pa.field("sect", pa.string(), nullable=False),
    pa.field("total_hadiths", pa.int32(), nullable=True),
    pa.field("source_corpus", pa.string(), nullable=False),
])

# ─── Network edges staging table (from muhaddithat dataset) ───
NETWORK_EDGE_SCHEMA = pa.schema([
    pa.field("from_narrator_name", pa.string(), nullable=False),
    pa.field("to_narrator_name", pa.string(), nullable=False),
    pa.field("hadith_id", pa.string(), nullable=True),
    pa.field("source", pa.string(), nullable=False),
    pa.field("from_external_id", pa.string(), nullable=True),
    pa.field("to_external_id", pa.string(), nullable=True),
])
```

---

## STEP 6: Shared Parser Utilities (src/parse/base.py)

```python
"""Shared parsing utilities."""

from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from src.utils.logging import get_logger

logger = get_logger(__name__)


def write_parquet(table: pa.Table, path: Path, schema: pa.Schema | None = None) -> Path:
    """Write a PyArrow Table to Parquet. Validate against schema if provided.
    Create parent directories. Log row count and file size."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if schema is not None:
        table = table.cast(schema)
    pq.write_table(table, path, compression="snappy")
    size_mb = path.stat().st_size / (1024 * 1024)
    logger.info("Wrote parquet", path=str(path), rows=table.num_rows, size_mb=round(size_mb, 2))
    return path


def read_csv_robust(path: Path, encoding: str = "utf-8", **kwargs) -> pa.Table:
    """Read a CSV with robust error handling for encoding issues.
    Try the specified encoding first, fall back to utf-8-sig, then latin-1.
    Pass through kwargs to pyarrow.csv.read_csv or pandas.read_csv."""


def generate_source_id(corpus: str, collection: str, *parts: int | str) -> str:
    """Generate a deterministic source_id string.
    E.g., generate_source_id("lk", "bukhari", 1, 1) → "lk:bukhari:1:1" """
    segments = [corpus, collection] + [str(p) for p in parts]
    return ":".join(segments)


def safe_int(value: str | int | float | None) -> int | None:
    """Safely convert a value to int. Return None on failure."""
    if value is None:
        return None
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None


def safe_str(value: object | None) -> str | None:
    """Convert to stripped string. Return None if empty or NaN."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s.lower() == "nan" or s.lower() == "none":
        return None
    return s
```

---

## STEP 7: Individual Parsers

Each parser is a module in `src/parse/` with a `def run(raw_dir: Path, staging_dir: Path) -> list[Path]` entry point that reads from the source's raw subdirectory, transforms data, writes Parquet files to staging, and returns the list of output file paths.

### src/parse/lk_corpus.py

**Input:** `data/raw/lk/` — CSV files per book.
**Outputs:**
- `data/staging/hadiths_lk.parquet` — All hadiths from all 6 books.
- `data/staging/narrator_mentions_lk.parquet` — Narrator mentions extracted from isnad fields.
- `data/staging/collections_lk.parquet` — Collection metadata for the 6 books.

**Parsing logic:**

1. Read each CSV using pandas. The LK corpus uses 16 columns:
   ```
   Chapter_Number, Chapter_English, Chapter_Arabic, Section_Number,
   Section_English, Section_Arabic, Hadith_number, English_Hadith,
   English_Isnad, English_Matn, Arabic_Hadith, Arabic_Isnad,
   Arabic_Matn, Arabic_Comment, English_Grade, Arabic_Grade
   ```
   **CRITICAL:** Do NOT use `pd.read_csv` with default settings. The LK corpus CSVs have known encoding and delimiter issues. Use these settings:
   - `encoding="utf-8"`
   - `on_bad_lines="warn"` (pandas 2.x) to log problematic rows instead of failing
   - Explicitly set column names from the known 16-column schema
   - If a CSV has more or fewer columns than expected, log a warning and attempt to recover.

2. Map each row to the `HADITH_SCHEMA`:
   - `source_id`: `generate_source_id("lk", book_name, chapter_num, hadith_num)`
   - `source_corpus`: `"lk"`
   - `collection_name`: Derive from filename (e.g., `Albukhari.csv` → `"bukhari"`)
   - `book_number`: `Chapter_Number`
   - `chapter_number`: `Section_Number`
   - `hadith_number`: `Hadith_number`
   - `matn_ar`: `Arabic_Matn`
   - `matn_en`: `English_Matn`
   - `isnad_raw_ar`: `Arabic_Isnad`
   - `isnad_raw_en`: `English_Isnad`
   - `full_text_ar`: `Arabic_Hadith`
   - `full_text_en`: `English_Hadith`
   - `grade`: `English_Grade` (prefer English; fall back to `Arabic_Grade`)
   - `chapter_name_ar`: `Chapter_Arabic`
   - `chapter_name_en`: `Chapter_English`
   - `sect`: `"sunni"`

3. Extract narrator mentions from `English_Isnad` field (English is more reliably parseable for Phase 1; Arabic NER comes in Phase 2):
   - Split on common English isnad patterns: "Narrated", "reported by", "on the authority of", "from", "who heard from"
   - For each extracted name span, create a row in `NARRATOR_MENTION_SCHEMA`.
   - If `Arabic_Isnad` is available, use `src.utils.arabic.extract_transmission_phrases` to identify Arabic transmission phrase boundaries, then extract the name spans between them.
   - Set `name_ar_normalized` using `src.utils.arabic.normalize_arabic`.
   - **This extraction will be imperfect.** That's fine — it's a first pass. Phase 2's NER pipeline will refine it. The goal here is to extract ~60-70% of mentions correctly.

4. Generate collection metadata:
   - One row per book with name, approximate hadith count, sect = "sunni".
   - Known compilations: Bukhari (~7563), Muslim (~7563), Abu Dawud (~5274), Tirmidhi (~3956), Nasa'i (~5758), Ibn Majah (~4341). Use these as `total_hadiths` estimates.

**Known pitfalls:**
- Some LK CSVs have inconsistent quoting. If a row fails to parse, log and skip it.
- Bukhari is the gold-standard subset (manually verified isnad segmentation). Flag it in logs.
- Some fields may contain HTML entities or markup — strip them.

### src/parse/sanadset.py

**Input:** `data/raw/sanadset/` — CSV files from Kaggle.
**Outputs:**
- `data/staging/hadiths_sanadset.parquet`
- `data/staging/narrator_mentions_sanadset.parquet`
- `data/staging/narrators_bio_kaggle.parquet` (from the narrators sub-download)

**Parsing logic:**

1. Read the main hadith CSV. The Sanadset uses `<SANAD>`, `<MATN>`, and `<NAR>` XML-style tags within the text fields.

2. For each row:
   - Extract SANAD text: content between `<SANAD>` and `</SANAD>` (or `<MATN>` if no closing tag).
   - Extract MATN text: content between `<MATN>` and `</MATN>` (or end of string).
   - Extract narrator names: find all `<NAR>name</NAR>` spans within SANAD. Each is a narrator mention.
   - Rows with "No SANAD" in the Sanad field: set `isnad_raw_ar = None`, skip narrator extraction.

3. Map to `HADITH_SCHEMA`:
   - `source_id`: `generate_source_id("sanadset", book_name, hadith_number)`
   - `source_corpus`: `"sanadset"`
   - `matn_ar`: extracted MATN text
   - `isnad_raw_ar`: extracted SANAD text (with NAR tags stripped)
   - `sect`: `"sunni"` (Sanadset is exclusively Sunni canonical texts)

4. Map narrator mentions to `NARRATOR_MENTION_SCHEMA`:
   - Parse `<NAR>` tags in order. Position = index in the tag sequence.
   - `name_ar`: raw text between NAR tags.
   - `name_ar_normalized`: after `normalize_arabic()`.
   - `transmission_method`: attempt to identify from the Arabic text between consecutive NAR tags using `extract_transmission_phrases`.

5. Parse the narrators biographical CSV into `NARRATOR_BIO_SCHEMA`:
   - Map available fields (name, dates, location, trustworthiness). The Kaggle narrators dataset structure may vary — inspect the headers first, then map dynamically.
   - Set `source = "kaggle_narrators"`.

**Performance note:** The Sanadset has 650K+ rows. Use PyArrow directly for reading if pandas is too slow. Process in chunks of 50K rows.

### src/parse/thaqalayn.py

**Input:** `data/raw/thaqalayn/` — JSON files per book.
**Outputs:**
- `data/staging/hadiths_thaqalayn.parquet`
- `data/staging/collections_thaqalayn.parquet`

**Parsing logic:**

1. Read `allbooks.json` to get the list of books with their IDs and names.
2. For each book JSON file, iterate hadiths. Expected structure per hadith (inspect actual JSON and adapt):
   ```json
   {
     "id": 12345,
     "arabicText": "...",
     "englishText": "...",
     "book": { "id": 1, "name": "al-Kafi" },
     "chapter": { "id": 1, "name": "..." },
     "grading": "..."
   }
   ```
   **CRITICAL:** The actual ThaqalaynAPI response structure may differ from this example. Inspect the first downloaded JSON file, log its keys, and adapt the parser accordingly. Do NOT assume a fixed structure — build the parser to discover and map fields dynamically, with fallbacks for missing fields.

3. Map to `HADITH_SCHEMA`:
   - `source_corpus`: `"thaqalayn"`
   - `sect`: `"shia"`
   - Map Arabic text to `matn_ar` (or `full_text_ar` if isnad/matn are not separated — Shia collections often present the full hadith without segmentation).
   - If isnad is not separated from matn, set `isnad_raw_ar = None` and put the full text in `full_text_ar`.

4. Generate collection metadata for each unique book encountered.

### src/parse/fawaz.py

**Input:** `data/raw/fawaz/` — JSON files per edition + info.json.
**Outputs:**
- `data/staging/hadiths_fawaz.parquet`
- `data/staging/collections_fawaz.parquet`

**Parsing logic:**

1. Read `editions.json` to enumerate available editions.
2. For each English edition JSON file, iterate hadiths. Expected structure:
   ```json
   {
     "metadata": { "name": "Sunan Abu Dawud", ... },
     "hadiths": [
       { "hadithnumber": 1, "text": "...", "grades": [...] }
     ]
   }
   ```
3. Map to `HADITH_SCHEMA`:
   - `source_corpus`: `"fawaz"`
   - `sect`: `"sunni"` (fawaz covers Sunni collections; check for any Shia editions and tag accordingly)
   - `matn_en`: hadith text (fawaz English editions typically contain full text without isnad/matn separation)
   - `grade`: serialize grades array to string or take the primary grade.
4. Read `info.json` for grading details per edition. Augment hadith records with grading metadata.

### src/parse/sunnah_api.py

**Input:** `data/raw/sunnah/` — JSON files per collection.
**Outputs:**
- `data/staging/hadiths_sunnah.parquet`
- `data/staging/collections_sunnah.parquet`

**Parsing logic:**

1. Read `collections.json` for collection metadata.
2. For each collection's hadiths JSON, iterate records. Sunnah.com API returns hadiths with this structure:
   ```json
   {
     "hadithNumber": "1",
     "body": "...",
     "grades": [{"grade": "Sahih", "graded_by": "Al-Albani"}],
     "collection": "bukhari",
     "bookNumber": "1",
     "chapterNumber": "1"
   }
   ```
   Adapt to actual response structure. Both Arabic and English bodies may be available under language-keyed fields.

3. Map to `HADITH_SCHEMA`:
   - `source_corpus`: `"sunnah"`
   - `sect`: `"sunni"`
   - Extract Arabic and English text from language-specific fields.
   - If grades array has multiple entries, serialize all as JSON string in `grade` field.

**Note:** If `SUNNAH_API_KEY` was not set and this source was skipped during acquisition, the parser should detect the missing raw files and exit gracefully with a log message.

### src/parse/open_hadith.py

**Input:** `data/raw/open_hadith/` — CSV files for 9 books (diacritics and no-diacritics variants).
**Outputs:**
- `data/staging/hadiths_open_hadith.parquet`

**Parsing logic:**

1. Read the **with-diacritics** CSV variants (these are the authoritative texts).
2. The Open-Hadith-Data CSVs have varying schemas per book. Inspect headers first:
   - Typical columns include hadith text, elaboration (tafseel), book/chapter identifiers.
   - Some books lack elaboration (Musnad Ahmad, Sunan al-Darimi).
3. Map to `HADITH_SCHEMA`:
   - `source_corpus`: `"open_hadith"`
   - `sect`: `"sunni"`
   - `matn_ar`: hadith text with diacritics preserved.
   - Isnad/matn may not be separated in this source — if not, put full text in `full_text_ar`.

### src/parse/muhaddithat.py

**Input:** `data/raw/muhaddithat/` — hadiths.csv, narrator CSVs.
**Outputs:**
- `data/staging/narrators_bio_muhaddithat.parquet`
- `data/staging/network_edges_muhaddithat.parquet`

**Parsing logic:**

1. Read `hadiths.csv` — each row contains a hadith ID and its isnad as a sequence of narrator IDs.
2. Read the narrator CSV — each row has an ID (matching muslimscholars.info), display name (with diacritics), gender, and brief bio.
3. Map narrators to `NARRATOR_BIO_SCHEMA`:
   - `source`: `"muhaddithat"`
   - `external_id`: the muslimscholars.info ID
   - `gender`: from the dataset
4. Map isnad sequences to `NETWORK_EDGE_SCHEMA`:
   - For each hadith, decompose the narrator sequence into consecutive pairs (narrator[i] → narrator[i+1]).
   - `from_external_id` and `to_external_id`: the muslimscholars.info IDs.

---

## STEP 8: Parse Orchestrator (src/parse/__init__.py)

Create a `run_all(raw_dir: Path, staging_dir: Path) -> dict[str, list[Path]]` function:

```python
from src.parse import (
    lk_corpus, sanadset, thaqalayn, fawaz,
    sunnah_api, open_hadith, muhaddithat,
)

PARSERS = [
    ("lk", lk_corpus),
    ("sanadset", sanadset),
    ("thaqalayn", thaqalayn),
    ("fawaz", fawaz),
    ("sunnah", sunnah_api),
    ("open_hadith", open_hadith),
    ("muhaddithat", muhaddithat),
]

def run_all(raw_dir: Path, staging_dir: Path) -> dict[str, list[Path]]:
    """Run all parsers. Return dict mapping source name to output file paths.
    Continue on failure; log errors."""
```

After all parsers complete, log a summary table:
- Source name, status, output file count, total row count across files, total Parquet size.
- Compute and log grand totals: total hadiths across all sources, total narrator mentions, total bio records.

---

## STEP 9: Wire Up the CLI and Makefile

### Update src/cli.py

Wire the `acquire` and `parse` commands to the orchestrators:

```python
if args.command == "acquire":
    from src.acquire import run_all as acquire_all
    settings = get_settings()
    results = acquire_all(Path(settings.data_raw_dir))
    print(f"Acquisition complete. {len(results)} sources downloaded.")

elif args.command == "parse":
    from src.parse import run_all as parse_all
    settings = get_settings()
    results = parse_all(Path(settings.data_raw_dir), Path(settings.data_staging_dir))
    print(f"Parsing complete. {sum(len(v) for v in results.values())} staging files produced.")
```

### Update Makefile

Replace the `acquire` and `parse` stubs:

```makefile
acquire:         ## Phase 1: Download all data sources
	uv run python -m src.cli acquire

parse:           ## Phase 1: Parse raw data into staging Parquet files
	uv run python -m src.cli parse
```

---

## STEP 10: Tests

### tests/test_acquire/

Create `tests/test_acquire/__init__.py` and `tests/test_acquire/test_base.py`:

- Test `generate_source_id` with various inputs.
- Test `safe_int` with ints, floats, strings, None, "NaN".
- Test `safe_str` with strings, None, empty, "nan", "None".
- Test `sha256_file` with a known test file.
- Test `ensure_dir` creates nested directories.

### tests/test_parse/

Create `tests/test_parse/__init__.py` and the following:

**tests/test_parse/test_schemas.py:**
- Test that each PyArrow schema can be used to create an empty Table.
- Test that a Table with sample data casts to each schema without errors.

**tests/test_parse/test_lk_parser.py:**
- Create a minimal mock CSV with 3 rows matching the LK 16-column format.
- Write it to a temp directory.
- Run the LK parser against it.
- Assert the output Parquet files exist, have expected row counts, and conform to the staging schemas.

**tests/test_parse/test_sanadset_parser.py:**
- Create a minimal mock CSV with rows containing `<SANAD>`, `<MATN>`, and `<NAR>` tags.
- Include one row with "No SANAD" to test the null-isnad path.
- Run the Sanadset parser.
- Assert narrator mentions are correctly extracted from NAR tags.
- Assert position_in_chain is sequential.

**tests/test_parse/test_narrator_extraction.py:**
- Test English isnad extraction with known inputs:
  - `"Narrated Abu Hurayra: The Prophet said..."` → should extract "Abu Hurayra"
  - `"It was narrated on the authority of Anas who heard from Malik..."` → should extract "Anas", "Malik"
- Test Arabic isnad extraction with known inputs using `extract_transmission_phrases`.

### tests/conftest.py (additions)

Add fixtures:
- `tmp_raw_dir` — temporary directory for mock raw data.
- `tmp_staging_dir` — temporary directory for parser output.
- `sample_lk_csv` — writes a 5-row mock CSV matching LK format and returns the path.
- `sample_sanadset_csv` — writes a 5-row mock CSV with NAR tags and returns the path.

---

## STEP 11: Data Validation Script (src/parse/validate.py)

Create a standalone validation script that reads all staging Parquet files and produces a comprehensive report:

```python
def validate_staging(staging_dir: Path) -> dict:
    """Read all Parquet files in staging_dir. For each file:
    - Report row count, column count, null percentages per column.
    - Verify schema matches expected staging schema.
    - Check for duplicate source_ids within each hadith file.
    - Check for empty matn fields (should be rare).
    - Report Arabic vs English coverage (% of rows with non-null matn_ar vs matn_en).

    Return a dict summarizing all findings. Print a formatted report to stdout.
    """
```

Add a CLI command `validate-staging` and a Makefile target:
```makefile
validate-staging:  ## Validate staging Parquet files
	uv run python -m src.cli validate-staging
```

---

## EXECUTION NOTES FOR CLAUDE CODE

1. Read the existing Phase 0 codebase first. Use the existing Pydantic models, enums, Arabic utils, config, and logging. Do not recreate them.

2. Every downloader must be idempotent. If files already exist in `data/raw/{source}/`, skip the download. This is critical for development iteration — nobody wants to re-download 650K hadiths because they're debugging a parser.

3. Every parser must handle malformed data gracefully. Log warnings for bad rows; do not crash. The Sanadset in particular has known encoding issues and inconsistent field counts.

4. The LK corpus CSV reader is the most fragile component. Test it thoroughly with mock data before running on real files. The CSVs are NOT Excel-compatible (confirmed in the LK documentation) — do not assume standard CSV dialect.

5. For the ThaqalaynAPI parser, you MUST inspect the actual JSON structure first. Write a small discovery function that loads one file, prints its keys and nested structure, and use that to build the field mapping. Do not hardcode assumptions about Thaqalayn's JSON schema.

6. All Parquet writes must use Snappy compression and validate against the staging schemas.

7. After implementing everything, run the full test suite: `pytest tests/ -v`. Also run `ruff check src/ tests/` and `mypy src/`.

8. Update the README.md Phase table: Phase 0 = ✅, Phase 1 = ✅, rest = ⬜.
