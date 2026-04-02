"""Shared fixtures for wavestreamer SDK tests."""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Environment isolation — tests must never hit real APIs
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Prevent tests from using real API keys or hitting production."""
    monkeypatch.setenv("WAVESTREAMER_URL", "http://localhost:8888")


# ---------------------------------------------------------------------------
# Mock HTTP session
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session():
    """Patch requests.Session and return the mock instance."""
    with patch("wavestreamer.client.requests.Session") as mock_cls:
        session = MagicMock()
        mock_cls.return_value = session
        yield session
