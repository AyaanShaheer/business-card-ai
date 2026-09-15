from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.common.db import Base, create_session_factory
from packages.common.models import DocumentModel, JobModel


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    factory = create_session_factory(engine)

    yield factory

    engine.dispose()


def create_job(session: Session):
    job = JobModel(
        id=uuid4(),
        status="created",
        total_documents=2,
    )

    session.add(job)
    session.commit()

    return job


def create_document(
    session: Session,
    *,
    job_id,
    content_hash: str,
):
    document = DocumentModel(
        id=uuid4(),
        job_id=job_id,
        source_uri="s3://bucket/card.jpg",
        content_hash=content_hash,
        filename="card.jpg",
        mime_type="image/jpeg",
        size_bytes=1024,
        status="uploaded",
    )

    session.add(document)

    return document


def test_duplicate_content_hash_is_rejected_within_same_job(
    session_factory,
):
    with session_factory() as session:
        job = create_job(session)

        first = create_document(
            session,
            job_id=job.id,
            content_hash="same-hash",
        )

        session.commit()

        assert first.id is not None

        second = create_document(
            session,
            job_id=job.id,
            content_hash="same-hash",
        )

        session.add(second)

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()


def test_same_content_hash_is_allowed_across_different_jobs(
    session_factory,
):
    with session_factory() as session:
        job_a = create_job(session)
        job_b = create_job(session)

        first = create_document(
            session,
            job_id=job_a.id,
            content_hash="shared-hash",
        )

        second = create_document(
            session,
            job_id=job_b.id,
            content_hash="shared-hash",
        )

        session.add_all([first, second])
        session.commit()

        assert first.id != second.id


def test_different_hashes_are_allowed_within_same_job(
    session_factory,
):
    with session_factory() as session:
        job = create_job(session)

        first = create_document(
            session,
            job_id=job.id,
            content_hash="hash-a",
        )

        second = create_document(
            session,
            job_id=job.id,
            content_hash="hash-b",
        )

        session.add_all([first, second])
        session.commit()

        assert first.id != second.id


def test_unique_constraint_is_present():
    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(engine)

    document_table = DocumentModel.__table__

    unique_constraints = {
        constraint.name
        for constraint in document_table.constraints
        if constraint.name is not None
    }

    indexes = {
        index.name
        for index in document_table.indexes
        if index.name is not None
    }

    assert (
        "uq_documents_job_content_hash" in unique_constraints
        or "uq_documents_job_content_hash" in indexes
    )

    engine.dispose()