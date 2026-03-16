"""Test navigation between pages."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestNavigation:
    def test_sidebar_links_work(self, page: Page):
        """Click each sidebar link and verify the target page loads."""
        page.goto("/")

        sidebar_links = page.locator("nav a")
        count = sidebar_links.count()
        assert count > 0, "Expected sidebar navigation links"

        for i in range(count):
            link = sidebar_links.nth(i)
            href = link.get_attribute("href")
            if href:
                link.click()
                page.wait_for_load_state("networkidle")
                expect(page.locator("h1")).to_be_visible()

    def test_narrator_detail_navigation(self, page: Page):
        """Navigate to narrators list, click first row, verify detail page."""
        page.goto("/narrators")
        page.wait_for_load_state("networkidle")

        first_row = page.locator("table tbody tr, [data-testid='narrator-row']").first
        if first_row.is_visible():
            first_row.click()
            page.wait_for_load_state("networkidle")
            expect(page.locator("h1, h2")).to_be_visible()

    def test_search_and_navigate(self, page: Page):
        """Search for a term, click a result, verify navigation."""
        page.goto("/search")
        page.wait_for_load_state("networkidle")

        search_input = page.locator("input").first
        search_input.fill("Bukhari")
        search_input.press("Enter")
        page.wait_for_load_state("networkidle")

        first_result = page.locator("a[href]", has=page.locator("text=/./")).first
        if first_result.is_visible():
            first_result.click()
            page.wait_for_load_state("networkidle")
            expect(page.locator("h1, h2")).to_be_visible()
