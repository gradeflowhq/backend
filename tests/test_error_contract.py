from typing import cast

from fastapi.testclient import TestClient
from httpx import Response

from tests.helpers.api import ApiClient


def assert_error_contract(response: Response, status_code: int) -> dict[str, object]:
    assert response.status_code == status_code, response.text
    raw_body = response.json()
    assert isinstance(raw_body, dict)
    body = cast(dict[str, object], raw_body)
    assert set(body) == {"code", "message", "errors"}
    assert isinstance(body["code"], str)
    assert isinstance(body["message"], str)
    errors = body["errors"]
    assert isinstance(errors, list)
    assert all(isinstance(error, str) for error in errors)
    return body


def test_unknown_route_uses_error_contract(client: TestClient) -> None:
    body = assert_error_contract(client.get("/not-a-real-route"), 404)

    assert body == {
        "code": "NOT_FOUND",
        "message": "Not Found",
        "errors": ["Not Found"],
    }


def test_request_validation_uses_error_contract(api: ApiClient) -> None:
    body = assert_error_contract(api.try_create_assessment(name=""), 422)

    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Request validation failed"
