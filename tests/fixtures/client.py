from collections.abc import Generator
from typing import Protocol
from urllib.parse import urlparse

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gradeflow_backend.db import get_session
from gradeflow_backend.main import app


@pytest.fixture(scope="function")
def client(test_engine: Engine) -> Generator[TestClient, None, None]:
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

    app.dependency_overrides[get_session] = _override_get_session

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


class _ResponseLike(Protocol):
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
        resp = client.post(path, json=json)

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
