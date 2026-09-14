from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class JobStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


class ExtractionStatus(StrEnum):
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    VALIDATION_FAILED = "validation_failed"
    FAILED = "failed"


class ReviewStatus(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    REQUIRED = "required"


class ExportStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportFormat(StrEnum):
    XLSX = "xlsx"


class SchemaBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )


class Lead(SchemaBase):
    first_name: str | None = None
    last_name: str | None = None
    job_title: str | None = None
    company: str | None = None
    location: str | None = None
    phone_number: str | None = None
    email_address: EmailStr | None = None


class Document(SchemaBase):
    document_id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    source_uri: str
    content_hash: str
    filename: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    status: DocumentStatus
    attempt_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Extraction(SchemaBase):
    extraction_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    model_name: str
    model_version: str
    status: ExtractionStatus
    raw_output: str | None = None
    validation_status: bool = False
    review_status: ReviewStatus = ReviewStatus.REQUIRED
    processing_latency_ms: int | None = Field(default=None, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Job(SchemaBase):
    job_id: UUID = Field(default_factory=uuid4)
    status: JobStatus
    total_documents: int = Field(ge=0)
    processed_documents: int = Field(default=0, ge=0)
    successful_documents: int = Field(default=0, ge=0)
    failed_documents: int = Field(default=0, ge=0)
    review_documents: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None


class Export(SchemaBase):
    export_id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    status: ExportStatus
    format: ExportFormat
    output_uri: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None