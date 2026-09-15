import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.common.models import DocumentModel, JobModel
from packages.common.repositories import DocumentRepository
from packages.common.services import DocumentService


DATABASE_URL = os.getenv("DATABASE_URL")

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def engine():
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL is not configured")

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
    )

    yield engine

    engine.dispose()


@pytest.fixture()
def job_id(engine):
    job_id = uuid4()

    with Session(engine) as session:
        session.add(
            JobModel(
                id=job_id,
                status="created",
                total_documents=2,
            )
        )
        session.commit()

    yield job_id

    with Session(engine) as session:
        job = session.get(JobModel, job_id)

        if job is not None:
            session.delete(job)
            session.commit()


class SynchronizedDocumentRepository(DocumentRepository):
    """
    Repository used only by this integration test to force both
    concurrent requests through the initial existence check before
    either one attempts the INSERT.
    """

    def __init__(
        self,
        session: Session,
        barrier: Barrier,
    ) -> None:
        super().__init__(session)
        self._barrier = barrier
        self._initial_lookup_completed = False

    def get_by_content_hash(
        self,
        *,
        job_id: UUID,
        content_hash: str,
    ) -> DocumentModel | None:
        result = super().get_by_content_hash(
            job_id=job_id,
            content_hash=content_hash,
        )

        # Synchronize ONLY the first lookup.
        #
        # The service may call get_by_content_hash() again after
        # catching IntegrityError. That recovery lookup must NOT
        # wait on the barrier.
        if not self._initial_lookup_completed:
            self._initial_lookup_completed = True
            self._barrier.wait()

        return result


def create_document(
    engine,
    job_id: UUID,
    barrier: Barrier,
    source_uri: str,
) -> UUID:
    with Session(engine) as session:
        repository = SynchronizedDocumentRepository(
            session=session,
            barrier=barrier,
        )

        service = DocumentService(
            session=session,
            repository=repository,
            max_file_size_bytes=10 * 1024 * 1024,
        )

        document = service.create_document(
            job_id=job_id,
            source_uri=source_uri,
            content_hash="service-race-hash",
            filename="business-card.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
        )

        return document.id


def test_concurrent_service_calls_are_idempotent(
    engine,
    job_id,
):
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                create_document,
                engine,
                job_id,
                barrier,
                "s3://bucket/card-a.jpg",
            ),
            executor.submit(
                create_document,
                engine,
                job_id,
                barrier,
                "s3://bucket/card-b.jpg",
            ),
        ]

        document_ids = [
            future.result()
            for future in futures
        ]

    # Both requests must complete successfully.
    assert len(document_ids) == 2

    # Both requests must resolve to the exact same persisted document.
    assert document_ids[0] == document_ids[1]

    # Exactly one document must exist in PostgreSQL.
    with Session(engine) as session:
        documents = (
            session.query(DocumentModel)
            .filter(
                DocumentModel.job_id == job_id,
                DocumentModel.content_hash == "service-race-hash",
            )
            .all()
        )

        assert len(documents) == 1
        assert documents[0].id == document_ids[0]