import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from packages.common.models import DocumentModel, JobModel


DATABASE_URL = os.getenv("DATABASE_URL")

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def migrated_engine():
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL is not configured")

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", DATABASE_URL)

    command.upgrade(config, "head")

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
    )

    yield engine

    engine.dispose()


def test_postgres_connection(migrated_engine):
    with migrated_engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


def test_postgres_schema_exists(migrated_engine):
    inspector = inspect(migrated_engine)

    tables = set(inspector.get_table_names())

    assert {
        "jobs",
        "documents",
        "extractions",
        "leads",
        "exports",
        "alembic_version",
    }.issubset(tables)


def test_postgres_can_persist_job(migrated_engine):
    job_id = uuid4()

    with Session(migrated_engine) as session:
        job = JobModel(
            id=job_id,
            status="created",
            total_documents=1,
        )

        session.add(job)
        session.commit()

        stored = session.get(JobModel, job_id)

        assert stored is not None
        assert stored.id == job_id
        assert stored.total_documents == 1


def test_postgres_foreign_key_relationship(migrated_engine):
    job_id = uuid4()
    document_id = uuid4()

    with Session(migrated_engine) as session:
        job = JobModel(
            id=job_id,
            status="created",
            total_documents=1,
        )

        document = DocumentModel(
            id=document_id,
            job_id=job_id,
            source_uri="s3://test/card.jpg",
            content_hash="integration-test-hash",
            filename="card.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
            status="uploaded",
        )

        session.add_all([job, document])
        session.commit()

        stored = session.get(DocumentModel, document_id)

        assert stored is not None
        assert stored.job_id == job_id


def test_migration_is_idempotent(migrated_engine):
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", DATABASE_URL)

    command.upgrade(config, "head")

    inspector = inspect(migrated_engine)

    tables = set(inspector.get_table_names())

    assert "jobs" in tables
    assert "documents" in tables