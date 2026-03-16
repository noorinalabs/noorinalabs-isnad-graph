"""Integration test fixtures using testcontainers."""

from __future__ import annotations

import pytest
from testcontainers.neo4j import Neo4jContainer
from testcontainers.postgres import PostgresContainer

from src.utils.neo4j_client import Neo4jClient

NEO4J_TEST_PASSWORD = "testpassword123"


@pytest.fixture(scope="session")
def neo4j_container():
    """Start a real Neo4j container for integration tests."""
    container = Neo4jContainer("neo4j:5-community")
    container.with_env("NEO4J_AUTH", f"neo4j/{NEO4J_TEST_PASSWORD}")
    with container as neo4j:
        yield neo4j


@pytest.fixture
def neo4j_client(neo4j_container):
    """Neo4jClient connected to the test container."""
    client = Neo4jClient(
        uri=neo4j_container.get_connection_url(),
        user="neo4j",
        password=NEO4J_TEST_PASSWORD,
    )
    yield client
    # Clean up: delete all nodes after each test
    client.execute_write("MATCH (n) DETACH DELETE n")
    client.close()


@pytest.fixture(scope="session")
def postgres_container():
    """Start a real PostgreSQL container."""
    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        yield pg


@pytest.fixture
def sample_data_dir(tmp_path):
    """Path to a temporary sample data directory for integration tests."""
    sample_dir = tmp_path / "test_samples"
    sample_dir.mkdir()
    return sample_dir


@pytest.fixture
def clean_staging(tmp_path):
    """Cleanup fixture that empties staging dir between tests."""
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir(exist_ok=True)
    yield staging_dir
    # Cleanup after test
    for f in staging_dir.iterdir():
        if f.is_file():
            f.unlink()
