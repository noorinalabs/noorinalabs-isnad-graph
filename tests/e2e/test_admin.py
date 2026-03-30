"""E2E tests for admin panel pages and access control."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestAdminAccessControl:
    """Verify admin routes are gated behind authentication + admin role."""

    def test_admin_root_redirects_unauthenticated(self, page: Page):
        """Unauthenticated visit to /admin redirects to /narrators."""
        page.goto("/admin")
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url("/narrators")

    def test_admin_users_redirects_unauthenticated(self, page: Page):
        page.goto("/admin/users")
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url("/narrators")

    def test_admin_health_redirects_unauthenticated(self, page: Page):
        page.goto("/admin/health")
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url("/narrators")

    def test_admin_stats_redirects_unauthenticated(self, page: Page):
        page.goto("/admin/stats")
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url("/narrators")

    def test_admin_analytics_redirects_unauthenticated(self, page: Page):
        page.goto("/admin/analytics")
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url("/narrators")

    def test_admin_moderation_redirects_unauthenticated(self, page: Page):
        page.goto("/admin/moderation")
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url("/narrators")

    def test_admin_reports_redirects_unauthenticated(self, page: Page):
        page.goto("/admin/reports")
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url("/narrators")

    def test_admin_config_redirects_unauthenticated(self, page: Page):
        page.goto("/admin/config")
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url("/narrators")
