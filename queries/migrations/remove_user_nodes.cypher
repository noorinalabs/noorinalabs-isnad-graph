// Migration: Remove USER node indexes and constraints from Neo4j
//
// Context: USER nodes are no longer managed by isnad-graph. User data
// has been migrated to noorinalabs-user-service (PostgreSQL). This
// script drops any remaining indexes/constraints on USER nodes.
//
// After running these statements, manually verify and delete USER nodes:
//   MATCH (u:USER) DETACH DELETE u;
//
// Run each statement individually in the Neo4j Browser or via cypher-shell.

// Drop indexes that may exist on USER node properties
DROP INDEX ix_user_email IF EXISTS;
DROP INDEX ix_user_id IF EXISTS;
DROP INDEX ix_user_provider IF EXISTS;
DROP INDEX ix_user_role IF EXISTS;

// Drop any uniqueness constraints on USER nodes
DROP CONSTRAINT constraint_user_email_unique IF EXISTS;
DROP CONSTRAINT constraint_user_id_unique IF EXISTS;

// Drop SESSION node indexes (sessions are now in Redis)
DROP INDEX ix_session_id IF EXISTS;
DROP INDEX ix_session_user_id IF EXISTS;
DROP CONSTRAINT constraint_session_id_unique IF EXISTS;
