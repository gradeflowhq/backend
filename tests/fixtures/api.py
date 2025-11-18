import pytest
from fastapi.testclient import TestClient

from gradeflow_backend.schemas.auth import TokenPairResponse
from tests.helpers.api import ApiClient


@pytest.fixture(scope="function")
def api(client: TestClient) -> ApiClient:
    api = ApiClient(client)
    tokens: TokenPairResponse = api.signup(
        email="user@example.com", password="Super-Strong-Pass-123!"
    )
    api.set_access_token(tokens.access_token)
    return api
