from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session


@contextmanager
def transaction(session: Session) -> Iterator[Session]:
    """Execute database operations within an atomic transaction."""
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise