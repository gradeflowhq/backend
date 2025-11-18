from __future__ import annotations

import os
from collections.abc import Generator

import pytest

# Auto-load fixtures from modules under tests/fixtures
pytest_plugins = [
    "tests.fixtures.db",
    "tests.fixtures.client",
    "tests.fixtures.api",
]


@pytest.fixture(scope="session", autouse=True)
def test_env() -> Generator[None, None, None]:
    """
    Session-wide environment setup for tests.
    - Ensures deterministic secrets and configs.
    - Extend with other env vars as needed (e.g., logging levels).
    """
    os.environ.setdefault("JWT_SECRET", "test-secret")
    os.environ.setdefault("JWT_ALGORITHM", "HS256")
    os.environ.setdefault("JWT_ISSUER", "gradeflow-api")
    os.environ.setdefault("JWT_AUDIENCE", "gradeflow-clients")
    # Add other defaults if your code reads env at import time

    yield
    # No teardown required; pytest will end the session
