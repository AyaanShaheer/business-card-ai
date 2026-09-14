from sqlalchemy import text

from packages.common.db import create_db_engine


def test_create_db_engine_can_connect():
    engine = create_db_engine("sqlite:///:memory:")

    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))

    assert result.scalar_one() == 1


def test_create_db_engine_enables_pre_ping():
    engine = create_db_engine("sqlite:///:memory:")

    assert engine.pool._pre_ping is True

    engine.dispose()