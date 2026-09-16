from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateJobRequest(BaseModel):
    total_documents: int = Field(gt=0)


class JobResponse(BaseModel):
    job_id: UUID
    status: str
    total_documents: int


class JobStatusResponse(BaseModel):
    """Full job status with progress tracking."""

    job_id: UUID
    status: str
    total_documents: int
    processed_documents: int
    successful_documents: int
    failed_documents: int
    review_documents: int
    progress_percent: float
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class DocumentResponse(BaseModel):
    document_id: UUID
    job_id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    content_hash: str
    status: str


class BulkUploadFileResult(BaseModel):
    """Per-file result within a bulk upload."""

    filename: str
    success: bool
    document_id: UUID | None = None
    error: str | None = None


class BulkUploadResponse(BaseModel):
    """Aggregate result of a bulk upload."""

    job_id: UUID
    accepted: int
    rejected: int
    results: list[BulkUploadFileResult]


class LeadResponse(BaseModel):
    """Single extracted lead."""

    lead_id: UUID
    document_id: UUID
    first_name: str | None
    last_name: str | None
    job_title: str | None
    company: str | None
    location: str | None
    phone_number: str | None
    email_address: str | None


class LeadListResponse(BaseModel):
    """Lead list for a job."""

    job_id: UUID
    total: int
    items: list[LeadResponse]