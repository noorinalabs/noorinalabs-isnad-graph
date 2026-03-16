# Phase 0: Scaffold & Tooling — Claude Code Instruction Set

> **Status (2026-03-15):** Phase 0 is complete. All scaffold, tooling, models, and infrastructure described below have been implemented.

## PROJECT CONTEXT

You are initializing a Python monorepo called `isnad-graph` — a computational hadith analysis platform that ingests Sunni and Shia hadith collections into a Neo4j graph database for isnad chain analysis, narrator network topology, and cross-sectarian parallel detection.

This is Phase 0 of a 5-phase build. Your job is to create the complete project scaffold: directory structure, dependency management, Pydantic data models, Docker infrastructure, Makefile orchestration, configuration management, and foundational utility modules. No data acquisition or processing happens in this phase — only the skeleton that subsequent phases will flesh out.

---

## STEP 1: Initialize the repository

Create the project root at `./isnad-graph/` with the following structure. Every directory listed below should be created, including empty `__init__.py` files where needed for Python package resolution.

```
isnad-graph/
├── README.md
├── LICENSE                        # MIT
├── pyproject.toml                 # uv-managed, Python 3.11+
├── Makefile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .python-version                # 3.11
│
├── src/
│   ├── __init__.py
│   ├── config.py                  # Pydantic Settings for env-based config
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── enums.py               # All enum types
│   │   ├── narrator.py            # Narrator node model
│   │   ├── hadith.py              # Hadith node model
│   │   ├── collection.py          # Collection node model
│   │   ├── chain.py               # Chain node model
│   │   ├── grading.py             # Grading node model
│   │   ├── historical.py          # HistoricalEvent + Location node models
│   │   └── edges.py               # All edge/relationship models
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── arabic.py              # Arabic text processing utilities
│   │   ├── neo4j_client.py        # Neo4j connection manager
│   │   ├── pg_client.py           # PostgreSQL connection manager
│   │   └── logging.py             # Structured logging setup
│   │
│   ├── acquire/
│   │   ├── __init__.py
│   │   └── .gitkeep               # Phase 1
│   │
│   ├── parse/
│   │   ├── __init__.py
│   │   └── .gitkeep               # Phase 1
│   │
│   ├── resolve/
│   │   ├── __init__.py
│   │   └── .gitkeep               # Phase 2
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   └── .gitkeep               # Phase 3
│   │
│   └── enrich/
│       ├── __init__.py
│       └── .gitkeep               # Phase 4
│
├── data/
│   ├── raw/
│   │   └── .gitkeep
│   ├── staging/
│   │   └── .gitkeep
│   └── curated/
│       ├── .gitkeep
│       └── historical_events.yaml  # Seed file with major events
│
├── notebooks/
│   └── .gitkeep
│
├── queries/
│   ├── validation/
│   │   └── .gitkeep
│   └── analysis/
│       └── .gitkeep
│
└── tests/
    ├── __init__.py
    ├── conftest.py                # Shared fixtures
    ├── test_models/
    │   ├── __init__.py
    │   └── test_all_models.py
    ├── test_utils/
    │   ├── __init__.py
    │   └── test_arabic.py
    └── test_config.py
```

---

## STEP 2: pyproject.toml

Use `uv` as the package manager. Target Python 3.11+. Include these dependency groups:

### Core dependencies:
```
pydantic >= 2.6
pydantic-settings >= 2.1
neo4j >= 5.15
psycopg[binary] >= 3.1
httpx >= 0.27
pyarrow >= 15.0
pandas >= 2.2
pyyaml >= 6.0
structlog >= 24.1
python-dotenv >= 1.0
```

### Dev dependencies (in a `[tool.uv.dev-dependencies]` or `[project.optional-dependencies]` dev group):
```
pytest >= 8.0
pytest-asyncio >= 0.23
pytest-cov >= 4.1
ruff >= 0.3
mypy >= 1.8
```

### Phase 2+ dependencies (in an "ml" optional group, not installed in Phase 0):
```
sentence-transformers >= 2.5
faiss-cpu >= 1.7
transformers >= 4.38
torch >= 2.2
rapidfuzz >= 3.6
camel-tools >= 1.5
```

Configure ruff for linting and formatting. Set line length 100. Enable isort, pyflakes, pycodestyle, and pydantic rules. Configure mypy for strict mode with pydantic plugin.

