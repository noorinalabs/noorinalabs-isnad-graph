"""Canonical hadith topic vocabulary.

Hadith documents carry a free-text ``topic_tags`` list (e.g. ``["intentions",
"sincerity"]``, ``["prayer"]``, ``["day_of_judgment"]``). Those tags are sparse
and unnormalized — they come from heterogeneous upstream sources, so the search
page's topic facet was "best-effort": it matched a hardcoded label list against
the raw tags with fuzzy substring logic, which is noisy and drifts from whatever
tags actually exist (isnad-graph#1061).

This module is the single source of truth for the topic facet. It defines a
small, **version-controlled canonical vocabulary** of topic tokens, maps the
free-text tags onto it via keyword groups, and aggregates document counts per
canonical topic. Tags that map to nothing (or hadiths with no tags at all) fall
into the ``uncategorized`` bucket rather than being dropped, so the facet's
counts always sum to the full corpus.

The long-term home for a stored, per-hadith canonical topic is the data layer
(topic classification in the enrich stage — see ``src/enrich/__init__.py`` and
``models.enrich.TopicResult``, tracked as future work). Until that lands, this
keyword mapping is the deterministic bridge between sparse tags and the facet.
The keyword groups deliberately favour transliterations + plain-English glosses
that co-occur in the source tags.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# Canonical token -> human-readable display label. This is THE topic vocabulary:
# adding/removing/renaming a topic is a deliberate, reviewed change to this map.
TOPIC_LABELS: Final[dict[str, str]] = {
    "aqidah": "Theology (Aqidah)",
    "ibadah": "Worship (Ibadah)",
    "fiqh": "Jurisprudence (Fiqh)",
    "akhlaq": "Ethics (Akhlaq)",
    "quran": "Qur'an & Tafsir",
    "sira": "History & Biography (Sira)",
    "knowledge": "Knowledge ('Ilm)",
    "eschatology": "Eschatology",
}

# The bucket for tags that map to no canonical topic (and for hadiths carrying no
# tags at all). Surfaced as a facet so documents are never silently dropped.
UNCATEGORIZED_TOPIC: Final[str] = "uncategorized"
UNCATEGORIZED_LABEL: Final[str] = "Uncategorized"

# Keyword groups: a normalized tag belongs to a canonical topic if its text
# CONTAINS any of the group's substrings. The dict is ordered by match priority —
# ``normalize_topic`` returns the first matching token, so more specific topics
# (eschatology, qur'an, sira) are checked before the broad legal catch-all
# (fiqh). Substrings are lower-cased and apostrophe/underscore-folded to match
# ``_normalize_tag`` output.
_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "eschatology": (
        "eschatolog",
        "hereafter",
        "afterlife",
        "akhirah",
        "akhira",
        "resurrection",
        "judgment",
        "judgement",
        "day of",
        "the hour",
        "signs of the hour",
        "paradise",
        "jannah",
        "hellfire",
        "hell",
        "jahannam",
        "dajjal",
        "antichrist",
        "doomsday",
        "qiyamah",
        "qiyamat",
        "barzakh",
        "the grave",
    ),
    "quran": (
        "quran",
        "koran",
        "tafsir",
        "tafseer",
        "exegesis",
        "revelation",
        "ayah",
        "ayat",
        "verse",
        "surah",
        "sura ",
        "recitation",
        "tilawah",
    ),
    "sira": (
        "sira",
        "seerah",
        "biograph",
        "history",
        "battle",
        "expedition",
        "ghazwa",
        "maghazi",
        "migration",
        "hijra",
        "companion",
        "sahaba",
        "sahabah",
    ),
    "ibadah": (
        "ibadah",
        "ibada",
        "worship",
        "prayer",
        "salah",
        "salat",
        "salaah",
        "fasting",
        "fast",
        "sawm",
        "siyam",
        "ramadan",
        "ablution",
        "wudu",
        "purification",
        "tahara",
        "pilgrimage",
        "hajj",
        "umrah",
        "zakat",
        "zakah",
        "alms",
        "charity",
        "sadaqah",
        "dhikr",
        "supplication",
        "dua",
        "invocation",
        "adhan",
        "azan",
        "mosque",
        "masjid",
    ),
    "aqidah": (
        "aqidah",
        "aqeedah",
        "aqida",
        "theolog",
        "belief",
        "creed",
        "faith",
        "iman",
        "tawhid",
        "tawheed",
        "monotheism",
        "oneness",
        "divine",
        "angel",
        "predestination",
        "qadar",
        "destiny",
    ),
    "akhlaq": (
        "akhlaq",
        "akhlaaq",
        "ethic",
        "moral",
        "manner",
        "character",
        "virtue",
        "sincerity",
        "intention",
        "ikhlas",
        "patience",
        "sabr",
        "honesty",
        "truthfulness",
        "humility",
        "gratitude",
        "kindness",
        "mercy",
        "compassion",
        "forgiveness",
        "repentance",
        "tawbah",
        "backbiting",
        "envy",
        "anger",
        "modesty",
        "haya",
    ),
    "knowledge": (
        "knowledge",
        "ilm",
        "learning",
        "scholar",
        "teaching",
        "education",
        "wisdom",
        "hikmah",
        "student",
    ),
    "fiqh": (
        "fiqh",
        "jurisprudence",
        "law",
        "legal",
        "ruling",
        "hukm",
        "permissible",
        "halal",
        "haram",
        "forbidden",
        "lawful",
        "unlawful",
        "transaction",
        "trade",
        "business",
        "commerce",
        "marriage",
        "nikah",
        "divorce",
        "talaq",
        "inheritance",
        "mirath",
        "contract",
        "oath",
        "vow",
        "punishment",
        "hudud",
        "dietary",
        "food",
        "drink",
        "clothing",
    ),
}

# Canonical tokens in their vocabulary/priority order. Facet output and
# ``canonical_topics_for_tags`` preserve this order for stable presentation.
TOPIC_TOKENS: Final[tuple[str, ...]] = tuple(TOPIC_LABELS.keys())

_WS_RE: Final = re.compile(r"\s+")


@dataclass(frozen=True)
class TopicFacetCount:
    """A canonical topic and the number of documents mapped to it."""

    value: str
    label: str
    count: int


def _normalize_tag(raw: str) -> str:
    """Fold a free-text tag for tolerant keyword matching.

    Lower-cases, replaces underscores/hyphens with spaces (so ``day_of_judgment``
    matches ``"day of"``), drops apostrophe/hamza glyphs, and collapses runs of
    whitespace. Mirrors the frontend ``norm`` helper so both ends agree.
    """
    text = raw.lower().replace("_", " ").replace("-", " ")
    text = re.sub(r"['’ʼʿ`´‘]", "", text)
    return _WS_RE.sub(" ", text).strip()


def normalize_topic(raw: str | None) -> str | None:
    """Map a single free-text topic tag to a canonical token, or ``None``.

    Priority follows ``_KEYWORDS`` insertion order: the first group whose keyword
    is contained in the normalized tag wins. Returns ``None`` for blank input or
    a tag that matches no canonical topic (the caller buckets those as
    :data:`UNCATEGORIZED_TOPIC`).
    """
    if not raw or not raw.strip():
        return None
    text = _normalize_tag(raw)
    if not text:
        return None
    for token, keywords in _KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return token
    return None


def canonical_topics_for_tags(tags: list[str] | None) -> list[str]:
    """Map a hadith's free-text ``topic_tags`` to its distinct canonical tokens.

    Returns the canonical tokens (in :data:`TOPIC_TOKENS` order, de-duplicated)
    that any of ``tags`` resolve to. An empty list means the hadith is
    *uncategorized* — either it has no tags or none of them map onto the
    vocabulary. The empty case is preserved (not coerced to ``uncategorized``) so
    result-level facet matching can keep treating "no topics" as permissive.
    """
    if not tags:
        return []
    matched: set[str] = set()
    for tag in tags:
        token = normalize_topic(tag)
        if token is not None:
            matched.add(token)
    return [t for t in TOPIC_TOKENS if t in matched]


def aggregate_topic_facets(tag_lists: list[list[str] | None]) -> list[TopicFacetCount]:
    """Aggregate per-hadith ``topic_tags`` into canonical topic-facet counts.

    ``tag_lists`` is one entry per hadith (its ``topic_tags``, possibly empty or
    ``None``). A hadith contributes one count to *each* distinct canonical topic
    its tags map to; a hadith that maps to no topic contributes to the
    ``uncategorized`` bucket. Document counts therefore sum to at least the corpus
    size (a multi-topic hadith is counted under each of its topics).

    The full canonical vocabulary is always returned in :data:`TOPIC_TOKENS`
    order — including zero-count topics — so the facet presents a stable
    vocabulary independent of how sparse the underlying tags are. The
    ``uncategorized`` bucket is always appended last.
    """
    counts: dict[str, int] = {token: 0 for token in TOPIC_TOKENS}
    uncategorized = 0
    for tags in tag_lists:
        tokens = canonical_topics_for_tags(tags)
        if not tokens:
            uncategorized += 1
            continue
        for token in tokens:
            counts[token] += 1

    facets = [
        TopicFacetCount(value=token, label=TOPIC_LABELS[token], count=counts[token])
        for token in TOPIC_TOKENS
    ]
    facets.append(
        TopicFacetCount(value=UNCATEGORIZED_TOPIC, label=UNCATEGORIZED_LABEL, count=uncategorized)
    )
    return facets
