import hashlib
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from apps.api.schemas import DocumentResponse
from packages.common.queue import DocumentMessage, InMemoryQueue
from packages.common.repositories import DocumentRepository, JobRepository
from packages.common.services import DocumentService
from packages.common.storage import ObjectStorage


router = APIRouter(
    prefix="/jobs/{job_id}/documents",
    tags=["documents"],
)

storage = ObjectStorage()
queue = InMemoryQueue()

@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    job_id: UUID,
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
) -> DocumentResponse:
    job_repository = JobRepository(session)

    job = job_repository.get_by_id(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="job not found",
        )

    if file.content_type is None:
        raise HTTPException(
            status_code=422,
            detail="file content type is required",
        )

    content = await file.read()

    content_hash = hashlib.sha256(content).hexdigest()

    repository = DocumentRepository(session)

    # Fast idempotency path.
    existing = repository.get_by_content_hash(
        job_id=job_id,
        content_hash=content_hash,
    )

    if existing is not None:
        return DocumentResponse(
            document_id=existing.id,
            job_id=existing.job_id,
            filename=existing.filename,
            mime_type=existing.mime_type,
            size_bytes=existing.size_bytes,
            content_hash=existing.content_hash,
            status=existing.status,
        )

    document_id = uuid4()

    source_uri = storage.put(
        job_id=job_id,
        document_id=document_id,
        filename=file.filename or "unknown",
        content=content,
    )

    service = DocumentService(
        session=session,
        repository=repository,
        max_file_size_bytes=10 * 1024 * 1024,
    )

    document = service.create_document(
        job_id=job_id,
        source_uri=source_uri,
        content_hash=content_hash,
        filename=file.filename or "unknown",
        mime_type=file.content_type,
        size_bytes=len(content),
    )

    # Only publish a message when a new document was actually created.
    queue.send(
        DocumentMessage(
            job_id=str(document.job_id),
            document_id=str(document.id),
        )
    )

    return DocumentResponse(
        document_id=document.id,
        job_id=document.job_id,
        filename=document.filename,
        mime_type=document.mime_type,
        size_bytes=document.size_bytes,
        content_hash=document.content_hash,
        status=document.status,
    )