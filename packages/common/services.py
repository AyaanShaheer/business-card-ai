from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.common.models import DocumentModel, JobModel
from packages.common.repositories import DocumentRepository, JobRepository
from packages.common.transaction import transaction


class JobService:
    """Business operations for processing jobs."""

    def __init__(
        self,
        *,
        session: Session,
        repository: JobRepository,
        max_files_per_job: int = 50,
    ) -> None:
        self._session = session
        self._repository = repository
        self._max_files_per_job = max_files_per_job

    def create_job(self, *, total_documents: int) -> JobModel:
        if total_documents <= 0:
            raise ValueError(
                "total_documents must be greater than zero"
            )

        if total_documents > self._max_files_per_job:
            raise ValueError(
                f"total_documents exceeds maximum of "
                f"{self._max_files_per_job}"
            )

        with transaction(self._session):
            return self._repository.create(
                status="created",
                total_documents=total_documents,
            )

    def get_job(self, job_id: UUID) -> JobModel | None:
        return self._repository.get_by_id(job_id)


class DocumentService:
    """Business operations for uploaded documents."""

    ALLOWED_MIME_TYPES = frozenset(
        {
            "image/jpeg",
            "image/png",
            "image/webp",
        }
    )

    def __init__(
        self,
        *,
        session: Session,
        repository: DocumentRepository,
        max_file_size_bytes: int,
    ) -> None:
        self._session = session
        self._repository = repository
        self._max_file_size_bytes = max_file_size_bytes

    def create_document(
        self,
        *,
        job_id: UUID,
        source_uri: str,
        content_hash: str,
        filename: str,
        mime_type: str,
        size_bytes: int,
    ) -> DocumentModel:
        self._validate_document(
            source_uri=source_uri,
            content_hash=content_hash,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
        )

        # Fast path:
        # If this exact document already exists for this job,
        # return it without attempting another INSERT.
        existing = self._repository.get_by_content_hash(
            job_id=job_id,
            content_hash=content_hash,
        )

        if existing is not None:
            return existing

        try:
            with transaction(self._session):
                return self._repository.create(
                    job_id=job_id,
                    source_uri=source_uri,
                    content_hash=content_hash,
                    filename=filename,
                    mime_type=mime_type,
                    size_bytes=size_bytes,
                )

        except IntegrityError:
            # Another request may have inserted the same
            # (job_id, content_hash) between our initial lookup
            # and INSERT.
            #
            # The transaction context has already rolled back,
            # so it is now safe to query again.
            existing = self._repository.get_by_content_hash(
                job_id=job_id,
                content_hash=content_hash,
            )

            if existing is not None:
                return existing

            # This IntegrityError was caused by something else.
            # Never hide unrelated database failures.
            raise

    def _validate_document(
        self,
        *,
        source_uri: str,
        content_hash: str,
        filename: str,
        mime_type: str,
        size_bytes: int,
    ) -> None:
        if not source_uri.strip():
            raise ValueError("source_uri must not be empty")

        if not content_hash.strip():
            raise ValueError("content_hash must not be empty")

        if not filename.strip():
            raise ValueError("filename must not be empty")

        if mime_type not in self.ALLOWED_MIME_TYPES:
            raise ValueError(
                f"unsupported mime type: {mime_type}"
            )

        if size_bytes < 0:
            raise ValueError(
                "size_bytes must not be negative"
            )

        if size_bytes > self._max_file_size_bytes:
            raise ValueError(
                "file size exceeds configured maximum"
            )