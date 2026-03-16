# ADR-001: Use PyArrow as intermediate staging format

## Status: Accepted (Phase 1)

## Context
We needed an intermediate format between raw source files and Neo4j graph nodes. Raw sources arrive in CSV, JSON, and REST API responses with inconsistent schemas. Loading directly into Neo4j would couple the graph schema to source format quirks.

## Decision
Use PyArrow Parquet files with explicit schemas as the staging format between raw acquisition and graph loading.

## Consequences
- Columnar format efficient for large datasets
- Schema validation at write time catches issues early
- Decouples raw format quirks from graph loading
- Requires defining PyArrow schemas that mirror Pydantic models
- Adds a disk-based intermediate step (acceptable for batch processing)