The `[project.scripts]` section should include:
```
isnad = "src.cli:main"
```

(We'll create a minimal CLI entry point.)

---

## STEP 3: Docker Compose

Create `docker-compose.yml` with three services on a shared `isnad-net` bridge network:

### neo4j
- Image: `neo4j:5-community`
- Ports: 7474 (browser), 7687 (bolt)
- Environment:
  - `NEO4J_AUTH=neo4j/isnad_graph_dev`
  - `NEO4J_PLUGINS=["apoc", "graph-data-science"]`
  - `NEO4J_dbms_memory_heap_max__size=2G`
  - `NEO4J_dbms_memory_pagecache_size=1G`
- Volume: `neo4j_data:/data`

### postgres
- Image: `pgvector/pgvector:pg16`
- Ports: 5432
- Environment:
  - `POSTGRES_DB=isnad_graph`
  - `POSTGRES_USER=isnad`
  - `POSTGRES_PASSWORD=isnad_dev`
- Volume: `pg_data:/var/lib/postgresql/data`
- Healthcheck: `pg_isready -U isnad`

### redis (optional, for caching API responses during acquisition)
- Image: `redis:7-alpine`
- Ports: 6379

Declare named volumes: `neo4j_data`, `pg_data`.

---

## STEP 4: Environment Configuration

### .env.example
```
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=isnad_graph_dev

# PostgreSQL
PG_DSN=postgresql://isnad:isnad_dev@localhost:5432/isnad_graph

# Redis
REDIS_URL=redis://localhost:6379/0

# APIs
SUNNAH_API_KEY=
KAGGLE_USERNAME=
KAGGLE_KEY=

# Paths
DATA_RAW_DIR=./data/raw
DATA_STAGING_DIR=./data/staging
DATA_CURATED_DIR=./data/curated

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=console
```

### src/config.py
Use `pydantic-settings` with `BaseSettings`. Load from `.env` file with `env_file=".env"`. Define all fields above with appropriate types and defaults. Group into nested models if you like (`Neo4jSettings`, `PostgresSettings`, etc.), but expose a single `Settings` class as the public API. Include a `@lru_cache` singleton getter function `get_settings()`.

---

## STEP 5: Enum Types (src/models/enums.py)

Define the following as `str, Enum` types (so they serialize cleanly to JSON/Parquet):

```python
class NarratorGeneration(str, Enum):
    SAHABI = "sahabi"
    TABII = "tabii"
    TABA_TABII = "taba_tabii"
    ATBA_TABA_TABIIN = "atba_taba_tabiin"
    LATER = "later"
    UNKNOWN = "unknown"

class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"

class SectAffiliation(str, Enum):
    SUNNI = "sunni"
    SHIA = "shia"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"

class TrustworthinessGrade(str, Enum):
    THIQA = "thiqa"                        # trustworthy
    SADUQ = "saduq"                        # truthful
    MAQBUL = "maqbul"                      # acceptable
    DAIF = "daif"                          # weak
    MATRUK = "matruk"                      # abandoned
    KADHDHAB = "kadhdhab"                  # liar
    UNKNOWN = "unknown"

class HadithGrade(str, Enum):
    SAHIH = "sahih"
    HASAN = "hasan"
    DAIF = "daif"
    MAWDU = "mawdu"                        # fabricated
    SAHIH_LI_GHAYRIHI = "sahih_li_ghayrihi"
    HASAN_LI_GHAYRIHI = "hasan_li_ghayrihi"
    UNKNOWN = "unknown"

class TransmissionMethod(str, Enum):
    HADDATHANA = "haddathana"              # حدثنا — "he narrated to us"
    AKHBARANA = "akhbarana"                # أخبرنا — "he informed us"
    SAMITU = "samitu"                      # سمعت — "I heard"
    AN = "an"                              # عن — "from" (weakest explicit form)
    QALA = "qala"                          # قال — "he said"
    ANBA_ANA = "anba_ana"                  # أنبأنا — "he told us"
    NAWALANI = "nawalani"                  # ناولني — "he handed to me" (munawala)
    KATABA_ILAYYA = "kataba_ilayya"        # كتب إلي — "he wrote to me"
    WIJADA = "wijada"                      # وجادة — "I found" (written source)
    OTHER = "other"
    UNKNOWN = "unknown"

class ChainClassification(str, Enum):
    MUTTASIL = "muttasil"                  # connected chain
    MURSAL = "mursal"                      # companion omitted
    MUALLAQ = "muallaq"                    # suspended (beginning omitted)
    MUNQATI = "munqati"                    # interrupted (middle gap)
    MUDALLAS = "mudallas"                  # concealed (narrator obscured)
    MUDTARIB = "mudtarib"                  # shaky (conflicting versions)
    UNKNOWN = "unknown"

class ChainPosition(str, Enum):
    ORIGINATOR = "originator"              # Prophet or Imam (source)
    FIRST = "first"                        # first transmitter (sahabi usually)
    MIDDLE = "middle"
    LAST = "last"                          # compiler or near-compiler
    UNKNOWN = "unknown"

class NarratorRole(str, Enum):
    ORIGINATOR = "originator"
    TRANSMITTER = "transmitter"
    COMPILER = "compiler"

class VariantType(str, Enum):
    VERBATIM = "verbatim"
    CLOSE_PARAPHRASE = "close_paraphrase"
    THEMATIC = "thematic"
    CONTRADICTORY = "contradictory"

class HistoricalEventType(str, Enum):
    CALIPHATE = "caliphate"
    FITNA = "fitna"
    CONQUEST = "conquest"
    THEOLOGICAL_CONTROVERSY = "theological_controversy"
    COMPILATION_EFFORT = "compilation_effort"
    PERSECUTION = "persecution"
    DYNASTY_TRANSITION = "dynasty_transition"

class SourceCorpus(str, Enum):
    LK = "lk"
    SANADSET = "sanadset"
    THAQALAYN = "thaqalayn"
    SUNNAH = "sunnah"
    FAWAZ = "fawaz"
    OPEN_HADITH = "open_hadith"
    MUHADDITHAT = "muhaddithat"

class Sect(str, Enum):
    SUNNI = "sunni"
    SHIA = "shia"
```

---

## STEP 6: Pydantic Node Models

All models should use `pydantic.BaseModel` with `model_config = ConfigDict(frozen=True, str_strip_whitespace=True)`. Use `Optional` fields where data may be missing. Include docstrings on each model and on non-obvious fields.

### src/models/narrator.py — Narrator
```
Fields:
  id: str                                  # Canonical ID, e.g. "nar:abu-hurayra-001"
  name_ar: str                             # Full Arabic name
  name_en: str                             # Full English transliteration
  kunya: Optional[str]                     # e.g., "Abu Hurayra"
  nisba: Optional[str]                     # e.g., "al-Dawsi"
  laqab: Optional[str]                     # honorific/epithet
  birth_year_ah: Optional[int]             # Hijri year, nullable
  death_year_ah: Optional[int]
  birth_location_id: Optional[str]         # FK to Location.id
  death_location_id: Optional[str]
  generation: NarratorGeneration
  gender: Gender
  sect_affiliation: SectAffiliation
  tabaqat_class: Optional[str]             # Layer/class in tabaqat literature
  trustworthiness_consensus: TrustworthinessGrade
  aliases: list[str] = []                  # Alternate name forms
  # Graph metrics (populated in Phase 4, nullable until then)
  betweenness_centrality: Optional[float] = None
  in_degree: Optional[int] = None
  out_degree: Optional[int] = None
  pagerank: Optional[float] = None
  community_id: Optional[int] = None
```

Include a `@field_validator` on `id` that enforces the `nar:` prefix pattern.

### src/models/hadith.py — Hadith
```
Fields:
  id: str                                  # e.g., "hdt:bukhari-001-001"
  matn_ar: str                             # Arabic body text
  matn_en: Optional[str]                   # English translation
  isnad_raw_ar: Optional[str]              # Raw Arabic isnad string
  isnad_raw_en: Optional[str]              # Raw English isnad string
  grade_composite: Optional[str]           # Consensus or primary grade string
  topic_tags: list[str] = []               # Populated in Phase 4
  source_corpus: SourceCorpus
  has_shia_parallel: bool = False
  has_sunni_parallel: bool = False
```

Include a `@field_validator` on `id` that enforces the `hdt:` prefix pattern.

### src/models/collection.py — Collection
```
Fields:
  id: str                                  # e.g., "col:bukhari"
  name_ar: str
  name_en: str
  compiler_name: Optional[str]             # Human-readable compiler name
  compiler_id: Optional[str]               # FK to Narrator.id, nullable
  compilation_year_ah: Optional[int]
  sect: Sect
  canonical_rank: Optional[int]            # 1 = highest authority in its tradition
  total_hadiths: Optional[int]
  book_count: Optional[int]
```

### src/models/chain.py — Chain
```
Fields:
  id: str                                  # e.g., "chn:bukhari-001-001-0"
  hadith_id: str                           # FK to Hadith.id
  chain_index: int                         # 0-based, for multi-chain hadiths
  full_chain_text_ar: Optional[str]
  full_chain_text_en: Optional[str]
  chain_length: int
  is_complete: bool
  is_elevated: bool = False                # ali isnad (short chain)
  classification: ChainClassification
  narrator_ids: list[str] = []             # Ordered list of Narrator IDs in this chain
```

### src/models/grading.py — Grading
```
Fields:
  id: str
  hadith_id: str                           # FK to Hadith.id
  scholar_name: str
  grade: HadithGrade
  methodology_school: Optional[str]        # e.g., "Hanbali", "Imami"
  era: Optional[str]                       # e.g., "classical", "modern"
```

### src/models/historical.py — HistoricalEvent and Location
```
HistoricalEvent:
  id: str
  name_en: str
  name_ar: Optional[str]
  year_start_ah: int
  year_end_ah: Optional[int]
  year_start_ce: int
  year_end_ce: Optional[int]
  type: HistoricalEventType
  caliphate: Optional[str]
  region: Optional[str]
  description: Optional[str]

Location:
  id: str                                  # e.g., "loc:medina"
  name_en: str
  name_ar: Optional[str]
  region: Optional[str]
  lat: Optional[float]
  lon: Optional[float]
  political_entity_period: Optional[dict]  # JSON: {"622-661": "Rashidun", "661-750": "Umayyad", ...}
```

### src/models/edges.py — Edge/Relationship Models

These are lightweight models for serialization/validation of edge data, not Neo4j relationship objects directly.

```
TransmittedTo:
  from_narrator_id: str
  to_narrator_id: str
  hadith_id: str
  chain_id: str
  position_in_chain: int
  transmission_method: TransmissionMethod

AppearsIn:
  hadith_id: str
  collection_id: str
  book_number: Optional[int]
  chapter_number: Optional[int]
  hadith_number_in_book: Optional[int]

ParallelOf:
  hadith_id_a: str
  hadith_id_b: str
  similarity_score: float                  # 0.0 to 1.0
  variant_type: VariantType
  cross_sect: bool

StudiedUnder:
  student_id: str                          # Narrator who learned
  teacher_id: str                          # Narrator who taught
  period_ah: Optional[str]
  location_id: Optional[str]
  source: Optional[str]                    # Where this relationship is documented

ActiveDuring:
  narrator_id: str
  event_id: str
  role: Optional[str]
  affiliation: Optional[str]

BasedIn:
  narrator_id: str
  location_id: str
  period_ah: Optional[str]
  role: Optional[str]
```

### src/models/__init__.py

Re-export all models and enums from this package for convenient imports:
```python
from src.models.enums import *
from src.models.narrator import Narrator
from src.models.hadith import Hadith
# ... etc
```

---

## STEP 7: Arabic Text Utilities (src/utils/arabic.py)

Implement these pure functions:

```python
def strip_diacritics(text: str) -> str:
    """Remove Arabic diacritical marks (tashkeel): fatha, damma, kasra, sukun,
    shadda, tanwin, superscript alef, etc. Unicode range 0x064B-0x065F, 0x0670."""

def normalize_alif(text: str) -> str:
    """Normalize alif variants (أ إ آ ٱ) to bare alif (ا)."""

def normalize_hamza(text: str) -> str:
    """Normalize hamza variants (ؤ ئ ء) to a canonical form."""

def normalize_taa_marbuta(text: str) -> str:
    """Normalize taa marbuta (ة) to haa (ه) for search matching."""

def normalize_arabic(text: str) -> str:
    """Full normalization pipeline: strip diacritics, normalize alif, hamza,
    taa marbuta, collapse whitespace, strip tatweel (kashida ـ)."""

def clean_whitespace(text: str) -> str:
    """Collapse multiple whitespace chars to single space, strip edges."""

def is_arabic(text: str) -> bool:
    """Check if text contains Arabic script characters."""

def extract_transmission_phrases(text: str) -> list[tuple[int, int, str]]:
    """Find transmission formula positions in an isnad string.
    Returns list of (start_pos, end_pos, method_label) tuples.
    Known patterns: حدثنا, أخبرنا, سمعت, عن, قال, أنبأنا, ناولني, كتب إلي"""
```

Use only the `re` and `unicodedata` stdlib modules — no external Arabic NLP libraries in Phase 0. The diacritics range is well-defined in Unicode and can be handled with a compiled regex character class.

---

## STEP 8: Database Client Utilities

### src/utils/neo4j_client.py

A context-managed Neo4j driver wrapper:

```python
class Neo4jClient:
    """Manages Neo4j driver lifecycle and provides query execution helpers."""

    def __init__(self, uri: str, user: str, password: str):
        ...

    def execute_read(self, query: str, parameters: dict | None = None) -> list[dict]:
        """Execute a read transaction, return list of record dicts."""

    def execute_write(self, query: str, parameters: dict | None = None) -> list[dict]:
        """Execute a write transaction, return list of record dicts."""

    def execute_write_batch(self, query: str, batch: list[dict], batch_size: int = 1000) -> int:
        """Execute a parameterized write query in batches using UNWIND.
        Returns total records affected."""

    def ensure_constraints(self) -> None:
        """Create uniqueness constraints for all node types:
        - Narrator(id), Hadith(id), Collection(id), Chain(id),
          Grading(id), HistoricalEvent(id), Location(id)"""

    def close(self) -> None: ...
    def __enter__(self): ...
    def __exit__(self, *args): ...
```

Use the `neo4j` Python driver. All queries should use parameterized inputs (never string interpolation).

### src/utils/pg_client.py

A context-managed PostgreSQL wrapper using `psycopg`:

```python
class PgClient:
    """Manages PostgreSQL connection and provides query helpers."""

    def __init__(self, dsn: str):
        ...

    def execute(self, query: str, params: tuple | None = None) -> list[dict]: ...
    def execute_many(self, query: str, params_list: list[tuple]) -> int: ...
    def ensure_schema(self) -> None:
        """Create the isnad_graph schema and pgvector extension if not exists."""
    def close(self) -> None: ...
    def __enter__(self): ...
    def __exit__(self, *args): ...
```

### src/utils/logging.py

Configure `structlog` with:
- Console renderer for development (colorized, human-readable).
- JSON renderer when `LOG_FORMAT=json` (for production/CI).
- Bind `logger_name` from the calling module automatically.
- Export a `get_logger(name: str)` factory function.

---

## STEP 9: Historical Events Seed Data

Create `data/curated/historical_events.yaml` with an initial set of major events.
Use this structure:

```yaml
events:
  - id: "evt:rashidun-caliphate"
    name_en: "Rashidun Caliphate"
    year_start_ah: 11
    year_end_ah: 40
    year_start_ce: 632
    year_end_ce: 661
    type: "caliphate"
    caliphate: "Rashidun"
    region: "Arabia, Levant, Persia, Egypt"
    description: "Rule of the four 'rightly-guided' caliphs: Abu Bakr, Umar, Uthman, Ali."

  - id: "evt:first-fitna"
    name_en: "First Fitna"
    year_start_ah: 35
    year_end_ah: 40
    year_start_ce: 656
    year_end_ce: 661
    type: "fitna"
    caliphate: "Rashidun"
    region: "Iraq, Levant, Arabia"
    description: "Civil war following assassination of Uthman. Battle of the Camel, Siffin, rise of Muawiya."

  - id: "evt:umayyad-caliphate"
    name_en: "Umayyad Caliphate"
    year_start_ah: 41
    year_end_ah: 132
    year_start_ce: 661
    year_end_ce: 750
    type: "caliphate"
    caliphate: "Umayyad"
    region: "Damascus-centered, Iberia to Central Asia"
    description: "Muawiya I through Marwan II. Expansion, Arabization, qadariyya debates."

  - id: "evt:second-fitna"
    name_en: "Second Fitna"
    year_start_ah: 60
    year_end_ah: 73
    year_start_ce: 680
    year_end_ce: 692
    type: "fitna"
    caliphate: "Umayyad"
    region: "Iraq, Hijaz, Levant"
    description: "Husayn's martyrdom at Karbala, Ibn al-Zubayr's counter-caliphate, Mukhtar's revolt."

  - id: "evt:karbala"
    name_en: "Battle of Karbala"
    year_start_ah: 61
    year_end_ah: 61
    year_start_ce: 680
    year_end_ce: 680
    type: "fitna"
    caliphate: "Umayyad"
    region: "Karbala, Iraq"
    description: "Martyrdom of Husayn ibn Ali. Foundational event for Shia identity and hadith transmission."

  - id: "evt:abbasid-revolution"
    name_en: "Abbasid Revolution"
    year_start_ah: 129
    year_end_ah: 132
    year_start_ce: 747
    year_end_ce: 750
    type: "dynasty_transition"
    caliphate: "Umayyad → Abbasid"
    region: "Khurasan, Iraq"
    description: "Overthrow of Umayyads. Abu Muslim's revolt. Shift of power to Baghdad."

  - id: "evt:abbasid-caliphate"
    name_en: "Abbasid Caliphate (Early Period)"
    year_start_ah: 132
    year_end_ah: 334
    year_start_ce: 750
    year_end_ce: 945
    type: "caliphate"
    caliphate: "Abbasid"
    region: "Baghdad-centered"
    description: "Golden age of hadith compilation. Bukhari, Muslim, Abu Dawud, Tirmidhi, Nasa'i, Ibn Majah all compile during this period."

  - id: "evt:mihna"
    name_en: "Mihna (Inquisition)"
    year_start_ah: 218
    year_end_ah: 234
    year_start_ce: 833
    year_end_ce: 848
    type: "theological_controversy"
    caliphate: "Abbasid"
    region: "Baghdad, Iraq"
    description: "Caliph al-Ma'mun enforces Mu'tazili doctrine of created Quran. Ahmad ibn Hanbal's resistance. Major impact on hadith transmission politics."

  - id: "evt:bukhari-compilation"
    name_en: "Compilation of Sahih al-Bukhari"
    year_start_ah: 217
    year_end_ah: 232
    year_start_ce: 832
    year_end_ce: 846
    type: "compilation_effort"
    caliphate: "Abbasid"
    region: "Bukhara, Khurasan"
    description: "Al-Bukhari compiles his Sahih over ~16 years, selecting ~7,563 from ~600,000 candidate hadiths."

  - id: "evt:muslim-compilation"
    name_en: "Compilation of Sahih Muslim"
    year_start_ah: 235
    year_end_ah: 261
    year_start_ce: 850
    year_end_ce: 875
    type: "compilation_effort"
    caliphate: "Abbasid"
    region: "Nishapur, Khurasan"
    description: "Muslim ibn al-Hajjaj compiles his Sahih, selecting ~4,000 from ~300,000 candidates."

  - id: "evt:kulayni-compilation"
    name_en: "Compilation of al-Kafi"
    year_start_ah: 300
    year_end_ah: 329
    year_start_ce: 913
    year_end_ce: 941
    type: "compilation_effort"
    caliphate: "Abbasid (Buyid influence)"
    region: "Baghdad, Iran"
    description: "Al-Kulayni compiles al-Kafi during the Minor Occultation period. ~16,199 narrations. Primary Shia collection."

  - id: "evt:minor-occultation"
    name_en: "Minor Occultation (al-Ghayba al-Sughra)"
    year_start_ah: 260
    year_end_ah: 329
    year_start_ce: 874
    year_end_ce: 941
    type: "theological_controversy"
    caliphate: "Abbasid"
    region: "Iraq, Iran"
    description: "Period of four deputies communicating with the Hidden Imam. Critical context for Shia hadith authentication."
```

Include at least these 12 events. They cover the critical timeline for understanding hadith compilation politics.

---

## STEP 10: Makefile

Create a `Makefile` with these targets:

```makefile
.PHONY: help setup infra infra-down acquire parse resolve load enrich test lint typecheck clean

help:            ## Show this help message
setup:           ## Install dependencies with uv
infra:           ## Start Docker services (Neo4j, PostgreSQL, Redis)
infra-down:      ## Stop Docker services
infra-reset:     ## Stop services and destroy volumes
acquire:         ## Phase 1: Download all data sources
parse:           ## Phase 1: Parse raw data into staging Parquet files
resolve:         ## Phase 2: Entity resolution (NER + disambiguation + dedup)
load:            ## Phase 3: Load graph into Neo4j
enrich:          ## Phase 4: Compute metrics, topics, historical overlay
test:            ## Run pytest suite
lint:            ## Run ruff linter
typecheck:       ## Run mypy type checker
format:          ## Run ruff formatter
clean:           ## Remove staging data and caches
pipeline:        ## Run full pipeline: acquire → parse → resolve → load → enrich
```

Implement `setup`, `infra`, `infra-down`, `infra-reset`, `test`, `lint`, `typecheck`, `format`, and `clean` fully. The Phase 1–4 targets should be stubs that echo "Phase N not yet implemented" until those phases are built.

---

## STEP 11: Minimal CLI Entry Point

Create `src/cli.py` with a simple argparse-based CLI:

```python
def main():
    parser = argparse.ArgumentParser(description="isnad-graph: Hadith Analysis Platform")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("info", help="Show configuration and database status")
    subparsers.add_parser("acquire", help="Download data sources")
    subparsers.add_parser("parse", help="Parse raw data to staging")
    subparsers.add_parser("resolve", help="Entity resolution")
    subparsers.add_parser("load", help="Load graph database")
    subparsers.add_parser("enrich", help="Compute metrics and enrichment")
    subparsers.add_parser("validate", help="Run graph validation queries")

    args = parser.parse_args()

    if args.command == "info":
        # Print settings (redacted passwords) and check DB connectivity
        ...
    else:
        print(f"Command '{args.command}' not yet implemented. See Makefile targets.")
```

The `info` command should instantiate `Settings`, print them (with password fields masked), and attempt to connect to Neo4j and PostgreSQL, printing connection status.

---

## STEP 12: Tests

### tests/conftest.py
- Fixture: `settings` — returns a `Settings` instance with test defaults.
- Fixture: `sample_narrator` — returns a valid `Narrator` instance for testing.
- Fixture: `sample_hadith` — returns a valid `Hadith` instance for testing.

### tests/test_models/test_all_models.py
- Test that each model can be instantiated with valid data.
- Test that each model rejects invalid data (wrong enum values, missing required fields).
- Test that `id` field validators enforce prefix patterns (e.g., `nar:`, `hdt:`, `col:`).
- Test that frozen models raise on mutation.
- Test serialization round-trip: `model.model_dump()` → `Model(**data)`.

### tests/test_utils/test_arabic.py
- Test `strip_diacritics` with known input/output pairs. Include at least:
  - `"بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"` → `"بسم الله الرحمن الرحيم"`
- Test `normalize_alif` with hamza-above, hamza-below, madda variants.
- Test `normalize_arabic` as a full pipeline.
- Test `extract_transmission_phrases` on a known isnad string.
- Test `is_arabic` with Arabic text, English text, and mixed text.

### tests/test_config.py
- Test that `Settings` loads from environment variables.
- Test default values.

---

## STEP 13: README.md

Write a README that includes:
1. Project title and one-paragraph description.
2. Architecture overview (mention Neo4j, PostgreSQL, pgvector).
3. Quick start instructions (clone, `make setup`, `make infra`, `make test`).
4. Phase overview table (Phase 0–5 with status: Phase 0 = ✅, rest = ⬜).
5. Data sources table (name, URL, format, coverage).
6. Directory structure explanation.
7. Development section (linting, testing, type checking).
8. License (MIT).

---

## STEP 14: .gitignore

Standard Python .gitignore plus:
```
data/raw/
data/staging/
*.parquet
.env
__pycache__/
.mypy_cache/
.ruff_cache/
.pytest_cache/
*.egg-info/
dist/
build/
.venv/
node_modules/
```

Do NOT gitignore `data/curated/` — that directory contains manually maintained seed data.

---

## EXECUTION NOTES FOR CLAUDE CODE

1. Create ALL files in a single pass. Do not ask for confirmation between steps.
2. Every Python file must pass `ruff check` and `mypy --strict` (with pydantic plugin).
3. Use absolute imports from `src.` throughout (not relative imports).
4. All Pydantic models must use `ConfigDict(frozen=True)` — immutability is a design decision.
5. The Arabic utility functions must be fully implemented with working regex patterns, not stubs.
6. Tests must be runnable with `pytest` from the repo root.
7. After creating all files, run `ruff check src/ tests/` and `pytest` to verify everything passes.
