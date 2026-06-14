"""Phase 4 enrichment stage.

The enrich stage runs *after* the graph load and adds derived structure on top
of the loaded nodes: graph metrics, topic classification, and the historical
overlay. The historical overlay (``ACTIVE_DURING`` edge creation plus the
``HistoricalEvent`` reference-node load) and the semantic-search embedding load
(hadith vectors → pgvector) are implemented in this repo today; metrics
(Neo4j GDS) and topic classification are tracked as future work.
"""

from __future__ import annotations

from src.enrich.embeddings import (
    EMBEDDING_DIM,
    Embedder,
    HashingEmbedder,
    ensure_embedding_schema,
    get_embedder,
    run_embedding_load,
    to_pgvector_literal,
)
from src.enrich.historical import (
    compute_active_during,
    default_events_path,
    event_to_graph_props,
    load_events_from_yaml,
    run_historical_overlay,
)

__all__ = [
    "EMBEDDING_DIM",
    "Embedder",
    "HashingEmbedder",
    "compute_active_during",
    "default_events_path",
    "ensure_embedding_schema",
    "event_to_graph_props",
    "get_embedder",
    "load_events_from_yaml",
    "run_embedding_load",
    "run_historical_overlay",
    "to_pgvector_literal",
]
