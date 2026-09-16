from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.worker.processor import DocumentProcessor
from packages.common.db import Base
from packages.common.models import (
    DocumentModel,
    JobModel,
)


class FakeObjectReader:
    def read(self, *, source_uri: str) -> bytes:
        return b"fake-image"


class FakeInferenceClient:
    model_name = "fake-qwen"
    model_version = "test"

    def __init__(self, result: dict) -> None:
        self.result = result

    def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
    ) -> dict:
        return self.result


class FailingInferenceClient:
    model_name = "fake-qwen"
    model_version = "test"

    def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
    ) -> dict:
        raise RuntimeError("inference unavailable")


@pytest.fixture()
def engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'job_progress.db'}",
        future=True,
    )

    from packages.common import models  # noqa: F401

    Base.metadata.create_all(engine)

    yield engine

    engine.dispose()


def create_job_with_document(
    engine,
    *,
    total_documents: int = 1,
):
    job_id = uuid4()
    document_id = uuid4()

    with Session(engine) as session:
        job = JobModel(
            id=job_id,
            status="queued",
            total_documents=total_documents,
        )

        document = DocumentModel(
            id=document_id,
            job_id=job_id,
            source_uri="local://card.jpg",
            content_hash=str(uuid4()).replace("-", "")[:64],
            filename="card.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
            status="queued",
        )

        session.add(job)
        session.add(document)
        session.commit()

    return job_id, document_id


def test_successful_processing_updates_job_progress(
    engine,
):
    job_id, document_id = create_job_with_document(
        engine,
        total_documents=1,
    )

    inference = FakeInferenceClient(
        {
            "first_name": "John",
            "last_name": "Doe",
            "job_title": "CEO",
            "company": "Acme",
            "location": "Dubai",
            "phone_number": "+971501234567",
            "email_address": "john@acme.com",
        }
    )

    processor = DocumentProcessor(
        engine=engine,
        object_reader=FakeObjectReader(),
        inference_client=inference,
    )

    processor.process(
        job_id=job_id,
        document_id=document_id,
    )

    with Session(engine) as session:
        job = session.get(JobModel, job_id)

        assert job is not None
        assert job.processed_documents == 1
        assert job.successful_documents == 1
        assert job.failed_documents == 0
        assert job.status == "completed"
        assert job.started_at is not None
        assert job.completed_at is not None


def test_failed_processing_updates_job_progress(
    engine,
):
    job_id, document_id = create_job_with_document(
        engine,
        total_documents=1,
    )

    processor = DocumentProcessor(
        engine=engine,
        object_reader=FakeObjectReader(),
        inference_client=FailingInferenceClient(),
    )

    with pytest.raises(
        RuntimeError,
        match="inference unavailable",
    ):
        processor.process(
            job_id=job_id,
            document_id=document_id,
        )

    with Session(engine) as session:
        job = session.get(JobModel, job_id)

        assert job is not None
        assert job.processed_documents == 1
        assert job.successful_documents == 0
        assert job.failed_documents == 1
        assert job.status == "completed_with_errors"
        assert job.started_at is not None
        assert job.completed_at is not None


def test_multi_document_job_is_not_completed_early(
    engine,
):
    job_id, document_id = create_job_with_document(
        engine,
        total_documents=2,
    )

    inference = FakeInferenceClient(
        {
            "first_name": "John",
            "last_name": "Doe",
            "job_title": "CEO",
            "company": "Acme",
            "location": "Dubai",
            "phone_number": "+971501234567",
            "email_address": "john@acme.com",
        }
    )

    processor = DocumentProcessor(
        engine=engine,
        object_reader=FakeObjectReader(),
        inference_client=inference,
    )

    processor.process(
        job_id=job_id,
        document_id=document_id,
    )

    with Session(engine) as session:
        job = session.get(JobModel, job_id)

        assert job is not None
        assert job.processed_documents == 1
        assert job.successful_documents == 1
        assert job.failed_documents == 0
        assert job.status != "completed"
        assert job.completed_at is None