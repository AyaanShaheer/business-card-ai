from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.common.db import Base, create_session_factory
from packages.common.repositories import JobRepository
from packages.common.services import JobService


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    factory = create_session_factory(engine)

    yield factory

    engine.dispose()


@pytest.fixture()
def service(session_factory):
    with session_factory() as session:
        repository = JobRepository(session)

        yield JobService(
            session=session,
            repository=repository,
            max_files_per_job=50,
        )


def test_create_job_returns_created_job(service):
    job = service.create_job(total_documents=10)

    assert job.id is not None
    assert job.status == "created"
    assert job.total_documents == 10


def test_create_job_rejects_negative_document_count(service):
    with pytest.raises(ValueError, match="total_documents"):
        service.create_job(total_documents=-1)


def test_create_job_rejects_unreasonably_large_batch(service):
    with pytest.raises(ValueError, match="maximum"):
        service.create_job(total_documents=51)


def test_create_job_persists_after_service_call(session_factory):
    with session_factory() as session:
        repository = JobRepository(session)
        service = JobService(
            session=session,
            repository=repository,
        )

        job = service.create_job(total_documents=5)

        job_id = job.id

    with session_factory() as session:
        stored = session.get(type(job), job_id)

        assert stored is not None
        assert stored.total_documents == 5


def test_create_job_is_rolled_back_on_failure(session_factory):
    class FailingRepository(JobRepository):
        def create(self, *, status: str, total_documents: int):
            super().create(
                status=status,
                total_documents=total_documents,
            )
            raise RuntimeError("simulated failure")

    with session_factory() as session:
        repository = FailingRepository(session)

        service = JobService(
            session=session,
            repository=repository,
        )

        with pytest.raises(RuntimeError, match="simulated failure"):
            service.create_job(total_documents=5)

    with session_factory() as session:
        # Database must contain no committed job after failure.
        from packages.common.models import JobModel

        assert session.query(JobModel).count() == 0


def test_get_job_returns_existing_job(session_factory):
    with session_factory() as session:
        repository = JobRepository(session)

        job = repository.create(
            status="created",
            total_documents=3,
        )
        session.commit()

        service = JobService(
            session=session,
            repository=repository,
        )

        result = service.get_job(job.id)

        assert result is not None
        assert result.id == job.id


def test_get_unknown_job_returns_none(session_factory):
    with session_factory() as session:
        repository = JobRepository(session)

        service = JobService(
            session=session,
            repository=repository,
        )

        result = service.get_job(uuid4())

        assert result is None