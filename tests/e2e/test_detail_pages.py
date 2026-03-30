"""E2E tests for detail pages (narrator, hadith, collection)."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestDetailPages:
    """Verify detail page routes render without crashing."""

    def test_narrator_detail_renders_heading(self, page: Page):
        """Navigating to a narrator detail page shows a heading (or error state)."""
        page.goto("/narrators")
        page.wait_for_load_state("networkidle")

        # Try clicking the first row to navigate to detail
        first_row = page.locator("table tbody tr, [data-testid='narrator-row']").first
        if first_row.is_visible():
            first_row.click()
            page.wait_for_load_state("networkidle")
            # Detail page should show some heading
            expect(page.locator("h1, h2")).to_be_visible()

    def test_hadith_detail_renders_heading(self, page: Page):
        """Navigating to a hadith detail page shows a heading (or error state)."""
        page.goto("/hadiths")
        page.wait_for_load_state("networkidle")

        first_row = page.locator("table tbody tr, [data-testid='hadith-row']").first
        if first_row.is_visible():
            first_row.click()
            page.wait_for_load_state("networkidle")
            expect(page.locator("h1, h2")).to_be_visible()

    def test_collection_detail_renders_heading(self, page: Page):
        """Navigating to a collection detail page shows a heading (or error state)."""
        page.goto("/collections")
        page.wait_for_load_state("networkidle")

        first_row = page.locator("table tbody tr, [data-testid='collection-row']").first
        if first_row.is_visible():
            first_row.click()
            page.wait_for_load_state("networkidle")
            expect(page.locator("h1, h2")).to_be_visible()

    def test_narrator_detail_direct_url_does_not_crash(self, page: Page):
        """Directly visiting /narrators/1 should render without JS errors."""
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto("/narrators/1")
        page.wait_for_load_state("networkidle")

        body = page.locator("body").inner_text()
        assert len(body) > 0
        assert len(errors) == 0, f"JS errors on narrator detail: {errors}"

    def test_hadith_detail_direct_url_does_not_crash(self, page: Page):
        """Directly visiting /hadiths/1 should render without JS errors."""
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto("/hadiths/1")
        page.wait_for_load_state("networkidle")

        body = page.locator("body").inner_text()
        assert len(body) > 0
        assert len(errors) == 0, f"JS errors on hadith detail: {errors}"

    def test_collection_detail_direct_url_does_not_crash(self, page: Page):
        """Directly visiting /collections/1 should render without JS errors."""
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto("/collections/1")
        page.wait_for_load_state("networkidle")

        body = page.locator("body").inner_text()
        assert len(body) > 0
        assert len(errors) == 0, f"JS errors on collection detail: {errors}"
