import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fakeredis import FakeValkey
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from gradeflow_backend.models import Base


def _test_db_url(tmp_path: Path) -> str:
    """Return DB_URL from env, or a per-test SQLite file as fallback."""
    url = os.environ.get("DB_URL", "")
    if url:
        return url
    db_path: Path = tmp_path / "gradeflow_backend.db"
    return f"sqlite+pysqlite:///{db_path}"


@pytest.fixture(scope="function")
def test_engine(tmp_path: Path) -> Generator[Engine, None, None]:
    url = _test_db_url(tmp_path)
    dialect = make_url(url).drivername.split("+")[0]
    kwargs: dict[str, Any] = {"echo": False, "future": True}
    if dialect == "sqlite":
        kwargs["connect_args"] = {"check_same_thread": False}
    engine: Engine = create_engine(url, **kwargs)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_session(test_engine: Engine) -> Generator[Session, None, None]:
    TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    db: Session = TestingSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@pytest.fixture(scope="function")
def fake_valkey() -> FakeValkey:
    return FakeValkey(decode_responses=True)
