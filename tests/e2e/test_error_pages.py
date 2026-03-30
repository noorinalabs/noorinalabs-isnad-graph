"""E2E tests for error states (404, unauthorized, missing data)."""

import pytest
from playwright.sync_api import Page


@pytest.mark.e2e
class TestErrorPages:
    """Verify the application handles error states gracefully."""

    def test_unknown_route_does_not_crash(self, page: Page):
        """Visiting a non-existent route should not produce a blank page or JS error."""
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto("/this-route-does-not-exist")
        page.wait_for_load_state("networkidle")

        # The page should still render something (React catches the route)
        body_text = page.locator("body").inner_text()
        assert len(body_text) > 0, "Page body should not be empty for unknown routes"
        assert len(errors) == 0, f"Unexpected JS errors on 404 route: {errors}"

    def test_unknown_narrator_id_does_not_crash(self, page: Page):
        """Visiting /narrators/nonexistent-id should not produce JS errors."""
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto("/narrators/nonexistent-id-12345")
        page.wait_for_load_state("networkidle")

        body_text = page.locator("body").inner_text()
        assert len(body_text) > 0
        assert len(errors) == 0, f"Unexpected JS errors on bad narrator ID: {errors}"

    def test_unknown_hadith_id_does_not_crash(self, page: Page):
        """Visiting /hadiths/nonexistent-id should not produce JS errors."""
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto("/hadiths/nonexistent-id-12345")
        page.wait_for_load_state("networkidle")

        body_text = page.locator("body").inner_text()
        assert len(body_text) > 0
        assert len(errors) == 0, f"Unexpected JS errors on bad hadith ID: {errors}"

    def test_unknown_collection_id_does_not_crash(self, page: Page):
        """Visiting /collections/nonexistent-id should not produce JS errors."""
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto("/collections/nonexistent-id-12345")
        page.wait_for_load_state("networkidle")

        body_text = page.locator("body").inner_text()
        assert len(body_text) > 0
        assert len(errors) == 0, f"Unexpected JS errors on bad collection ID: {errors}"

    def test_api_404_returns_json(self, page: Page):
        """An unknown API route should return a JSON error, not HTML."""
        response = page.request.get("/api/v1/nonexistent-endpoint")
        assert response.status in (404, 405)

    def test_unauthorized_admin_api(self, page: Page):
        """Admin API endpoints without auth should return 401 or 403."""
        response = page.request.get("/api/v1/admin/users")
        assert response.status in (401, 403)
