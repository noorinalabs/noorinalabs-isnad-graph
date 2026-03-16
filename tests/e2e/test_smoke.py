"""Smoke tests: verify all pages load without errors."""

import re

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestSmoke:
    def test_home_page_loads(self, page: Page):
        page.goto("/")
        expect(page).to_have_title(re.compile("isnad"))

    def test_narrators_page_loads(self, page: Page):
        page.goto("/narrators")
        expect(page.locator("h1")).to_contain_text("Narrator")

    def test_hadiths_page_loads(self, page: Page):
        page.goto("/hadiths")
        expect(page.locator("h1")).to_contain_text("Hadith")

    def test_collections_page_loads(self, page: Page):
        page.goto("/collections")
        expect(page.locator("h1")).to_contain_text("Collection")

    def test_search_page_loads(self, page: Page):
        page.goto("/search")
        expect(page.locator("input")).to_be_visible()

    def test_timeline_page_loads(self, page: Page):
        page.goto("/timeline")
        expect(page.locator("h1")).to_contain_text("Timeline")

    def test_graph_page_loads(self, page: Page):
        page.goto("/graph")
        expect(page.locator("h1")).to_contain_text("Graph")

    def test_compare_page_loads(self, page: Page):
        page.goto("/compare")
        expect(page.locator("h1")).to_contain_text("Compar")
