"""Tests for GET /jobs/{job_id}/leads and multi-document processing."""

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

    def __init__(self, responses: list[dict] | None = None) -> None:
        self._responses = responses or []
        self._call_count = 0

    def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
    ) -> dict:
        if self._responses:
            result = self._responses[
                self._call_count % len(self._responses)
            ]
            self._call_count += 1
            if isinstance(result, Exception):
                raise result
            return result

        self._call_count += 1
        return {
            "first_name": f"Person{self._call_count}",
            "last_name": "Test",
            "job_title": "Engineer",
            "company": "Corp",
            "location": "NYC",
            "phone_number": "+1234567890",
            "email_address": f"p{self._call_count}@test.com",
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


def _upload(client, job_id, name, content):
    return client.post(
        f"/jobs/{job_id}/documents",
        files={"file": (name, BytesIO(content), "image/jpeg")},
    )


def _drain_queue(queue, engine, inference_client):
    """Process all messages in the queue."""
    worker = Worker(
        queue=queue,
        processor=DocumentProcessor(
            engine=engine,
            object_reader=FakeObjectReader(),
            inference_client=inference_client,
        ),
    )
    processed = 0
    while worker.process_one():
        processed += 1
    return processed


# ── Leads API Tests ──


def test_leads_empty_for_new_job(isolated_client):
    client, _, _ = isolated_client

    job = client.post(
        "/jobs", json={"total_documents": 1}
    ).json()

    response = client.get(f"/jobs/{job['job_id']}/leads")

    assert response.status_code == 200

    body = response.json()
    assert body["job_id"] == job["job_id"]
    assert body["total"] == 0
    assert body["items"] == []


def test_leads_returns_404_for_unknown_job(isolated_client):
    client, _, _ = isolated_client

    response = client.get(
        "/jobs/00000000-0000-0000-0000-000000000000/leads"
    )

    assert response.status_code == 404


def test_leads_returns_one_lead_after_processing(
    isolated_client,
):
    client, queue, engine = isolated_client

    job = client.post(
        "/jobs", json={"total_documents": 1}
    ).json()
    job_id = job["job_id"]

    _upload(client, job_id, "card.jpg", b"image-data")

    _drain_queue(queue, engine, FakeInferenceClient())

    response = client.get(f"/jobs/{job_id}/leads")

    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 1

    lead = body["items"][0]
    assert lead["first_name"] == "Person1"
    assert lead["last_name"] == "Test"
    assert lead["email_address"] == "p1@test.com"
    assert lead["document_id"] is not None
    assert lead["lead_id"] is not None


def test_leads_returns_multiple_leads(isolated_client):
    client, queue, engine = isolated_client

    job = client.post(
        "/jobs", json={"total_documents": 3}
    ).json()
    job_id = job["job_id"]

    _upload(client, job_id, "a.jpg", b"img-a")
    _upload(client, job_id, "b.jpg", b"img-b")
    _upload(client, job_id, "c.jpg", b"img-c")

    processed = _drain_queue(
        queue, engine, FakeInferenceClient()
    )
    assert processed == 3

    response = client.get(f"/jobs/{job_id}/leads")
    body = response.json()

    assert body["total"] == 3
    assert len(body["items"]) == 3

    names = sorted(i["first_name"] for i in body["items"])
    assert names == ["Person1", "Person2", "Person3"]


# ── Multi-Document Processing Tests ──


def test_multi_doc_all_succeed(isolated_client):
    client, queue, engine = isolated_client

    job = client.post(
        "/jobs", json={"total_documents": 3}
    ).json()
    job_id = job["job_id"]

    for i in range(3):
        _upload(
            client, job_id, f"card{i}.jpg", f"img-{i}".encode()
        )

    _drain_queue(queue, engine, FakeInferenceClient())

    status = client.get(f"/jobs/{job_id}").json()

    assert status["status"] == "completed"
    assert status["processed_documents"] == 3
    assert status["successful_documents"] == 3
    assert status["failed_documents"] == 0
    assert status["progress_percent"] == 100.0


def test_multi_doc_all_fail(isolated_client):
    client, queue, engine = isolated_client

    job = client.post(
        "/jobs", json={"total_documents": 2}
    ).json()
    job_id = job["job_id"]

    _upload(client, job_id, "a.jpg", b"img-a")
    _upload(client, job_id, "b.jpg", b"img-b")

    # Process with failing inference — catch exceptions.
    worker = Worker(
        queue=queue,
        processor=DocumentProcessor(
            engine=engine,
            object_reader=FakeObjectReader(),
            inference_client=FailingInferenceClient(),
        ),
    )

    for _ in range(2):
        with pytest.raises(RuntimeError):
            worker.process_one()

    status = client.get(f"/jobs/{job_id}").json()

    assert status["status"] == "completed_with_errors"
    assert status["processed_documents"] == 2
    assert status["failed_documents"] == 2
    assert status["successful_documents"] == 0

    # No leads from failed processing.
    leads = client.get(f"/jobs/{job_id}/leads").json()
    assert leads["total"] == 0


def test_multi_doc_mixed_success_failure(isolated_client):
    """One failure must not prevent other documents."""
    client, queue, engine = isolated_client

    job = client.post(
        "/jobs", json={"total_documents": 3}
    ).json()
    job_id = job["job_id"]

    _upload(client, job_id, "a.jpg", b"img-a")
    _upload(client, job_id, "b.jpg", b"img-b")
    _upload(client, job_id, "c.jpg", b"img-c")

    # First call succeeds, second fails, third succeeds.
    responses = [
        {
            "first_name": "Alice",
            "last_name": "A",
            "job_title": "CEO",
            "company": "Co",
            "location": "LA",
            "phone_number": "+1111111111",
            "email_address": "alice@co.com",
        },
        RuntimeError("inference failed"),
        {
            "first_name": "Charlie",
            "last_name": "C",
            "job_title": "CTO",
            "company": "Co",
            "location": "SF",
            "phone_number": "+3333333333",
            "email_address": "charlie@co.com",
        },
    ]

    inference = FakeInferenceClient(responses)

    worker = Worker(
        queue=queue,
        processor=DocumentProcessor(
            engine=engine,
            object_reader=FakeObjectReader(),
            inference_client=inference,
        ),
    )

    # Process all 3 — one will raise.
    for _ in range(3):
        try:
            worker.process_one()
        except RuntimeError:
            pass

    status = client.get(f"/jobs/{job_id}").json()

    assert status["status"] == "completed_with_errors"
    assert status["processed_documents"] == 3
    assert status["successful_documents"] == 2
    assert status["failed_documents"] == 1

    leads = client.get(f"/jobs/{job_id}/leads").json()
    assert leads["total"] == 2

    names = sorted(i["first_name"] for i in leads["items"])
    assert names == ["Alice", "Charlie"]
