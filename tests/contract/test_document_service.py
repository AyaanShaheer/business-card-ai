from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.common.db import Base, create_session_factory
from packages.common.models import DocumentModel, JobModel
from packages.common.repositories import DocumentRepository
from packages.common.services import DocumentService


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    factory = create_session_factory(engine)

    yield factory

    engine.dispose()


@pytest.fixture()
def job_id(session_factory):
    with session_factory() as session:
        job = JobModel(
            id=uuid4(),
            status="created",
            total_documents=1,
        )

        session.add(job)
        session.commit()

        return job.id


@pytest.fixture()
def service(session_factory):
    with session_factory() as session:
        repository = DocumentRepository(session)

        yield DocumentService(
            session=session,
            repository=repository,
            max_file_size_bytes=10 * 1024 * 1024,
        )



def test_create_document(service, job_id):
    document = service.create_document(
        job_id=job_id,
        source_uri="s3://bucket/card.jpg",
        content_hash="hash-1",
        filename="card.jpg",
        mime_type="image/jpeg",
        size_bytes=1024,
    )

    assert document.id is not None
    assert document.job_id == job_id
    assert document.status == "uploaded"


def test_reject_unsupported_mime_type(service, job_id):
    with pytest.raises(ValueError, match="mime"):
        service.create_document(
            job_id=job_id,
            source_uri="s3://bucket/card.exe",
            content_hash="hash-2",
            filename="card.exe",
            mime_type="application/octet-stream",
            size_bytes=1024,
        )


def test_reject_file_above_size_limit(service, job_id):
    with pytest.raises(ValueError, match="size"):
        service.create_document(
            job_id=job_id,
            source_uri="s3://bucket/large.jpg",
            content_hash="hash-3",
            filename="large.jpg",
            mime_type="image/jpeg",
            size_bytes=10 * 1024 * 1024 + 1,
        )


def test_reject_empty_filename(service, job_id):
    with pytest.raises(ValueError, match="filename"):
        service.create_document(
            job_id=job_id,
            source_uri="s3://bucket/card.jpg",
            content_hash="hash-4",
            filename="",
            mime_type="image/jpeg",
            size_bytes=1024,
        )


def test_reject_empty_content_hash(service, job_id):
    with pytest.raises(ValueError, match="hash"):
        service.create_document(
            job_id=job_id,
            source_uri="s3://bucket/card.jpg",
            content_hash="",
            filename="card.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
        )


def test_same_hash_same_job_is_idempotent(service, job_id):
    first = service.create_document(
        job_id=job_id,
        source_uri="s3://bucket/card1.jpg",
        content_hash="same-hash",
        filename="card1.jpg",
        mime_type="image/jpeg",
        size_bytes=1024,
    )

    second = service.create_document(
        job_id=job_id,
        source_uri="s3://bucket/card1-copy.jpg",
        content_hash="same-hash",
        filename="card1-copy.jpg",
        mime_type="image/jpeg",
        size_bytes=1024,
    )

    assert first.id == second.id


def test_same_hash_different_jobs_creates_separate_document(
    session_factory,
    job_id,
):
    with session_factory() as session:
        second_job = JobModel(
            id=uuid4(),
            status="created",
            total_documents=1,
        )
        session.add(second_job)
        session.commit()

    with session_factory() as session:
        service = DocumentService(
            session=session,
            repository=DocumentRepository(session),
            max_file_size_bytes=10 * 1024 * 1024,
        )

        first = service.create_document(
            job_id=job_id,
            source_uri="s3://bucket/card.jpg",
            content_hash="shared-hash",
            filename="card.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
        )

        second = service.create_document(
            job_id=second_job.id,
            source_uri="s3://bucket/card.jpg",
            content_hash="shared-hash",
            filename="card.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
        )

        assert first.id != second.id


def test_document_defaults_to_uploaded_status(service, job_id):
    document = service.create_document(
        job_id=job_id,
        source_uri="s3://bucket/card.jpg",
        content_hash="hash-status",
        filename="card.jpg",
        mime_type="image/jpeg",
        size_bytes=1024,
    )

    assert document.status == "uploaded"

def test_create_document_handles_unique_constraint_race(
    session_factory,
    job_id,
):
    class RaceRepository(DocumentRepository):
        def create(
            self,
            *,
            job_id,
            source_uri,
            content_hash,
            filename,
            mime_type,
            size_bytes,
            status="uploaded",
        ):
            raise IntegrityError(
                "duplicate key",
                {},
                Exception("uq_documents_job_content_hash"),
            )

    with session_factory() as session:
        repository = RaceRepository(session)

        service = DocumentService(
            session=session,
            repository=repository,
            max_file_size_bytes=10 * 1024 * 1024,
        )

        with pytest.raises(IntegrityError):
            service.create_document(
                job_id=job_id,
                source_uri="s3://bucket/card.jpg",
                content_hash="race-hash",
                filename="card.jpg",
                mime_type="image/jpeg",
                size_bytes=1024,
            )

def test_create_document_reraises_unrelated_integrity_error(
    session_factory,
    job_id,
):
    class FailingRepository(DocumentRepository):
        def create(
            self,
            *,
            job_id,
            source_uri,
            content_hash,
            filename,
            mime_type,
            size_bytes,
            status="uploaded",
        ):
            raise IntegrityError(
                "some other database constraint failed",
                {},
                Exception("different_constraint"),
            )

    with session_factory() as session:
        repository = FailingRepository(session)

        service = DocumentService(
            session=session,
            repository=repository,
            max_file_size_bytes=10 * 1024 * 1024,
        )

        with pytest.raises(IntegrityError):
            service.create_document(
                job_id=job_id,
                source_uri="s3://bucket/card.jpg",
                content_hash="other-race-hash",
                filename="card.jpg",
                mime_type="image/jpeg",
                size_bytes=1024,
            )