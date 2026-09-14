from collections.abc import Callable

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


def create_db_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine for the supplied database URL."""
    return create_engine(
        database_url,
        pool_pre_ping=True,
    )


def create_session_factory(engine: Engine) -> Callable[[], Session]:
    """Create a reusable SQLAlchemy session factory."""
    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )