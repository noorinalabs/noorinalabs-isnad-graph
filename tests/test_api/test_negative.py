"""Negative and boundary tests for API endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient


class TestNegativeInputs:
    """Test that invalid inputs are rejected with appropriate error codes."""

    def test_invalid_pagination_page_zero(self, client: TestClient) -> None:
        """page=0 should fail validation (ge=1)."""
        resp = client.get("/api/v1/narrators?page=0")
        assert resp.status_code == 422

    def test_invalid_pagination_negative_page(self, client: TestClient) -> None:
        """page=-1 should fail validation."""
        resp = client.get("/api/v1/narrators?page=-1")
        assert resp.status_code == 422

    def test_invalid_pagination_huge_limit(self, client: TestClient) -> None:
        """limit=10000 should fail validation (le=100)."""
        resp = client.get("/api/v1/narrators?limit=10000")
        assert resp.status_code == 422

    def test_invalid_pagination_limit_zero(self, client: TestClient) -> None:
        """limit=0 should fail validation (ge=1)."""
        resp = client.get("/api/v1/hadiths?limit=0")
        assert resp.status_code == 422

    def test_invalid_pagination_limit_negative(self, client: TestClient) -> None:
        """limit=-5 should fail validation."""
        resp = client.get("/api/v1/hadiths?limit=-5")
        assert resp.status_code == 422

    def test_narrator_id_with_special_chars(self, client: TestClient) -> None:
        """Special characters in narrator ID should return 404, not 500."""
        resp = client.get("/api/v1/narrators/<script>alert(1)</script>")
        assert resp.status_code == 404

    def test_narrator_id_with_sql_injection(self, client: TestClient) -> None:
        """SQL-like injection in narrator ID should return 404."""
        resp = client.get("/api/v1/narrators/' OR 1=1 --")
        assert resp.status_code == 404

    def test_search_empty_query(self, client: TestClient) -> None:
        """Empty search query should fail min_length=1 validation."""
        resp = client.get("/api/v1/search?q=")
        assert resp.status_code == 422

    def test_search_missing_query(self, client: TestClient) -> None:
        """Missing q parameter should fail as required."""
        resp = client.get("/api/v1/search")
        assert resp.status_code == 422

    def test_search_very_long_query(self, client: TestClient) -> None:
        """Query exceeding max_length=500 should fail validation."""
        long_q = "a" * 501
        resp = client.get(f"/api/v1/search?q={long_q}")
        assert resp.status_code == 422

    def test_hadith_id_nonexistent(self, client: TestClient) -> None:
        """Nonexistent hadith ID returns 404 with descriptive message."""
        resp = client.get("/api/v1/hadiths/does-not-exist-999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_narrator_id_nonexistent(self, client: TestClient) -> None:
        """Nonexistent narrator ID returns 404."""
        resp = client.get("/api/v1/narrators/does-not-exist-999")
        assert resp.status_code == 404

    def test_pagination_non_integer_page(self, client: TestClient) -> None:
        """Non-integer page should fail validation."""
        resp = client.get("/api/v1/narrators?page=abc")
        assert resp.status_code == 422

    def test_pagination_non_integer_limit(self, client: TestClient) -> None:
        """Non-integer limit should fail validation."""
        resp = client.get("/api/v1/hadiths?limit=xyz")
        assert resp.status_code == 422


class TestBoundaryConditions:
    """Test boundary conditions with mocked database responses."""

    def test_single_narrator_in_database(self, client: TestClient, mock_neo4j: MagicMock) -> None:
        """Database with exactly one narrator returns it correctly."""
        narrator_props = {
            "id": "nar-only",
            "name_ar": "محمد",
            "name_en": "Muhammad",
            "generation": "sahabi",
            "gender": "male",
            "sect_affiliation": "sunni",
            "trustworthiness_consensus": "thiqah",
        }
        mock_neo4j.execute_read.side_effect = [
            [{"total": 1}],
            [{"props": narrator_props}],
        ]
        resp = client.get("/api/v1/narrators")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["id"] == "nar-only"

    def test_empty_database(self, client: TestClient, mock_neo4j: MagicMock) -> None:
        """Empty database returns empty paginated response."""
        mock_neo4j.execute_read.return_value = []
        resp = client.get("/api/v1/narrators")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    def test_narrator_with_no_chains(self, client: TestClient, mock_neo4j: MagicMock) -> None:
        """Narrator with no chains returns empty chains list."""
        mock_neo4j.execute_read.side_effect = [
            [{"id": "nar-lonely"}],  # narrator exists
            [],  # no chains
        ]
        resp = client.get("/api/v1/graph/narrator/nar-lonely/chains")
        assert resp.status_code == 200
        body = resp.json()
        assert body["chains"] == []
        assert body["total"] == 0

    def test_hadith_with_no_parallels(self, client: TestClient, mock_neo4j: MagicMock) -> None:
        """Hadith chain visualization with no edges returns empty lists."""
        mock_neo4j.execute_read.side_effect = [
            [{"id": "hdt-lonely"}],  # hadith exists
            [],  # no chain edges
        ]
        resp = client.get("/api/v1/graph/hadith/hdt-lonely/chain")
        assert resp.status_code == 200
        body = resp.json()
        assert body["nodes"] == []
        assert body["edges"] == []

    def test_max_pagination_limit(self, client: TestClient, mock_neo4j: MagicMock) -> None:
        """limit=100 (max allowed) succeeds."""
        mock_neo4j.execute_read.side_effect = [
            [{"total": 0}],
            [],
        ]
        resp = client.get("/api/v1/narrators?limit=100")
        assert resp.status_code == 200
        assert resp.json()["limit"] == 100

    def test_limit_just_over_max(self, client: TestClient) -> None:
        """limit=101 should fail (le=100)."""
        resp = client.get("/api/v1/narrators?limit=101")
        assert resp.status_code == 422

    def test_search_at_max_length(self, client: TestClient, mock_neo4j: MagicMock) -> None:
        """Query at exactly max_length=500 should succeed."""
        q = "a" * 500
        mock_neo4j.execute_read.return_value = []
        resp = client.get(f"/api/v1/search?q={q}")
        assert resp.status_code == 200

    def test_search_single_char_query(self, client: TestClient, mock_neo4j: MagicMock) -> None:
        """Single character query (min_length=1) should succeed."""
        mock_neo4j.execute_read.return_value = []
        resp = client.get("/api/v1/search?q=a")
        assert resp.status_code == 200
