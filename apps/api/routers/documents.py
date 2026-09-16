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
from apps.api.schemas import (
    BulkUploadFileResult,
    BulkUploadResponse,
    DocumentResponse,
)
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

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


def _process_single_upload(
    *,
    job_id: UUID,
    file: UploadFile,
    content: bytes,
    session: Session,
) -> DocumentResponse:
    """Validate, store, and persist a single uploaded file.

    Raises ValueError for validation failures.
    """
    content_hash = hashlib.sha256(content).hexdigest()

    doc_repo = DocumentRepository(session)

    # Fast idempotency path.
    existing = doc_repo.get_by_content_hash(
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
        repository=doc_repo,
        max_file_size_bytes=MAX_FILE_SIZE_BYTES,
    )

    document = service.create_document(
        job_id=job_id,
        source_uri=source_uri,
        content_hash=content_hash,
        filename=file.filename or "unknown",
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
    )

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

    return _process_single_upload(
        job_id=job_id,
        file=file,
        content=content,
        session=session,
    )


@router.post(
    "/bulk",
    response_model=BulkUploadResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_documents_bulk(
    job_id: UUID,
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_db_session),
) -> BulkUploadResponse:
    """Upload multiple business card images in one request.

    Each file is validated independently — one failure does not
    prevent other files from being accepted.
    """
    job_repository = JobRepository(session)

    job = job_repository.get_by_id(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="job not found",
        )

    if not files:
        raise HTTPException(
            status_code=422,
            detail="at least one file is required",
        )

    results: list[BulkUploadFileResult] = []
    accepted = 0
    rejected = 0

    for file in files:
        filename = file.filename or "unknown"

        try:
            if file.content_type is None:
                raise ValueError("file content type is required")

            content = await file.read()

            doc_response = _process_single_upload(
                job_id=job_id,
                file=file,
                content=content,
                session=session,
            )

            results.append(
                BulkUploadFileResult(
                    filename=filename,
                    success=True,
                    document_id=doc_response.document_id,
                )
            )
            accepted += 1

        except (ValueError, Exception) as exc:
            results.append(
                BulkUploadFileResult(
                    filename=filename,
                    success=False,
                    error=str(exc),
                )
            )
            rejected += 1

    if accepted > 0:
        job.total_documents = accepted
        session.commit()

    return BulkUploadResponse(
        job_id=job_id,
        accepted=accepted,
        rejected=rejected,
        results=results,
    )