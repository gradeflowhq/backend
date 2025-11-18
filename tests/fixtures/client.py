from collections.abc import Generator

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
