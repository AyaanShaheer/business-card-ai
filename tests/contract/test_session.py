from sqlalchemy import text
from sqlalchemy.orm import Session

from packages.common.db import create_db_engine, create_session_factory


def test_session_factory_creates_sqlalchemy_sessions():
    engine = create_db_engine("sqlite:///:memory:")
    session_factory = create_session_factory(engine)

    session = session_factory()

    try:
        assert isinstance(session, Session)
    finally:
        session.close()
        engine.dispose()


def test_session_can_execute_query():
    engine = create_db_engine("sqlite:///:memory:")
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        result = session.execute(text("SELECT 1"))

        assert result.scalar_one() == 1

    engine.dispose()


def test_session_factory_reuses_same_engine():
    engine = create_db_engine("sqlite:///:memory:")
    session_factory = create_session_factory(engine)

    with session_factory() as session_1:
        with session_factory() as session_2:
            assert session_1.bind is engine
            assert session_2.bind is engine

    engine.dispose()


def test_session_context_returns_closed_session_after_exit():
    engine = create_db_engine("sqlite:///:memory:")
    session_factory = create_session_factory(engine)

    session = session_factory()

    with session:
        session.execute(text("SELECT 1"))

    assert session.is_active is True

    session.close()

    assert session.is_active is True

    engine.dispose()