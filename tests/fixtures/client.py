from collections.abc import Generator
from typing import Protocol
from urllib.parse import urlparse

import httpx
import pytest
from fakeredis import FakeValkey
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gradeflow_backend.db import get_session, get_valkey
from gradeflow_backend.dependencies.auth import get_current_user
from gradeflow_backend.main import app
from gradeflow_backend.schemas.auth import ZitadelTokenPayload

# Default test user identity — matches the Zitadel token payload shape.
TEST_USER_SUB = "test-user-id"
TEST_USER_EMAIL = "user@example.com"
TEST_USER_NAME: str | None = None


def _make_test_token(
    sub: str = TEST_USER_SUB,
    email: str = TEST_USER_EMAIL,
    name: str | None = TEST_USER_NAME,
) -> ZitadelTokenPayload:
    return ZitadelTokenPayload(
        sub=sub,
        email=email,
        name=name,
        iss="https://zitadel.test",
        aud="test-client-id",
    )


# Registry mapping bearer tokens to test user payloads.
# The api fixture uses "test-token" (default user); secondary users
# register themselves here via ``register_test_user()``.
_token_registry: dict[str, ZitadelTokenPayload] = {
    "test-token": _make_test_token(),
}


def register_test_user(token: str, *, sub: str, email: str, name: str | None = None) -> None:
    """Register a secondary test user so the auth override can resolve it."""
    _token_registry[token] = _make_test_token(sub=sub, email=email, name=name)


def _override_get_current_user(request: Request) -> tuple[ZitadelTokenPayload, str]:
    """
    Bypass real Zitadel JWT validation in tests.
    Resolves the user identity from the bearer token via ``_token_registry``.
    """
    auth = request.headers.get("authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    payload = _token_registry.get(token)
    if payload is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid test token")
    return payload, token


@pytest.fixture(scope="function")
def client(test_engine: Engine, fake_valkey: FakeValkey) -> Generator[TestClient, None, None]:
    TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    def _override_get_session() -> Generator[Session, None, None]:
        db: Session = TestingSessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # Reset token registry to only the default user for each test
    _token_registry.clear()
    _token_registry["test-token"] = _make_test_token()

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_valkey] = lambda: fake_valkey
    app.dependency_overrides[get_current_user] = _override_get_current_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


class _ResponseLike(Protocol):
    """Shape required by the httpx.post mock below."""

    status_code: int
    text: str

    def raise_for_status(self) -> None: ...


@pytest.fixture(autouse=True)
def patch_httpx_post(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def _post(
        url: str,
        *,
        json: dict[str, object] | None = None,
        timeout: float | int | None = None,
        **kwargs: object,
    ) -> _ResponseLike:
        parsed = urlparse(url)
        path = parsed.path or "/"
        raw_headers = kwargs.get("headers")
        headers: dict[str, str] | None = (
            dict(raw_headers) if isinstance(raw_headers, dict) else None
        )
        if json is not None:
            resp = client.post(path, json=json, headers=headers)
        else:
            content = kwargs.get("content")
            resp = client.post(
                path,
                content=content if isinstance(content, (str, bytes)) else None,
                headers=headers,
            )

        class _DummyResponse:
            status_code = resp.status_code
            text = resp.text

            def raise_for_status(self) -> None:
                if resp.status_code >= 400:
                    req = httpx.Request("POST", path)
                    res = httpx.Response(
                        status_code=resp.status_code,
                        content=resp.text.encode("utf-8"),
                        request=req,
                    )
                    raise httpx.HTTPStatusError(resp.text, request=req, response=res)

        return _DummyResponse()

    monkeypatch.setattr(httpx, "post", _post)
