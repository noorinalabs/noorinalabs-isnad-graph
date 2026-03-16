# ADR-004: Web scraper over API for sunnah.com

## Status: Accepted (Phase 1)

## Context
Sunnah.com provides a REST API, but it has rate limits, incomplete coverage of some collections, and inconsistent availability. We needed reliable, complete access to hadith text and metadata for all target collections.

## Decision
Implement a web scraper as the primary acquisition method for sunnah.com data, with the API as a fallback for structured metadata.

## Consequences
- More complete data coverage than the API alone
- Scraper requires maintenance if sunnah.com changes its HTML structure
- Must implement polite scraping (rate limiting, respecting robots.txt)
- Raw HTML parsing adds complexity but gives access to full hadith text with Arabic diacritics preserved
- API remains available for supplementary metadata queries
