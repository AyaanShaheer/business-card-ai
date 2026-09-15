from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.worker.processor import DocumentProcessor
from apps.worker.worker import Worker
from packages.common.db import Base
from packages.common.models import (
    DocumentModel,
    ExtractionModel,
    JobModel,
    LeadModel,
)
from packages.common.queue import (
    DocumentMessage,
    InMemoryQueue,
)


class FakeObjectReader:
    def read(self, *, source_uri: str) -> bytes:
        return b"fake-image"


class FakeInferenceClient:
    model_name = "fake-qwen"
    model_version = "test"

    def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
    ) -> dict:
        assert image_bytes == b"fake-image"
        assert mime_type == "image/jpeg"

        return {
            "first_name": "Ahmed",
            "last_name": "Khan",
            "job_title": "Software Engineer",
            "company": "Acme Technologies",
            "location": "Dubai, UAE",
            "phone_number": "+971501234567",
            "email_address": "ahmed@acme.com",
        }


def test_worker_processes_document_end_to_end(tmp_path):
    database_path = tmp_path / "worker_integration.db"

    engine = create_engine(
        f"sqlite:///{database_path}",
        future=True,
    )

    Base.metadata.create_all(engine)

    job_id = uuid4()
    document_id = uuid4()

    with Session(engine) as session:
        session.add(
            JobModel(
                id=job_id,
                status="queued",
                total_documents=1,
            )
        )

        session.add(
            DocumentModel(
                id=document_id,
                job_id=job_id,
                source_uri="local://card.jpg",
                content_hash="worker-integration-hash",
                filename="card.jpg",
                mime_type="image/jpeg",
                size_bytes=1024,
                status="queued",
            )
        )

        session.commit()

    queue = InMemoryQueue()

    queue.send(
        DocumentMessage(
            job_id=str(job_id),
            document_id=str(document_id),
        )
    )

    processor = DocumentProcessor(
        engine=engine,
        object_reader=FakeObjectReader(),
        inference_client=FakeInferenceClient(),
    )

    worker = Worker(
        queue=queue,
        processor=processor,
    )

    assert worker.process_one() is True
    assert worker.process_one() is False

    with Session(engine) as session:
        document = session.get(
            DocumentModel,
            document_id,
        )

        assert document is not None
        assert document.status == "extracted"
        assert document.attempt_count == 1

        extraction = (
            session.query(ExtractionModel)
            .filter(
                ExtractionModel.document_id == document_id,
            )
            .one()
        )

        assert extraction.status == "extracted"
        assert extraction.attempt_number == 1
        assert extraction.validation_status is True
        assert extraction.raw_output["company"] == "Acme Technologies"

        lead = (
            session.query(LeadModel)
            .filter(
                LeadModel.extraction_id == extraction.id,
            )
            .one()
        )

        assert lead.first_name == "Ahmed"
        assert lead.last_name == "Khan"
        assert lead.company == "Acme Technologies"
        assert lead.email_address == "ahmed@acme.com"

    engine.dispose()