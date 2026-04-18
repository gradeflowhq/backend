from collections.abc import Generator

import pytest

from gradeflow_backend.config import get_settings

# Auto-load fixtures from modules under tests/fixtures
pytest_plugins = [
    "tests.fixtures.db",
    "tests.fixtures.client",
    "tests.fixtures.api",
]


@pytest.fixture(scope="session", autouse=True)
def test_env() -> Generator[None, None, None]:
    settings = get_settings()

    # Zitadel: provide a dummy client_id so startup validation passes
    settings.zitadel.client_id = "test-client-id"

    # Executor: force synchronous, single worker, short timeouts for tests
    settings.executor.executor = "SYNCHRONOUS"
    settings.executor.num_workers = 1
    settings.executor.timeout_s = 10
    settings.executor.poll_interval_s = 0.1

    yield
