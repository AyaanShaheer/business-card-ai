from sqlalchemy import Integer, String, create_engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from packages.common.db import Base, create_session_factory
from packages.common.transaction import transaction


class TestRecord(Base):
    __tablename__ = "test_records"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    value: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )


def create_test_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    session_factory = create_session_factory(engine)

    return engine, session_factory


def test_transaction_commits_successfully():
    engine, session_factory = create_test_session()

    with session_factory() as session:
        with transaction(session):
            session.add(TestRecord(value="committed"))

    with session_factory() as session:
        records = session.query(TestRecord).all()

        assert len(records) == 1
        assert records[0].value == "committed"

    engine.dispose()


def test_transaction_rolls_back_on_exception():
    engine, session_factory = create_test_session()

    with session_factory() as session:
        try:
            with transaction(session):
                session.add(TestRecord(value="rolled-back"))
                raise RuntimeError("simulated failure")
        except RuntimeError:
            pass

    with session_factory() as session:
        records = session.query(TestRecord).all()

        assert records == []

    engine.dispose()


def test_transaction_does_not_swallow_exceptions():
    engine, session_factory = create_test_session()

    with session_factory() as session:
        try:
            with transaction(session):
                raise ValueError("business failure")
        except ValueError as exc:
            assert str(exc) == "business failure"

    engine.dispose()


def test_transaction_can_handle_multiple_writes_atomically():
    engine, session_factory = create_test_session()

    with session_factory() as session:
        with transaction(session):
            session.add(TestRecord(value="first"))
            session.add(TestRecord(value="second"))

    with session_factory() as session:
        records = session.query(TestRecord).all()

        assert len(records) == 2

    engine.dispose()