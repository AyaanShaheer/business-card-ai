"""Tests for POST /jobs/{job_id}/documents/bulk endpoint."""

from io import BytesIO

from fastapi.testclient import TestClient

from apps.api.main import app


client = TestClient(app)


def create_job(total_documents: int = 5) -> str:
    response = client.post(
        "/jobs",
        json={"total_documents": total_documents},
    )
    assert response.status_code == 201
    return response.json()["job_id"]


def make_file(
    name: str = "card.jpg",
    content: bytes = b"fake-image",
    mime: str = "image/jpeg",
):
    return (name, BytesIO(content), mime)


def test_bulk_upload_single_file():
    job_id = create_job()

    response = client.post(
        f"/jobs/{job_id}/documents/bulk",
        files=[("files", make_file())],
    )

    assert response.status_code == 200

    body = response.json()

    assert body["job_id"] == job_id
    assert body["accepted"] == 1
    assert body["rejected"] == 0
    assert len(body["results"]) == 1
    assert body["results"][0]["success"] is True
    assert body["results"][0]["document_id"] is not None


def test_bulk_upload_multiple_files():
    job_id = create_job()

    response = client.post(
        f"/jobs/{job_id}/documents/bulk",
        files=[
            ("files", make_file("a.jpg", b"img-a")),
            ("files", make_file("b.jpg", b"img-b")),
            ("files", make_file("c.png", b"img-c", "image/png")),
        ],
    )

    assert response.status_code == 200

    body = response.json()

    assert body["accepted"] == 3
    assert body["rejected"] == 0
    assert len(body["results"]) == 3


def test_bulk_upload_mixed_valid_invalid():
    job_id = create_job()

    response = client.post(
        f"/jobs/{job_id}/documents/bulk",
        files=[
            ("files", make_file("good.jpg", b"valid-image")),
            ("files", make_file("bad.pdf", b"not-image", "application/pdf")),
            ("files", make_file("also-good.png", b"another", "image/png")),
        ],
    )

    assert response.status_code == 200

    body = response.json()

    assert body["accepted"] == 2
    assert body["rejected"] == 1

    results_by_name = {r["filename"]: r for r in body["results"]}

    assert results_by_name["good.jpg"]["success"] is True
    assert results_by_name["bad.pdf"]["success"] is False
    assert "unsupported mime type" in results_by_name["bad.pdf"]["error"]
    assert results_by_name["also-good.png"]["success"] is True


def test_bulk_upload_duplicate_files():
    job_id = create_job()

    same_content = b"identical-content"

    response = client.post(
        f"/jobs/{job_id}/documents/bulk",
        files=[
            ("files", make_file("a.jpg", same_content)),
            ("files", make_file("b.jpg", same_content)),
        ],
    )

    assert response.status_code == 200

    body = response.json()

    # Both should succeed — second is idempotent.
    assert body["accepted"] == 2
    assert body["rejected"] == 0

    # Both should point to the same document.
    ids = [r["document_id"] for r in body["results"]]
    assert ids[0] == ids[1]


def test_bulk_upload_oversized_file():
    job_id = create_job()

    oversized = b"x" * (10 * 1024 * 1024 + 1)

    response = client.post(
        f"/jobs/{job_id}/documents/bulk",
        files=[
            ("files", make_file("small.jpg", b"ok")),
            ("files", make_file("huge.jpg", oversized)),
        ],
    )

    assert response.status_code == 200

    body = response.json()

    assert body["accepted"] == 1
    assert body["rejected"] == 1


def test_bulk_upload_unsupported_mime():
    job_id = create_job()

    response = client.post(
        f"/jobs/{job_id}/documents/bulk",
        files=[
            ("files", make_file("doc.pdf", b"data", "application/pdf")),
        ],
    )

    assert response.status_code == 200

    body = response.json()

    assert body["accepted"] == 0
    assert body["rejected"] == 1


def test_bulk_upload_missing_job():
    response = client.post(
        "/jobs/00000000-0000-0000-0000-000000000000/documents/bulk",
        files=[("files", make_file())],
    )

    assert response.status_code == 404
