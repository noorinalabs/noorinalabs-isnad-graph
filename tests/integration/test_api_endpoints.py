"""Integration tests for API endpoints against a real Neo4j container."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.middleware import require_auth
from src.auth.models import User
from src.utils.neo4j_client import Neo4jClient

pytestmark = pytest.mark.integration


@pytest.fixture
def _seed_data(neo4j_client: Neo4jClient) -> None:
    """Load sample data into Neo4j for API tests."""
    neo4j_client.ensure_constraints()

    # Create narrators
    neo4j_client.execute_write_batch(
        """
        UNWIND $batch AS row
        MERGE (n:Narrator {id: row.id})
        SET n.name_ar = row.name_ar,
            n.name_en = row.name_en,
            n.generation = row.generation,
            n.death_year_ah = row.death_year_ah,
            n.gender = row.gender,
            n.sect_affiliation = row.sect_affiliation,
            n.trustworthiness_consensus = row.trustworthiness_consensus
        """,
        [
            {
                "id": "nar:001",
                "name_ar": "أبو هريرة",
                "name_en": "Abu Hurayrah",
                "generation": "sahabi",
                "death_year_ah": 59,
                "gender": "male",
                "sect_affiliation": "sunni",
                "trustworthiness_consensus": "thiqa",
            },
            {
                "id": "nar:002",
                "name_ar": "مالك بن أنس",
                "name_en": "Malik ibn Anas",
                "generation": "tabii",
                "death_year_ah": 179,
                "gender": "male",
                "sect_affiliation": "sunni",
                "trustworthiness_consensus": "thiqa",
            },
        ],
    )

    # Create hadiths
    neo4j_client.execute_write_batch(
        """
        UNWIND $batch AS row
        MERGE (h:Hadith {id: row.id})
        SET h.matn_ar = row.matn_ar,
            h.matn_en = row.matn_en,
            h.grade = row.grade,
            h.source_corpus = row.source_corpus,
            h.sect = row.sect,
            h.collection_name = row.collection_name
        """,
        [
            {
                "id": "hdt:bukhari:1",
                "matn_ar": "إنما الأعمال بالنيات",
                "matn_en": "Actions are judged by intentions",
                "grade": "sahih",
                "source_corpus": "sunnah",
                "sect": "sunni",
                "collection_name": "bukhari",
            },
            {
                "id": "hdt:bukhari:2",
                "matn_ar": "بني الإسلام على خمس",
                "matn_en": "Islam is built on five pillars",
                "grade": "sahih",
                "source_corpus": "sunnah",
                "sect": "sunni",
                "collection_name": "bukhari",
            },
        ],
    )

    # Create collections
    neo4j_client.execute_write_batch(
        """
        UNWIND $batch AS row
        MERGE (c:Collection {id: row.id})
        SET c.name_en = row.name_en,
            c.name_ar = row.name_ar,
            c.sect = row.sect
        """,
        [
            {
                "id": "col:bukhari",
                "name_en": "Sahih al-Bukhari",
                "name_ar": "صحيح البخاري",
                "sect": "sunni",
            },
        ],
    )


def _integration_user() -> User:
    return User(
        id="test-integration-user",
        email="integration@test.com",
        name="Integration Test User",
        provider="google",
        provider_user_id="test-integration-user",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def api_client(neo4j_client: Neo4jClient, _seed_data: None) -> TestClient:
    """FastAPI TestClient backed by a real Neo4j container."""
    app = create_app()
    app.state.neo4j = neo4j_client
    app.dependency_overrides[require_auth] = _integration_user
    return TestClient(
        app,
        raise_server_exceptions=False,
    )


class TestNarratorsEndpoint:
    """Test /api/v1/narrators against real data."""

    def test_list_narrators(self, api_client: TestClient) -> None:
        resp = api_client.get("/api/v1/narrators")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_get_narrator_by_id(self, api_client: TestClient) -> None:
        resp = api_client.get("/api/v1/narrators/nar:001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "nar:001"
        assert data["name_en"] == "Abu Hurayrah"

    def test_get_narrator_not_found(self, api_client: TestClient) -> None:
        resp = api_client.get("/api/v1/narrators/nar:nonexistent")
        assert resp.status_code == 404


class TestHadithsEndpoint:
    """Test /api/v1/hadiths against real data."""

    def test_list_hadiths(self, api_client: TestClient) -> None:
        resp = api_client.get("/api/v1/hadiths")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_get_hadith_by_id(self, api_client: TestClient) -> None:
        resp = api_client.get("/api/v1/hadiths/hdt:bukhari:1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "hdt:bukhari:1"
        assert "intentions" in data["matn_en"]

    def test_get_hadith_not_found(self, api_client: TestClient) -> None:
        resp = api_client.get("/api/v1/hadiths/hdt:nonexistent")
        assert resp.status_code == 404


class TestSearchEndpoint:
    """Test /api/v1/search against real data."""

    def test_search_by_narrator_name(self, api_client: TestClient) -> None:
        resp = api_client.get("/api/v1/search", params={"q": "Abu Hurayrah"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        ids = [r["id"] for r in data["results"]]
        assert "nar:001" in ids

    def test_search_by_hadith_text(self, api_client: TestClient) -> None:
        resp = api_client.get("/api/v1/search", params={"q": "intentions"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_search_empty_results(self, api_client: TestClient) -> None:
        resp = api_client.get("/api/v1/search", params={"q": "zzz_nonexistent_zzz"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
