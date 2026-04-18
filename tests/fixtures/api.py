import pytest
from fastapi.testclient import TestClient

from tests.helpers.api import ApiClient


@pytest.fixture(scope="function")
def api(client: TestClient) -> ApiClient:
    """
    Authenticated API client.
    Auth is handled by the dependency override in fixtures/client.py — any
    request with an Authorization header is accepted (the Zitadel JWT
    validation is bypassed).
    """
    api = ApiClient(client)
    api.set_access_token("test-token")
    return api
