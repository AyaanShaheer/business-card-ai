import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.common.models import DocumentModel, JobModel


DATABASE_URL = os.getenv("DATABASE_URL")

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def engine():
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL is not configured")

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
    )

    yield engine

    engine.dispose()


@pytest.fixture()
def job_id(engine):
    job_id = uuid4()

    with Session(engine) as session:
        session.add(
            JobModel(
                id=job_id,
                status="created",
                total_documents=2,
            )
        )
        session.commit()

    yield job_id

    with Session(engine) as session:
        job = session.get(JobModel, job_id)

        if job is not None:
            session.delete(job)
            session.commit()


def insert_document(engine, job_id, content_hash):
    document_id = uuid4()

    with Session(engine) as session:
        document = DocumentModel(
            id=document_id,
            job_id=job_id,
            source_uri=f"s3://bucket/{document_id}.jpg",
            content_hash=content_hash,
            filename=f"{document_id}.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
            status="uploaded",
        )

        session.add(document)

        try:
            session.commit()
            return "success", document_id

        except IntegrityError:
            session.rollback()
            return "integrity_error", None


def test_concurrent_duplicate_documents_are_database_safe(
    engine,
    job_id,
):
    content_hash = "concurrent-race-hash"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                insert_document,
                engine,
                job_id,
                content_hash,
            ),
            executor.submit(
                insert_document,
                engine,
                job_id,
                content_hash,
            ),
        ]

        results = [future.result() for future in futures]

    outcomes = [result[0] for result in results]

    assert outcomes.count("success") == 1
    assert outcomes.count("integrity_error") == 1

    with Session(engine) as session:
        documents = (
            session.query(DocumentModel)
            .filter(
                DocumentModel.job_id == job_id,
                DocumentModel.content_hash == content_hash,
            )
            .all()
        )

        assert len(documents) == 1