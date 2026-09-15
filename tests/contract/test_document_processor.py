from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.worker.processor import DocumentProcessor
from packages.common.db import Base
from packages.common.models import (
    DocumentModel,
    ExtractionModel,
    JobModel,
    LeadModel,
)


class FakeObjectReader:
    def read(self, *, source_uri: str) -> bytes:
        return b"fake-image"


class FakeInferenceClient:
    model_name = "fake-qwen"
    model_version = "test"

    def __init__(self, result: dict) -> None:
        self.result = result
        self.received_image = None
        self.received_mime_type = None

    def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
    ) -> dict:
        self.received_image = image_bytes
        self.received_mime_type = mime_type

        return self.result


class FailingInferenceClient:
    model_name = "qwen/test"
    model_version = "qwen/test"

    def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
    ) -> dict:
        raise RuntimeError("remote inference unavailable")


@pytest.fixture()
def engine(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'processor.db'}"

    engine = create_engine(
        database_url,
        future=True,
    )

    # Import models so all ORM tables are registered with Base.metadata.
    from packages.common import models  # noqa: F401

    Base.metadata.create_all(engine)

    yield engine

    engine.dispose()


@pytest.fixture()
def document_context(engine):
    job_id = uuid4()
    document_id = uuid4()

    with Session(engine) as session:
        job = JobModel(
            id=job_id,
            status="processing",
            total_documents=1,
        )

        document = DocumentModel(
            id=document_id,
            job_id=job_id,
            source_uri="local://card.jpg",
            content_hash="processor-test-hash",
            filename="card.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
            status="queued",
        )

        session.add(job)
        session.add(document)
        session.commit()

    return job_id, document_id


def test_processor_persists_extraction_and_lead(
    engine,
    document_context,
):
    job_id, document_id = document_context

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

    assert inference.received_image == b"fake-image"
    assert inference.received_mime_type == "image/jpeg"

    with Session(engine) as session:
        document = session.get(
            DocumentModel,
            document_id,
        )

        assert document is not None
        assert document.status == "extracted"
        assert document.attempt_count == 1

        extraction = (
            session.query(ExtractionModel)
            .filter(
                ExtractionModel.document_id == document_id
            )
            .one()
        )

        assert extraction.status == "extracted"
        assert extraction.attempt_number == 1
        assert extraction.validation_status is True
        assert extraction.raw_output["company"] == "Acme"

        lead = (
            session.query(LeadModel)
            .filter(
                LeadModel.extraction_id == extraction.id
            )
            .one()
        )

        assert lead.first_name == "John"
        assert lead.last_name == "Doe"
        assert lead.job_title == "CEO"
        assert lead.company == "Acme"
        assert lead.location == "Dubai"
        assert lead.phone_number == "+971501234567"
        assert lead.email_address == "john@acme.com"


def test_processor_rejects_invalid_inference_output(
    engine,
    document_context,
):
    job_id, document_id = document_context

    inference = FakeInferenceClient(
        {
            "first_name": "John",
            "email_address": "not-an-email",
        }
    )

    processor = DocumentProcessor(
        engine=engine,
        object_reader=FakeObjectReader(),
        inference_client=inference,
    )

    with pytest.raises(ValueError):
        processor.process(
            job_id=job_id,
            document_id=document_id,
        )

    with Session(engine) as session:
        document = session.get(
            DocumentModel,
            document_id,
        )

        assert document is not None
        assert document.status == "failed"
        assert document.attempt_count == 1


def test_processor_fails_for_unknown_document(engine):
    inference = FakeInferenceClient(
        {
            "first_name": "John",
        }
    )

    processor = DocumentProcessor(
        engine=engine,
        object_reader=FakeObjectReader(),
        inference_client=inference,
    )

    with pytest.raises(
        ValueError,
        match="document not found",
    ):
        processor.process(
            job_id=uuid4(),
            document_id=uuid4(),
        )


def test_inference_failure_marks_document_failed(
    engine,
    document_context,
):
    job_id, document_id = document_context

    processor = DocumentProcessor(
        engine=engine,
        object_reader=FakeObjectReader(),
        inference_client=FailingInferenceClient(),
    )

    with pytest.raises(
        RuntimeError,
        match="remote inference unavailable",
    ):
        processor.process(
            job_id=job_id,
            document_id=document_id,
        )

    with Session(engine) as session:
        document = session.get(
            DocumentModel,
            document_id,
        )

        assert document is not None
        assert document.status == "failed"
        assert document.attempt_count == 1