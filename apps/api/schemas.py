from uuid import UUID

from pydantic import BaseModel, Field


class CreateJobRequest(BaseModel):
    total_documents: int = Field(gt=0)


class JobResponse(BaseModel):
    job_id: UUID
    status: str
    total_documents: int

class DocumentResponse(BaseModel):
    document_id: UUID
    job_id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    content_hash: str
    status: str