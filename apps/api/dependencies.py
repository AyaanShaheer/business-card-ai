from collections.abc import Iterator

from sqlalchemy.orm import Session

from packages.common.db import create_db_engine, create_session_factory
from packages.common.settings import Settings


settings = Settings()

engine = create_db_engine(str(settings.database_url))
SessionLocal = create_session_factory(engine)


def get_db_session() -> Iterator[Session]:
    """
    Provide one SQLAlchemy session per request.

    The session is closed automatically after the request finishes.
    Transaction ownership remains with the service layer.
    """
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()