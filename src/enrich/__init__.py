"""Phase 4 enrichment stage.

The enrich stage runs *after* the graph load and adds derived structure on top
of the loaded nodes: graph metrics, topic classification, and the historical
overlay. Only the historical overlay (``ACTIVE_DURING`` edge creation plus the
``HistoricalEvent`` reference-node load) is implemented in this repo today;
metrics (Neo4j GDS) and topic classification are tracked as future work.
"""

from __future__ import annotations

from src.enrich.historical import (
    compute_active_during,
    default_events_path,
    event_to_graph_props,
    load_events_from_yaml,
    run_historical_overlay,
)

__all__ = [
    "compute_active_during",
    "default_events_path",
    "event_to_graph_props",
    "load_events_from_yaml",
    "run_historical_overlay",
]
