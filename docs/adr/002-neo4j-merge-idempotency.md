# ADR-002: Use MERGE for idempotent graph loading

## Status: Accepted (Phase 3)

## Context
The ETL pipeline must be safe to re-run at any point. If a load step fails partway through, re-running it should not create duplicate nodes or relationships in Neo4j.

## Decision
All Neo4j node and relationship creation uses Cypher `MERGE` (not `CREATE`) keyed on stable identifiers derived from source data.

## Consequences
- Pipeline is fully idempotent — safe to re-run after failures
- Slightly slower than CREATE due to existence checks, but acceptable for batch loads
- Requires careful design of merge keys (composite keys for relationships)
- Updates to existing nodes happen via MERGE + SET, preserving graph integrity
