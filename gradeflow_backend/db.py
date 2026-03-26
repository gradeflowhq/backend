from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from gradeflow_backend.config import get_settings
from gradeflow_backend.models import Base


def _build_engine() -> Engine:
    url = get_settings().database.url
    dialect = make_url(url).drivername.split("+")[0]  # e.g. "sqlite", "postgresql", "mysql"
    kwargs: dict[str, Any] = {"echo": False}
    if dialect == "sqlite":
        # SQLite raises an error when the same connection is accessed from multiple threads.
        # FastAPI dispatches sync dependencies via a thread pool, so this flag is required.
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


ENGINE = _build_engine()

SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=ENGINE)


def get_session() -> Generator[Session, Any, Any]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
