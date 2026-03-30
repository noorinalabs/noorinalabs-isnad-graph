"""Scrape Wikipedia Timeline of Islam pages for historical events.

Extracts structured event data from the main timeline page and
century-specific sub-pages (7th–15th century CE).  Outputs YAML to
``data/curated/historical_events.yaml`` preserving the existing schema
so that ``src/graph/load_nodes.py`` can load events without changes.

Usage::

    uv run python scripts/scrape_islamic_timeline.py
    uv run python scripts/scrape_islamic_timeline.py --centuries 7 8 9
    uv run python scripts/scrape_islamic_timeline.py --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import math
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import yaml
from bs4 import BeautifulSoup, Tag

# ---------------------------------------------------------------------------
# CE ↔ AH conversion
# ---------------------------------------------------------------------------

# The Islamic (Hijri) calendar started on 16 July 622 CE.
# The calendar is lunar (~354.36667 days/year vs ~365.25 for Gregorian).

_HIJRI_EPOCH_CE = 622
_ISLAMIC_YEAR_DAYS = 354.36667
_GREGORIAN_YEAR_DAYS = 365.25


def ce_to_ah(ce_year: int) -> int:
    """Convert a Common Era year to an approximate Hijri year.

    Uses the standard astronomical approximation.  Accurate to ±1 year
    for the 7th–15th century range relevant to hadith scholarship.
    """
    if ce_year < _HIJRI_EPOCH_CE:
        return 0  # pre-Islamic
    return math.floor((ce_year - _HIJRI_EPOCH_CE) * (_GREGORIAN_YEAR_DAYS / _ISLAMIC_YEAR_DAYS)) + 1


def ah_to_ce(ah_year: int) -> int:
    """Convert a Hijri year to an approximate Common Era year."""
    return math.floor(ah_year * (_ISLAMIC_YEAR_DAYS / _GREGORIAN_YEAR_DAYS) + _HIJRI_EPOCH_CE)


# ---------------------------------------------------------------------------
# Event categorization
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "caliphate": [
        "caliph",
        "caliphate",
        "succession",
        "inaugurated",
        "proclaimed",
        "abdicate",
    ],
    "fitna": [
        "fitna",
        "civil war",
        "revolt",
        "rebellion",
        "uprising",
        "assassination",
        "murdered",
        "killed",
        "martyr",
        "karbala",
    ],
    "conquest": [
        "conquest",
        "capture",
        "siege",
        "conquer",
        "fall of",
        "invasion",
        "annex",
        "occupy",
        "expedition",
    ],
    "compilation_effort": [
        "compil",
        "hadith",
        "sahih",
        "sunan",
        "musnad",
        "wrote",
        "author",
        "book",
        "scholar",
        "jurisprud",
        "fiqh",
        "school",
        "madhhab",
    ],
    "theological_controversy": [
        "mutazil",
        "ashari",
        "theology",
        "creed",
        "doctrine",
        "mihna",
        "inquisition",
        "heresy",
        "debate",
    ],
    "dynasty_transition": [
        "dynasty",
        "overthrow",
        "revolution",
        "founded",
        "established",
        "umayyad",
        "abbasid",
        "fatimid",
        "ayyubid",
        "mamluk",
        "seljuk",
        "ottoman",
    ],
    "persecution": [
        "persecution",
        "massacre",
        "pogrom",
        "exile",
        "expulsion",
    ],
}

# Priority order when multiple categories match
_CATEGORY_PRIORITY = [
    "fitna",
    "conquest",
    "dynasty_transition",
    "caliphate",
    "theological_controversy",
    "compilation_effort",
    "persecution",
]


def categorize_event(description: str) -> str:
    """Assign a HistoricalEventType category based on keyword matching."""
    desc_lower = description.lower()
    scores: dict[str, int] = {}
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in desc_lower)
        if score > 0:
            scores[cat] = score
    if not scores:
        return "conquest"  # default for military/political events
    # Tie-break by priority order
    max_score = max(scores.values())
    for cat in _CATEGORY_PRIORITY:
        if scores.get(cat, 0) == max_score:
            return cat
    return max(scores, key=lambda k: scores[k])


# ---------------------------------------------------------------------------
# Wikipedia scraping
# ---------------------------------------------------------------------------

_BASE_URL = "https://en.wikipedia.org"
_MAIN_PAGE = "/wiki/Timeline_of_the_history_of_Islam"
_CENTURY_TEMPLATE = "/wiki/Timeline_of_the_history_of_Islam_({century}_century)"

_USER_AGENT = (
    "isnad-graph/0.1 (https://github.com/parametrization/isnad-graph; "
    "educational research) Python/httpx"
)
_REQUEST_DELAY = 1.0  # seconds between requests

# Match year(s) at the start of a list item: "622", "622–632", "c. 750"
_YEAR_PATTERN = re.compile(
    r"^(?:c\.?\s*)?(\d{3,4})"  # first year
    r"(?:\s*[–—\-/]\s*(?:c\.?\s*)?(\d{3,4}))?"  # optional second year
)

_CENTURY_NAMES = {
    6: "6th",
    7: "7th",
    8: "8th",
    9: "9th",
    10: "10th",
    11: "11th",
    12: "12th",
    13: "13th",
    14: "14th",
    15: "15th",
}


def _make_event_id(ce_year: int, description: str) -> str:
    """Generate a deterministic event ID from year and description."""
    slug = re.sub(r"[^a-z0-9]+", "-", description[:60].lower()).strip("-")
    # Add a short hash to avoid collisions
    h = hashlib.sha256(f"{ce_year}:{description}".encode()).hexdigest()[:6]
    return f"evt:wiki-{ce_year}-{slug}-{h}"


def _clean_text(text: str) -> str:
    """Clean scraped text: normalize whitespace, strip footnote references."""
    text = re.sub(r"\[(?:citation needed|\d+|a-z)\]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Remove trailing period duplication
    text = re.sub(r"\.\.+$", ".", text)
    return text


def _extract_events_from_list_items(
    soup: BeautifulSoup,
    source_url: str,
) -> list[dict[str, Any]]:
    """Extract events from <li> elements in a Wikipedia timeline page."""
    events: list[dict[str, Any]] = []

    # Find all list items in the main content area
    content = soup.find("div", {"class": "mw-parser-output"})
    if not content:
        return events

    assert isinstance(content, Tag)
    for li in content.find_all("li", recursive=True):
        # Skip items inside navigation, references, or table of contents
        parent_classes = " ".join(
            c for p in li.parents if isinstance(p, Tag) for c in (p.get("class") or [])
        )
        if any(
            skip in parent_classes
            for skip in ["reflist", "toc", "navbox", "sidebar", "mw-references"]
        ):
            continue

        text = _clean_text(li.get_text())
        if len(text) < 10:
            continue

        match = _YEAR_PATTERN.match(text)
        if not match:
            continue

        year_start_ce = int(match.group(1))
        year_end_ce = int(match.group(2)) if match.group(2) else year_start_ce

        # Skip events outside Islamic history range
        if year_start_ce < 570 or year_start_ce > 1500:
            continue

        # Extract description: everything after the year(s) and separators
        desc_start = match.end()
        description = text[desc_start:].lstrip(" –—-:,")
        description = _clean_text(description)

        if len(description) < 5:
            continue

        # Strip leading date fragments (e.g., "9 September – ")
        description = re.sub(
            r"^(?:\d{1,2}\s+\w+\s*[–—-]\s*(?:\d{1,2}\s+\w+\s*[–—-]\s*)?)",
            "",
            description,
        ).strip(" –—-")

        year_start_ah = ce_to_ah(year_start_ce)
        year_end_ah = ce_to_ah(year_end_ce)
        category = categorize_event(description)

        events.append(
            {
                "id": _make_event_id(year_start_ce, description),
                "name_en": description[:120] if len(description) > 120 else description,
                "year_start_ah": year_start_ah,
                "year_end_ah": year_end_ah,
                "year_start_ce": year_start_ce,
                "year_end_ce": year_end_ce,
                "type": category,
                "description": description,
                "source_url": source_url,
            }
        )

    return events


def fetch_page(client: httpx.Client, path: str) -> BeautifulSoup:
    """Fetch a Wikipedia page and return parsed BeautifulSoup."""
    url = f"{_BASE_URL}{path}"
    resp = client.get(url)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def scrape_timeline(
    centuries: list[int] | None = None,
    delay: float = _REQUEST_DELAY,
) -> list[dict[str, Any]]:
    """Scrape Wikipedia Timeline of Islam pages and return event dicts.

    Parameters
    ----------
    centuries
        Which century pages to scrape (default: 7–15 for hadith relevance).
    delay
        Seconds to wait between HTTP requests (respects Wikipedia rate limits).
    """
    if centuries is None:
        centuries = list(range(7, 16))  # 7th through 15th century

    all_events: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    headers = {"User-Agent": _USER_AGENT}

    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        # 1. Scrape main overview page
        print(f"Fetching main timeline page: {_MAIN_PAGE}")
        soup = fetch_page(client, _MAIN_PAGE)
        main_events = _extract_events_from_list_items(soup, f"{_BASE_URL}{_MAIN_PAGE}")
        for evt in main_events:
            if evt["id"] not in seen_ids:
                seen_ids.add(evt["id"])
                all_events.append(evt)
        print(f"  -> {len(main_events)} events from main page")

        time.sleep(delay)

        # 2. Scrape century-specific pages
        for century in centuries:
            name = _CENTURY_NAMES.get(century, f"{century}th")
            path = _CENTURY_TEMPLATE.format(century=name)
            print(f"Fetching {name} century page: {path}")
            try:
                soup = fetch_page(client, path)
                century_events = _extract_events_from_list_items(soup, f"{_BASE_URL}{path}")
                new_count = 0
                for evt in century_events:
                    if evt["id"] not in seen_ids:
                        seen_ids.add(evt["id"])
                        all_events.append(evt)
                        new_count += 1
                print(f"  -> {len(century_events)} events ({new_count} new)")
            except httpx.HTTPStatusError as e:
                print(f"  -> SKIPPED (HTTP {e.response.status_code})", file=sys.stderr)

            time.sleep(delay)

    # Sort by year
    all_events.sort(key=lambda e: (e["year_start_ce"], e.get("year_end_ce", 0)))
    return all_events


# ---------------------------------------------------------------------------
# YAML output
# ---------------------------------------------------------------------------


def _merge_with_existing(
    new_events: list[dict[str, Any]],
    existing_path: Path,
) -> list[dict[str, Any]]:
    """Merge new scraped events with existing curated events.

    Existing hand-curated events (non-wiki IDs) are preserved.
    Wiki-sourced events are replaced with the fresh scrape.
    """
    if not existing_path.exists():
        return new_events

    with open(existing_path) as f:
        data = yaml.safe_load(f) or {}

    existing = data.get("events", [])
    # Keep non-wiki events (hand-curated)
    curated = [e for e in existing if not e.get("id", "").startswith("evt:wiki-")]
    curated_ids = {e["id"] for e in curated}

    # Also keep wiki events that don't conflict
    merged = list(curated)
    for evt in new_events:
        if evt["id"] not in curated_ids:
            merged.append(evt)

    merged.sort(key=lambda e: (e.get("year_start_ce", 0), e.get("year_end_ce", 0)))
    return merged


def write_events_yaml(
    events: list[dict[str, Any]],
    output_path: Path,
    *,
    merge: bool = True,
) -> None:
    """Write events to YAML file, optionally merging with existing data."""
    if merge:
        events = _merge_with_existing(events, output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove source_url from YAML output (not part of Neo4j schema)
    yaml_events = []
    for evt in events:
        entry: dict[str, Any] = {
            "id": evt["id"],
            "name_en": evt["name_en"],
            "year_start_ah": evt["year_start_ah"],
            "year_end_ah": evt["year_end_ah"],
            "year_start_ce": evt["year_start_ce"],
            "year_end_ce": evt["year_end_ce"],
            "type": evt["type"],
        }
        if evt.get("caliphate"):
            entry["caliphate"] = evt["caliphate"]
        if evt.get("region"):
            entry["region"] = evt["region"]
        if evt.get("description"):
            entry["description"] = evt["description"]
        if evt.get("source_url"):
            entry["source_url"] = evt["source_url"]
        yaml_events.append(entry)

    data = {"events": yaml_events}

    with open(output_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)

    print(f"\nWrote {len(yaml_events)} events to {output_path}")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def print_report(events: list[dict[str, Any]]) -> None:
    """Print event count and category distribution."""
    print(f"\n{'=' * 60}")
    print("Historical Events Report")
    print(f"{'=' * 60}")
    print(f"Total events: {len(events)}")

    # Category distribution
    cats: dict[str, int] = {}
    for evt in events:
        cat = evt.get("type", "unknown")
        cats[cat] = cats.get(cat, 0) + 1
    print("\nCategory distribution:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat:<30s} {count:>4d}")

    # Century distribution
    centuries: dict[str, int] = {}
    for evt in events:
        ce = evt.get("year_start_ce", 0)
        c = f"{ce // 100 + 1}th century"
        centuries[c] = centuries.get(c, 0) + 1
    print("\nCentury distribution:")
    for century, count in sorted(centuries.items()):
        print(f"  {century:<30s} {count:>4d}")

    # Date range
    if events:
        min_ce = min(e.get("year_start_ce", 9999) for e in events)
        max_ce = max(e.get("year_end_ce", 0) or e.get("year_start_ce", 0) for e in events)
        print(f"\nDate range: {min_ce} CE – {max_ce} CE")
        print(f"           {ce_to_ah(min_ce)} AH – {ce_to_ah(max_ce)} AH")
    print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Wikipedia Timeline of Islam for historical events."
    )
    parser.add_argument(
        "--centuries",
        nargs="+",
        type=int,
        default=None,
        help="Century numbers to scrape (default: 7-15)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/curated/historical_events.yaml"),
        help="Output YAML path (default: data/curated/historical_events.yaml)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=_REQUEST_DELAY,
        help="Delay between HTTP requests in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Overwrite existing file instead of merging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and report but don't write output file",
    )
    args = parser.parse_args()

    events = scrape_timeline(centuries=args.centuries, delay=args.delay)
    print_report(events)

    if not args.dry_run:
        write_events_yaml(events, args.output, merge=not args.no_merge)


if __name__ == "__main__":
    main()
