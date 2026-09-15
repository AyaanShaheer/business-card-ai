from io import BytesIO

from fastapi.testclient import TestClient

from apps.api.main import app


client = TestClient(app)


def create_job(total_documents: int = 1) -> str:
    response = client.post(
        "/jobs",
        json={"total_documents": total_documents},
    )

    assert response.status_code == 201

    return response.json()["job_id"]


def test_upload_document_returns_created_document():
    job_id = create_job()

    response = client.post(
        f"/jobs/{job_id}/documents",
        files={
            "file": (
                "card.jpg",
                BytesIO(b"fake-image-data"),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert "document_id" in body
    assert body["job_id"] == job_id
    assert body["filename"] == "card.jpg"
    assert body["mime_type"] == "image/jpeg"
    assert body["size_bytes"] == len(b"fake-image-data")
    assert len(body["content_hash"]) == 64
    assert body["status"] == "uploaded"


def test_upload_rejects_unsupported_mime_type():
    job_id = create_job()

    response = client.post(
        f"/jobs/{job_id}/documents",
        files={
            "file": (
                "card.pdf",
                BytesIO(b"not-an-image"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 422


def test_upload_rejects_unknown_job():
    response = client.post(
        "/jobs/00000000-0000-0000-0000-000000000000/documents",
        files={
            "file": (
                "card.jpg",
                BytesIO(b"fake-image-data"),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 404


def test_duplicate_upload_is_idempotent():
    job_id = create_job(total_documents=2)

    content = b"same-image-content"

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

    assert (
        first.json()["document_id"]
        == second.json()["document_id"]
    )

def test_upload_rejects_oversized_file():
    job_id = create_job()

    content = b"x" * (10 * 1024 * 1024 + 1)

    response = client.post(
        f"/jobs/{job_id}/documents",
        files={
            "file": (
                "huge.jpg",
                BytesIO(content),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 422