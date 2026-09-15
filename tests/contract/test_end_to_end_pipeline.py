from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.dependencies import get_db_session
from apps.api.main import app
from apps.api.routers import documents
from apps.worker.processor import DocumentProcessor
from apps.worker.worker import Worker
from packages.common.db import Base
from packages.common.models import DocumentModel, ExtractionModel, LeadModel
from packages.common.queue import InMemoryQueue


class FakeStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def put(
        self,
        *,
        job_id: UUID,
        document_id: UUID,
        filename: str,
        content: bytes,
    ) -> str:
        path = self.root / str(document_id)
        path.write_bytes(content)
        return f"local://{path}"


class FakeObjectReader:
    def read(self, *, source_uri: str) -> bytes:
        path = Path(source_uri.removeprefix("local://"))
        return path.read_bytes()


class FakeInferenceClient:
    model_name = "qwen/test"
    model_version = "test"

    def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
    ) -> dict:
        assert image_bytes
        assert mime_type == "image/jpeg"

        return {
            "first_name": "John",
            "last_name": "Doe",
            "job_title": "CEO",
            "company": "Acme",
            "location": "Dubai",
            "phone_number": "+971501234567",
            "email_address": "john@acme.com",
        }


@pytest.fixture()
def e2e_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'e2e.db'}",
        future=True,
    )

    from packages.common import models  # noqa: F401

    Base.metadata.create_all(engine)

    yield engine

    engine.dispose()


@pytest.fixture()
def e2e_session_factory(e2e_engine):
    return sessionmaker(
        bind=e2e_engine,
        autoflush=False,
        expire_on_commit=False,
    )


@pytest.fixture()
def e2e_client(
    e2e_session_factory,
    tmp_path,
):
    queue = InMemoryQueue()
    storage = FakeStorage(tmp_path / "objects")
    storage.root.mkdir(parents=True, exist_ok=True)

    original_queue = documents.queue
    original_storage = documents.storage

    documents.queue = queue
    documents.storage = storage

    def override_get_db_session() -> Iterator[Session]:
        session = e2e_session_factory()

        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as client:
        yield client, queue, storage

    app.dependency_overrides.clear()
    documents.queue = original_queue
    documents.storage = original_storage


def test_upload_to_worker_persists_lead(
    e2e_client,
    e2e_engine,
):
    client, queue, _storage = e2e_client

    job_response = client.post(
        "/jobs",
        json={"total_documents": 1},
    )

    assert job_response.status_code == 201

    job_id = job_response.json()["job_id"]

    image_bytes = b"fake-business-card-image"

    upload_response = client.post(
        f"/jobs/{job_id}/documents",
        files={
            "file": (
                "card.jpg",
                image_bytes,
                "image/jpeg",
            )
        },
    )

    assert upload_response.status_code == 201

    document_payload = upload_response.json()

    document_id = UUID(
        document_payload["document_id"]
    )

    # The upload must have placed exactly one message on the queue.
    assert queue._queue.qsize() == 1

    worker = Worker(
        queue=queue,
        processor=DocumentProcessor(
            engine=e2e_engine,
            object_reader=FakeObjectReader(),
            inference_client=FakeInferenceClient(),
        ),
    )

    assert worker.process_one() is True

    # Queue should now be empty.
    assert queue.receive() is None

    with Session(e2e_engine) as session:
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

        lead = (
            session.query(LeadModel)
            .filter(
                LeadModel.extraction_id == extraction.id,
            )
            .one()
        )

        assert lead.first_name == "John"
        assert lead.last_name == "Doe"
        assert lead.company == "Acme"
        assert lead.email_address == "john@acme.com"

def test_duplicate_upload_does_not_enqueue_second_message(
    e2e_client,
):
    client, queue, _storage = e2e_client

    job_response = client.post(
        "/jobs",
        json={"total_documents": 1},
    )

    assert job_response.status_code == 201

    job_id = job_response.json()["job_id"]

    image_bytes = b"same-business-card"

    first_response = client.post(
        f"/jobs/{job_id}/documents",
        files={
            "file": (
                "card.jpg",
                image_bytes,
                "image/jpeg",
            )
        },
    )

    assert first_response.status_code == 201

    first_message = queue.receive()
    assert first_message is not None

    second_response = client.post(
        f"/jobs/{job_id}/documents",
        files={
            "file": (
                "different-name.jpg",
                image_bytes,
                "image/jpeg",
            )
        },
    )

    assert second_response.status_code == 201

    assert queue.receive() is None

    assert (
        second_response.json()["document_id"]
        == first_response.json()["document_id"]
    )