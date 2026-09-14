import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from packages.common.db import Base
from packages.common.models import DocumentModel, JobModel


DATABASE_URL = os.getenv("DATABASE_URL")


pytestmark = pytest.mark.integration


@pytest.fixture()
def engine():
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL is not configured")

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
    )

    yield engine

    engine.dispose()


def test_postgres_connection(engine):
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


def test_postgres_can_persist_job(engine):
    Base.metadata.create_all(engine)

    job_id = uuid4()

    with Session(engine) as session:
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


def test_postgres_foreign_key_relationship(engine):
    Base.metadata.create_all(engine)

    job_id = uuid4()
    document_id = uuid4()

    with Session(engine) as session:
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