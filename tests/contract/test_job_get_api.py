"""Tests for GET /jobs/{job_id} status endpoint."""

from collections.abc import Iterator
from io import BytesIO
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
from packages.common.queue import InMemoryQueue


client = TestClient(app)


def test_get_job_returns_status_for_existing_job():
    """A freshly created job should return full status."""
    create_resp = client.post(
        "/jobs",
        json={"total_documents": 5},
    )

    assert create_resp.status_code == 201

    job_id = create_resp.json()["job_id"]

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200

    body = response.json()

    assert body["job_id"] == job_id
    assert body["status"] == "created"
    assert body["total_documents"] == 5
    assert body["processed_documents"] == 0
    assert body["successful_documents"] == 0
    assert body["failed_documents"] == 0
    assert body["review_documents"] == 0
    assert body["progress_percent"] == 0.0
    assert body["created_at"] is not None
    assert body["started_at"] is None
    assert body["completed_at"] is None


def test_get_job_returns_404_for_unknown_job():
    response = client.get(
        "/jobs/00000000-0000-0000-0000-000000000000",
    )

    assert response.status_code == 404


def test_get_job_new_job_has_zero_progress():
    create_resp = client.post(
        "/jobs",
        json={"total_documents": 10},
    )

    job_id = create_resp.json()["job_id"]

    body = client.get(f"/jobs/{job_id}").json()

    assert body["processed_documents"] == 0
    assert body["successful_documents"] == 0
    assert body["failed_documents"] == 0
    assert body["progress_percent"] == 0.0


# ── Integration tests that need isolated DB ──


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
        return {
            "first_name": "Jane",
            "last_name": "Smith",
            "job_title": "CTO",
            "company": "TechCo",
            "location": "London",
            "phone_number": "+44123456789",
            "email_address": "jane@techco.com",
        }


class FailingInferenceClient:
    model_name = "qwen/test"
    model_version = "test"

    def extract(self, *, image_bytes: bytes, mime_type: str) -> dict:
        raise RuntimeError("inference failed")


@pytest.fixture()
def isolated_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        future=True,
    )

    from packages.common import models  # noqa: F401

    Base.metadata.create_all(engine)

    yield engine

    engine.dispose()


@pytest.fixture()
def isolated_client(isolated_engine, tmp_path):
    session_factory = sessionmaker(
        bind=isolated_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    queue = InMemoryQueue()
    storage = FakeStorage(tmp_path / "objects")
    storage.root.mkdir(parents=True, exist_ok=True)

    original_queue = documents.queue
    original_storage = documents.storage

    documents.queue = queue
    documents.storage = storage

    def override_session() -> Iterator[Session]:
        session = session_factory()

        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_session

    with TestClient(app) as test_client:
        yield test_client, queue, isolated_engine

    app.dependency_overrides.clear()
    documents.queue = original_queue
    documents.storage = original_storage


def _upload_card(
    test_client: TestClient,
    job_id: str,
    name: str = "card.jpg",
    content: bytes = b"fake-image",
) -> dict:
    resp = test_client.post(
        f"/jobs/{job_id}/documents",
        files={
            "file": (name, BytesIO(content), "image/jpeg"),
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_successful_processing_updates_counters(
    isolated_client,
):
    test_client, queue, engine = isolated_client

    job = test_client.post(
        "/jobs", json={"total_documents": 1}
    ).json()
    job_id = job["job_id"]

    _upload_card(test_client, job_id)

    worker = Worker(
        queue=queue,
        processor=DocumentProcessor(
            engine=engine,
            object_reader=FakeObjectReader(),
            inference_client=FakeInferenceClient(),
        ),
    )

    worker.process_one()

    body = test_client.get(f"/jobs/{job_id}").json()

    assert body["status"] == "completed"
    assert body["processed_documents"] == 1
    assert body["successful_documents"] == 1
    assert body["failed_documents"] == 0
    assert body["progress_percent"] == 100.0
    assert body["started_at"] is not None
    assert body["completed_at"] is not None


def test_failed_processing_updates_counters(
    isolated_client,
):
    test_client, queue, engine = isolated_client

    job = test_client.post(
        "/jobs", json={"total_documents": 1}
    ).json()
    job_id = job["job_id"]

    _upload_card(test_client, job_id)

    worker = Worker(
        queue=queue,
        processor=DocumentProcessor(
            engine=engine,
            object_reader=FakeObjectReader(),
            inference_client=FailingInferenceClient(),
        ),
    )

    with pytest.raises(RuntimeError):
        worker.process_one()

    body = test_client.get(f"/jobs/{job_id}").json()

    assert body["status"] == "completed_with_errors"
    assert body["processed_documents"] == 1
    assert body["successful_documents"] == 0
    assert body["failed_documents"] == 1
    assert body["progress_percent"] == 100.0


def test_completed_job_reports_completed(
    isolated_client,
):
    test_client, queue, engine = isolated_client

    job = test_client.post(
        "/jobs", json={"total_documents": 1}
    ).json()
    job_id = job["job_id"]

    _upload_card(test_client, job_id)

    Worker(
        queue=queue,
        processor=DocumentProcessor(
            engine=engine,
            object_reader=FakeObjectReader(),
            inference_client=FakeInferenceClient(),
        ),
    ).process_one()

    body = test_client.get(f"/jobs/{job_id}").json()

    assert body["status"] == "completed"
    assert body["completed_at"] is not None


def test_partial_progress_percent(isolated_client):
    """Processing 1 of 3 documents → ~33.3%."""
    test_client, queue, engine = isolated_client

    job = test_client.post(
        "/jobs", json={"total_documents": 3}
    ).json()
    job_id = job["job_id"]

    _upload_card(test_client, job_id, "a.jpg", b"img-a")

    Worker(
        queue=queue,
        processor=DocumentProcessor(
            engine=engine,
            object_reader=FakeObjectReader(),
            inference_client=FakeInferenceClient(),
        ),
    ).process_one()

    body = test_client.get(f"/jobs/{job_id}").json()

    assert body["processed_documents"] == 1
    assert body["total_documents"] == 3
    assert body["progress_percent"] == 33.3
    assert body["status"] == "processing"
    assert body["completed_at"] is None
