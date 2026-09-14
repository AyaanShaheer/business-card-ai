from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from packages.schemas.domain import (
    Document,
    DocumentStatus,
    Export,
    ExportFormat,
    ExportStatus,
    Extraction,
    ExtractionStatus,
    Job,
    JobStatus,
    Lead,
    ReviewStatus,
)


def test_lead_accepts_fully_populated_record():
    lead = Lead(
        first_name="John",
        last_name="Smith",
        job_title="CEO",
        company="Acme Corporation",
        location="Dubai, UAE",
        phone_number="+971501234567",
        email_address="john@acme.com",
    )

    assert lead.first_name == "John"
    assert lead.last_name == "Smith"
    assert lead.email_address == "john@acme.com"


def test_lead_allows_missing_fields():
    lead = Lead(
        first_name="John",
        last_name="Smith",
        company="Acme Corporation",
        email_address="john@acme.com",
    )

    assert lead.job_title is None
    assert lead.location is None
    assert lead.phone_number is None


def test_lead_rejects_invalid_email():
    with pytest.raises(ValidationError):
        Lead(
            first_name="John",
            last_name="Smith",
            email_address="john@acme",
        )


def test_lead_rejects_unexpected_fields():
    with pytest.raises(ValidationError):
        Lead(
            first_name="John",
            company="Acme",
            salary="500000",
        )


def test_document_requires_valid_status():
    document = Document(
        document_id=uuid4(),
        job_id=uuid4(),
        source_uri="s3://bucket/original/card.jpg",
        content_hash="abc123",
        filename="card.jpg",
        mime_type="image/jpeg",
        size_bytes=1024,
        status=DocumentStatus.UPLOADED,
    )

    assert document.status == DocumentStatus.UPLOADED


def test_document_rejects_negative_size():
    with pytest.raises(ValidationError):
        Document(
            document_id=uuid4(),
            job_id=uuid4(),
            source_uri="s3://bucket/card.jpg",
            content_hash="abc123",
            filename="card.jpg",
            mime_type="image/jpeg",
            size_bytes=-1,
            status=DocumentStatus.UPLOADED,
        )


def test_document_attempt_count_cannot_be_negative():
    with pytest.raises(ValidationError):
        Document(
            document_id=uuid4(),
            job_id=uuid4(),
            source_uri="s3://bucket/card.jpg",
            content_hash="abc123",
            filename="card.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
            status=DocumentStatus.UPLOADED,
            attempt_count=-1,
        )


def test_job_defaults_to_zero_counts():
    job = Job(
        job_id=uuid4(),
        status=JobStatus.QUEUED,
        total_documents=10,
    )

    assert job.processed_documents == 0
    assert job.successful_documents == 0
    assert job.failed_documents == 0
    assert job.review_documents == 0


def test_job_rejects_negative_counts():
    with pytest.raises(ValidationError):
        Job(
            job_id=uuid4(),
            status=JobStatus.QUEUED,
            total_documents=-1,
        )


def test_extraction_stores_model_metadata():
    extraction = Extraction(
        extraction_id=uuid4(),
        document_id=uuid4(),
        model_name="Qwen3-VL",
        model_version="4B",
        status=ExtractionStatus.EXTRACTED,
        review_status=ReviewStatus.HIGH,
        validation_status=True,
        processing_latency_ms=1200,
    )

    assert extraction.model_name == "Qwen3-VL"
    assert extraction.model_version == "4B"
    assert extraction.processing_latency_ms == 1200


def test_extraction_latency_cannot_be_negative():
    with pytest.raises(ValidationError):
        Extraction(
            extraction_id=uuid4(),
            document_id=uuid4(),
            model_name="Qwen3-VL",
            model_version="4B",
            status=ExtractionStatus.EXTRACTED,
            processing_latency_ms=-1,
        )


def test_export_schema():
    export = Export(
        export_id=uuid4(),
        job_id=uuid4(),
        status=ExportStatus.QUEUED,
        format=ExportFormat.XLSX,
    )

    assert export.format == ExportFormat.XLSX
    assert export.status == ExportStatus.QUEUED


def test_uuid_fields_are_real_uuids():
    job_id = uuid4()

    job = Job(
        job_id=job_id,
        status=JobStatus.CREATED,
        total_documents=1,
    )

    assert isinstance(job.job_id, UUID)
    assert job.job_id == job_id


def test_datetime_defaults_are_timezone_aware():
    job = Job(
        job_id=uuid4(),
        status=JobStatus.CREATED,
        total_documents=1,
    )

    assert isinstance(job.created_at, datetime)
    assert job.created_at.tzinfo is not None
    assert job.created_at.utcoffset() is not None


def test_document_mime_type_must_be_string():
    with pytest.raises(ValidationError):
        Document(
            document_id=uuid4(),
            job_id=uuid4(),
            source_uri="s3://bucket/card.jpg",
            content_hash="abc123",
            filename="card.jpg",
            mime_type=None,
            size_bytes=1024,
            status=DocumentStatus.UPLOADED,
        )