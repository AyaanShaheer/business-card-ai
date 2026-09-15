from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.worker.processor import DocumentProcessor
from packages.common.db import Base
from packages.common.models import (
    DocumentModel,
    JobModel,
    LeadModel,
)


class FakeObjectReader:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def read(self, *, source_uri: str) -> bytes:
        return self.content


class FakeInferenceClient:
    model_name = "fake-qwen"
    model_version = "test"

    def __init__(self) -> None:
        self.received_image = None
        self.received_mime_type = None

    def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
    ) -> dict:
        self.received_image = image_bytes
        self.received_mime_type = mime_type

        return {
            "first_name": "Ahmed",
            "last_name": "Khan",
            "job_title": "CEO",
            "company": "Acme",
            "location": "Dubai",
            "phone_number": "+971501234567",
            "email_address": "ahmed@acme.com",
        }


def test_processor_reads_object_before_inference(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'processor.db'}",
        future=True,
    )

    Base.metadata.create_all(engine)

    job_id = uuid4()
    document_id = uuid4()

    with Session(engine) as session:
        session.add(
            JobModel(
                id=job_id,
                status="processing",
                total_documents=1,
            )
        )

        session.add(
            DocumentModel(
                id=document_id,
                job_id=job_id,
                source_uri="local://card.jpg",
                content_hash="reader-test-hash",
                filename="card.jpg",
                mime_type="image/jpeg",
                size_bytes=5,
                status="queued",
            )
        )

        session.commit()

    image_bytes = b"12345"

    reader = FakeObjectReader(image_bytes)
    inference = FakeInferenceClient()

    processor = DocumentProcessor(
        engine=engine,
        object_reader=reader,
        inference_client=inference,
    )

    processor.process(
        job_id=job_id,
        document_id=document_id,
    )

    assert inference.received_image == image_bytes
    assert inference.received_mime_type == "image/jpeg"

    with Session(engine) as session:
        lead = (
            session.query(LeadModel)
            .filter(
                LeadModel.document_id == document_id,
            )
            .one()
        )

        assert lead.company == "Acme"

    engine.dispose()