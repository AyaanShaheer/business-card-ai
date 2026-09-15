from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.common.db import create_session_factory
from packages.common.models import JobModel
from packages.common.repositories import JobRepository


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    from packages.common.db import Base

    Base.metadata.create_all(engine)

    session_factory = create_session_factory(engine)

    with session_factory() as db:
        yield db

    engine.dispose()


def test_create_job(session):
    repository = JobRepository(session)

    job = repository.create(
        status="created",
        total_documents=10,
    )

    session.commit()

    assert job.id is not None
    assert job.status == "created"
    assert job.total_documents == 10


def test_get_job_by_id(session):
    repository = JobRepository(session)

    job = repository.create(
        status="created",
        total_documents=5,
    )

    session.commit()

    stored = repository.get_by_id(job.id)

    assert stored is not None
    assert stored.id == job.id


def test_get_job_returns_none_for_unknown_id(session):
    repository = JobRepository(session)

    result = repository.get_by_id(uuid4())

    assert result is None


def test_update_job_status(session):
    repository = JobRepository(session)

    job = repository.create(
        status="created",
        total_documents=5,
    )

    session.commit()

    updated = repository.update_status(
        job.id,
        "processing",
    )

    session.commit()

    assert updated is not None
    assert updated.status == "processing"


def test_update_unknown_job_returns_none(session):
    repository = JobRepository(session)

    result = repository.update_status(
        uuid4(),
        "processing",
    )

    assert result is None


def test_repository_does_not_commit_transactions(session):
    repository = JobRepository(session)

    job = repository.create(
        status="created",
        total_documents=1,
    )

    # The repository must not commit.
    # The caller controls the transaction boundary.
    assert job.id is not None

    session.rollback()

    assert session.get(JobModel, job.id) is None