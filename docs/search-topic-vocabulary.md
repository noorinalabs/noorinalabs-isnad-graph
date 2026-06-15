# Search topic facet — canonical vocabulary

The search/hadith **topic facet** filters hadiths by subject. Hadith documents
carry a free-text `topic_tags` list that is sparse and unnormalized (it comes
from heterogeneous upstream sources), so the facet used to be "best-effort": a
hardcoded label list fuzzy-matched against whatever tags happened to exist. That
was noisy, incomplete, and drifted from the data (isnad-graph#1061).

This document describes the canonical vocabulary that replaced it.

## Single source of truth

`src/utils/topics.py` is the **only** place the vocabulary is defined. Adding,
removing, or renaming a topic is a deliberate edit to `TOPIC_LABELS` there. Both
the backend facet aggregation and the frontend facet UI consume that one
definition — the frontend never hardcodes topic labels; it reads them from the
API (`/api/v1/hadiths/facets`).

## Canonical topics

| Token | Display label |
|-------|---------------|
| `aqidah` | Theology (Aqidah) |
| `ibadah` | Worship (Ibadah) |
| `fiqh` | Jurisprudence (Fiqh) |
| `akhlaq` | Ethics (Akhlaq) |
| `quran` | Qur'an & Tafsir |
| `sira` | History & Biography (Sira) |
| `knowledge` | Knowledge ('Ilm) |
| `eschatology` | Eschatology |
| `uncategorized` | Uncategorized (synthetic bucket) |

## How tags map onto the vocabulary

`normalize_topic(tag)` folds a free-text tag (lowercase, underscore/hyphen →
space, apostrophe-stripped) and returns the first canonical token whose keyword
group matches a substring of it, or `None`. The keyword groups (`_KEYWORDS`) are
ordered by priority, so specific topics (eschatology, qur'an, sira) are checked
before the broad legal catch-all (fiqh).

- A hadith maps to the **distinct set** of canonical tokens its tags resolve to
  (a hadith can appear under several topics).
- A hadith whose tags resolve to **nothing** — or that carries no tags at all —
  falls into the `uncategorized` bucket. Documents are never dropped, so the
  facet counts always cover the full corpus.

## API & UI surface

- `GET /api/v1/hadiths/facets` returns `topics: [{value, label, count}]`. The
  **full** vocabulary is always returned (including zero-count topics) so the
  facet is stable regardless of how sparse the tags are; the `uncategorized`
  bucket is always appended last.
- Search results (`GET /api/v1/search`) carry `topics` as the canonical tokens
  the hadith maps onto, so the search page's client-side filtering matches on a
  stable token set rather than fuzzy substrings. An empty `topics` is treated
  permissively (kept visible under any filter) so tag-less hadiths and semantic
  hits don't disappear; selecting only the `uncategorized` bucket isolates them.

## Follow-up — denser, source-of-truth topics

The keyword mapping is a deterministic bridge over the *currently sparse* tags.
The durable improvement is upstream: real per-hadith topic classification in the
enrich stage (see `src/enrich/__init__.py` and `models.enrich.TopicResult`,
tracked as future work). When that lands, hadiths would carry a stored canonical
topic and this module would normalize/validate against the same vocabulary
rather than infer it from sparse tags. Densifying `topic_tags` is therefore a
**data/ingest follow-up**, out of scope for the facet itself.
