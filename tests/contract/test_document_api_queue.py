from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.routers.documents import queue


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_queue():
    """
    Ensure every test starts with an empty in-memory queue.
    """
    while queue.receive() is not None:
        queue.task_done()

    yield

    while queue.receive() is not None:
        queue.task_done()


def create_job(total_documents: int = 1) -> str:
    response = client.post(
        "/jobs",
        json={"total_documents": total_documents},
    )

    assert response.status_code == 201

    return response.json()["job_id"]


def test_upload_publishes_document_message():
    job_id = create_job()

    response = client.post(
        f"/jobs/{job_id}/documents",
        files={
            "file": (
                "card.jpg",
                BytesIO(b"image-content"),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 201

    document_id = response.json()["document_id"]

    message = queue.receive()

    assert message is not None
    assert message.job_id == job_id
    assert message.document_id == document_id

    queue.task_done()


def test_duplicate_upload_does_not_publish_second_message():
    job_id = create_job()

    content = b"same-image"

    first = client.post(
        f"/jobs/{job_id}/documents",
        files={
            "file": (
                "card.jpg",
                BytesIO(content),
                "image/jpeg",
            )
        },
    )

    second = client.post(
        f"/jobs/{job_id}/documents",
        files={
            "file": (
                "card-copy.jpg",
                BytesIO(content),
                "image/jpeg",
            )
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201

    first_message = queue.receive()
    second_message = queue.receive()

    assert first_message is not None
    assert second_message is None

    queue.task_done()


def test_unknown_job_does_not_publish_message():
    response = client.post(
        "/jobs/00000000-0000-0000-0000-000000000000/documents",
        files={
            "file": (
                "card.jpg",
                BytesIO(b"image-content"),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 404
    assert queue.receive() is None