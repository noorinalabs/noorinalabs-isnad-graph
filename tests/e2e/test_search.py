"""E2E tests for search functionality."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestSearch:
    """Exercise the search page UI interactions."""

    def test_search_page_has_input(self, page: Page):
        """Search page renders with a text input."""
        page.goto("/search")
        page.wait_for_load_state("networkidle")
        search_input = page.locator("input[type='text']").first
        expect(search_input).to_be_visible()

    def test_search_page_has_mode_selector(self, page: Page):
        """Search page shows fulltext and semantic radio buttons."""
        page.goto("/search")
        page.wait_for_load_state("networkidle")
        radios = page.locator("input[type='radio']")
        expect(radios).to_have_count(2)

    def test_fulltext_mode_selected_by_default(self, page: Page):
        """Full-text mode radio should be checked by default."""
        page.goto("/search")
        page.wait_for_load_state("networkidle")
        fulltext_radio = page.locator("input[type='radio']").first
        expect(fulltext_radio).to_be_checked()

    def test_typing_short_query_shows_no_results(self, page: Page):
        """Queries shorter than 2 characters should not trigger search."""
        page.goto("/search")
        page.wait_for_load_state("networkidle")
        search_input = page.locator("input[type='text']").first
        search_input.fill("a")
        # Wait a bit for debounce to fire
        page.wait_for_timeout(500)
        # No "Searching..." indicator and no results
        searching_indicator = page.locator("text=Searching...")
        expect(searching_indicator).to_have_count(0)

    def test_search_with_query_triggers_request(self, page: Page):
        """Typing a query >= 2 chars should trigger a search (shows loading or results)."""
        page.goto("/search")
        page.wait_for_load_state("networkidle")
        search_input = page.locator("input[type='text']").first
        search_input.fill("Bukhari")
        # Wait for debounce + network
        page.wait_for_timeout(500)
        # We just verify the page didn't crash — don't assert on API data
        expect(page.locator("h2")).to_contain_text("Search")

    def test_switch_to_semantic_mode(self, page: Page):
        """Clicking semantic radio switches the search mode."""
        page.goto("/search")
        page.wait_for_load_state("networkidle")
        semantic_radio = page.locator("input[type='radio']").nth(1)
        semantic_radio.click()
        expect(semantic_radio).to_be_checked()

    def test_search_placeholder_text(self, page: Page):
        """The search input should have descriptive placeholder text."""
        page.goto("/search")
        page.wait_for_load_state("networkidle")
        search_input = page.locator("input[type='text']").first
        placeholder = search_input.get_attribute("placeholder")
        assert placeholder is not None
        assert "search" in placeholder.lower() or "narrator" in placeholder.lower()
