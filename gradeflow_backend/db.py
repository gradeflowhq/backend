from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from gradeflow_backend.models import Base

# Using SQLite for initial setup; replace with your DB URL when ready.
ENGINE = create_engine("sqlite+pysqlite:///./gradeflow_backend.db", echo=False)

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
