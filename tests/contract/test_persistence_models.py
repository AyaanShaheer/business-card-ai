from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.common.db import Base
from packages.common.models import (
    DocumentModel,
    ExtractionModel,
    JobModel,
    LeadModel,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
    )

    Base.metadata.create_all(engine)

    with Session(engine) as db:
        yield db

    Base.metadata.drop_all(engine)


def test_job_can_be_persisted(session):
    job = JobModel(
        id=uuid4(),
        status="created",
        total_documents=10,
    )

    session.add(job)
    session.commit()

    stored = session.get(JobModel, job.id)

    assert stored is not None
    assert stored.total_documents == 10
    assert stored.processed_documents == 0


def test_document_belongs_to_job(session):
    job = JobModel(
        id=uuid4(),
        status="created",
        total_documents=1,
    )

    document = DocumentModel(
        id=uuid4(),
        job_id=job.id,
        source_uri="s3://bucket/card.jpg",
        content_hash="abc123",
        filename="card.jpg",
        mime_type="image/jpeg",
        size_bytes=1024,
        status="uploaded",
    )

    session.add(job)
    session.add(document)
    session.commit()

    stored = session.get(DocumentModel, document.id)

    assert stored is not None
    assert stored.job_id == job.id


def test_document_content_hash_is_indexed_and_stored(session):
    job = JobModel(
        id=uuid4(),
        status="created",
        total_documents=1,
    )

    document = DocumentModel(
        id=uuid4(),
        job_id=job.id,
        source_uri="s3://bucket/card.jpg",
        content_hash="sha256-test",
        filename="card.jpg",
        mime_type="image/jpeg",
        size_bytes=1000,
        status="uploaded",
    )

    session.add_all([job, document])
    session.commit()

    stored = session.get(DocumentModel, document.id)

    assert stored.content_hash == "sha256-test"


def test_document_rejects_negative_size(session):
    job = JobModel(
        id=uuid4(),
        status="created",
        total_documents=1,
    )

    document = DocumentModel(
        id=uuid4(),
        job_id=job.id,
        source_uri="s3://bucket/card.jpg",
        content_hash="abc123",
        filename="card.jpg",
        mime_type="image/jpeg",
        size_bytes=-1,
        status="uploaded",
    )

    session.add_all([job, document])

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_multiple_extraction_attempts_can_exist(session):
    job = JobModel(
        id=uuid4(),
        status="processing",
        total_documents=1,
    )

    document = DocumentModel(
        id=uuid4(),
        job_id=job.id,
        source_uri="s3://bucket/card.jpg",
        content_hash="abc123",
        filename="card.jpg",
        mime_type="image/jpeg",
        size_bytes=1000,
        status="processing",
    )

    extraction_1 = ExtractionModel(
        id=uuid4(),
        document_id=document.id,
        attempt_number=1,
        model_name="Qwen3-VL",
        model_version="4B",
        status="failed",
        validation_status=False,
        processing_latency_ms=3000,
    )

    extraction_2 = ExtractionModel(
        id=uuid4(),
        document_id=document.id,
        attempt_number=2,
        model_name="Qwen3-VL",
        model_version="4B",
        status="extracted",
        validation_status=True,
        processing_latency_ms=2500,
    )

    session.add_all([job, document, extraction_1, extraction_2])
    session.commit()

    assert len(document.extractions) == 2


def test_lead_is_linked_to_successful_extraction(session):
    job = JobModel(
        id=uuid4(),
        status="completed",
        total_documents=1,
        processed_documents=1,
        successful_documents=1,
    )

    document = DocumentModel(
        id=uuid4(),
        job_id=job.id,
        source_uri="s3://bucket/card.jpg",
        content_hash="abc123",
        filename="card.jpg",
        mime_type="image/jpeg",
        size_bytes=1000,
        status="extracted",
    )

    extraction = ExtractionModel(
        id=uuid4(),
        document_id=document.id,
        attempt_number=1,
        model_name="Qwen3-VL",
        model_version="4B",
        status="extracted",
        validation_status=True,
        processing_latency_ms=2000,
    )

    lead = LeadModel(
        id=uuid4(),
        extraction_id=extraction.id,
        document_id=document.id,
        first_name="John",
        last_name="Smith",
        company="Acme",
        email_address="john@acme.com",
    )

    session.add_all([job, document, extraction, lead])
    session.commit()

    stored = session.get(LeadModel, lead.id)

    assert stored is not None
    assert stored.email_address == "john@acme.com"
    assert stored.extraction_id == extraction.id


def test_job_relationship_loads_documents(session):
    job = JobModel(
        id=uuid4(),
        status="created",
        total_documents=2,
    )

    document_1 = DocumentModel(
        id=uuid4(),
        job_id=job.id,
        source_uri="s3://bucket/card1.jpg",
        content_hash="hash1",
        filename="card1.jpg",
        mime_type="image/jpeg",
        size_bytes=1000,
        status="uploaded",
    )

    document_2 = DocumentModel(
        id=uuid4(),
        job_id=job.id,
        source_uri="s3://bucket/card2.jpg",
        content_hash="hash2",
        filename="card2.jpg",
        mime_type="image/jpeg",
        size_bytes=1000,
        status="uploaded",
    )

    session.add_all([job, document_1, document_2])
    session.commit()

    assert len(job.documents) == 2