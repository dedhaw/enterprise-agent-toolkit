"""
SQLAlchemy SQLite setup.
All ORM models import Base from here.
"""
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config import get_settings


class Base(DeclarativeBase):
    pass


def _get_engine():
    settings = get_settings()
    os.makedirs(os.path.dirname(settings.db_path), exist_ok=True)
    return create_engine(
        f"sqlite:///{settings.db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )


def init_db() -> None:
    """Create all tables. Call once on startup."""
    from src.db.chat import models as _  # noqa: F401 — registers models with Base
    engine = _get_engine()
    Base.metadata.create_all(engine)


def get_session_factory():
    return sessionmaker(bind=_get_engine(), autoflush=False, autocommit=False)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_db_dep() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session."""
    with get_db() as session:
        yield session
