from fastapi.testclient import TestClient

from apps.api.main import app


client = TestClient(app)


def test_create_job_returns_created_job():
    response = client.post(
        "/jobs",
        json={"total_documents": 3},
    )

    assert response.status_code == 201

    body = response.json()

    assert "job_id" in body
    assert body["status"] == "created"
    assert body["total_documents"] == 3

def test_create_job_rejects_zero_documents():
    response = client.post(
        "/jobs",
        json={"total_documents": 0},
    )

    assert response.status_code == 422


def test_create_job_rejects_negative_documents():
    response = client.post(
        "/jobs",
        json={"total_documents": -1},
    )

    assert response.status_code == 422


def test_create_job_rejects_more_than_maximum():
    response = client.post(
        "/jobs",
        json={"total_documents": 51},
    )

    assert response.status_code == 422