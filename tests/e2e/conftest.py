"""E2E test fixtures for Playwright browser tests."""

import pytest


@pytest.fixture(scope="session")
def browser_context_args():
    """Configure browser context for tests."""
    return {
        "viewport": {"width": 1280, "height": 720},
        "base_url": "http://localhost:3000",
    }
