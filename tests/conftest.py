from __future__ import annotations

import pytest

from web_prime_search.config import Settings


@pytest.fixture()
def settings() -> Settings:
    """Return a Settings instance with default values."""
    return Settings()
