from uuid import UUID

from sqlalchemy.orm import Session

from packages.common.models import DocumentModel, JobModel, LeadModel


class JobRepository:
    """Data-access operations for jobs."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        status: str,
        total_documents: int,
    ) -> JobModel:
        job = JobModel(
            status=status,
            total_documents=total_documents,
        )

        self._session.add(job)
        self._session.flush()

        return job

    def get_by_id(self, job_id: UUID) -> JobModel | None:
        return self._session.get(JobModel, job_id)

    def update_status(
        self,
        job_id: UUID,
        status: str,
    ) -> JobModel | None:
        job = self.get_by_id(job_id)

        if job is None:
            return None

        job.status = status
        self._session.flush()

        return job

class DocumentRepository:
    """Data-access operations for documents."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        job_id: UUID,
        source_uri: str,
        content_hash: str,
        filename: str,
        mime_type: str,
        size_bytes: int,
        status: str = "uploaded",
    ) -> DocumentModel:
        document = DocumentModel(
            job_id=job_id,
            source_uri=source_uri,
            content_hash=content_hash,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            status=status,
        )

        self._session.add(document)
        self._session.flush()

        return document

    def get_by_id(
        self,
        document_id: UUID,
    ) -> DocumentModel | None:
        return self._session.get(DocumentModel, document_id)

    def get_by_content_hash(
        self,
        *,
        job_id: UUID,
        content_hash: str,
    ) -> DocumentModel | None:
        return (
            self._session.query(DocumentModel)
            .filter(
                DocumentModel.job_id == job_id,
                DocumentModel.content_hash == content_hash,
            )
            .one_or_none()
        )


class LeadRepository:
    """Data-access operations for leads."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_job_id(
        self,
        job_id: UUID,
    ) -> list[LeadModel]:
        return (
            self._session.query(LeadModel)
            .filter(LeadModel.document_id.in_(
                self._session.query(DocumentModel.id).filter(
                    DocumentModel.job_id == job_id,
                )
            ))
            .all()
        )