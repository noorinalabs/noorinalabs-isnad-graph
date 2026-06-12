# Historical Overlay Runbook

How to populate `HistoricalEvent` nodes and `ACTIVE_DURING` narrator links in a
deployed graph. This is the enrich-stage step behind isnad-graph#965 — without it
the "Historical Events / Narrator Activity" timeline panel renders empty.

## What it does

`isnad enrich-historical` (→ `src.enrich.historical.run_historical_overlay`):

1. Loads the curated event set from `data/curated/historical_events.yaml`, mapping
   the curated field names (`name_en` / `year_start_ah` / `type`) onto the graph
   property names the `/timeline` API reads (`name` / `year_ah` / `event_type`).
   See `event_to_graph_props` — it is the single schema bridge.
2. `MERGE`s one `HistoricalEvent` node per event (idempotent, keyed on `id`).
3. Reads every `Narrator` and links it `ACTIVE_DURING` each event whose date range
   overlaps the narrator's lifespan. Edges are `MERGE`d bare (no properties in the
   pattern) to avoid the null-property-in-MERGE loader bug (main#139).

### Lifespan heuristic

A narrator's active window is `[birth_year_ah, death_year_ah]`. Hadith biographies
reliably record the death year but rarely the birth year, so when one end is
missing it is estimated using `DEFAULT_ASSUMED_LIFESPAN_AH` (80 Hijri years). A
narrator with neither year is skipped (`narrators_skipped_no_dates`); a narrator
whose two known years span more than `MAX_NARRATOR_LIFETIME_AH` (120) is treated as
bad data and skipped (`narrators_skipped_max_lifetime`). Both counts are reported.

## Running it

### Local / CI (no live DB)

Unit-tested without Docker:

```bash
ENVIRONMENT=test uv run pytest tests/test_enrich/test_historical.py
```

The pure overlap logic (`compute_active_during`) and the YAML→graph-prop mapping
are fully covered against a fake client.

### Deferred live leg — staging

> Requires the staging Neo4j, which is only reachable from inside the cluster
> (`bolt://neo4j:7687` does not resolve from the dev sandbox — main#631 / no local
> Docker). Run from inside the deployed app container where `NEO4J_URI` resolves.

```bash
ssh noorinalabs-stg
# from the host, exec into the isnad-graph api/worker container:
docker exec -it <isnad-graph-container> uv run isnad enrich-historical
```

Expected output (counts depend on how many narrators are loaded — see #963):

```
=== historical overlay complete ===
  events linked          : <n>
  narrators linked       : <n>
  ACTIVE_DURING edges    : <n>
  skipped (no dates)     : <n>
  skipped (max lifetime) : <n>
```

`events linked` reflects events that gained at least one narrator edge; the event
nodes themselves are always loaded (13 in the curated set today), so the panel
renders even when zero narrators are present yet.

### Verify

```cypher
MATCH (e:HistoricalEvent) RETURN count(e);                       // expect >= 13
MATCH (:Narrator)-[r:ACTIVE_DURING]->(:HistoricalEvent) RETURN count(r);
```

Then reload the Timeline page — events should appear with per-event narrator counts.

## Notes / follow-ups

- This implements only the **historical overlay** sub-step of the Phase-4 enrich
  stage. Graph metrics (Neo4j GDS) and topic classification (`EnrichSummary.metrics`
  / `.topics`) are separate, unimplemented enrich sub-steps and out of scope here.
- `ACTIVE_DURING` coverage scales with narrator data. Until richer narrator bios
  land (#963 / da#81), many narrators will be skipped as `no_dates`; the event
  nodes load regardless, which is what unblocks the empty panel.
