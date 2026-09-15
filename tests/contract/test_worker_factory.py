from unittest.mock import Mock

from apps.worker.application import WorkerApplication
from apps.worker.factory import create_worker_application
from apps.worker.processor import DocumentProcessor
from apps.worker.worker import Worker
from packages.common.settings import Settings


def test_create_worker_application_builds_processor():
    settings = Settings(
        _env_file=None,
        database_url=(
            "postgresql+psycopg://user:password@localhost:5432/testdb"
        ),
        inference_base_url="https://example.com/v1",
        inference_model="qwen/test",
        inference_api_key="test-key",
        inference_timeout_seconds=30,
    )

    queue = Mock()

    application = create_worker_application(
        settings=settings,
        queue=queue,
    )

    assert isinstance(application, WorkerApplication)
    assert isinstance(application.worker, Worker)
    assert isinstance(application.worker._processor, DocumentProcessor)
    assert application.worker._queue is queue

    application.close()


def test_create_worker_application_uses_configured_inference_client(
    monkeypatch,
):
    settings = Settings(
        _env_file=None,
        database_url=(
            "postgresql+psycopg://user:password@localhost:5432/testdb"
        ),
        inference_base_url="https://example.com/v1",
        inference_model="qwen/test",
        inference_api_key="test-key",
        inference_timeout_seconds=30,
    )

    fake_client = Mock()
    fake_engine = Mock()

    monkeypatch.setattr(
        "apps.worker.factory.create_inference_client",
        lambda settings: fake_client,
    )

    monkeypatch.setattr(
        "apps.worker.factory.create_db_engine",
        lambda database_url: fake_engine,
    )

    application = create_worker_application(
        settings=settings,
        queue=Mock(),
    )

    assert application.worker._processor._inference_client is fake_client

    application.close()

    fake_client.close.assert_called_once()
    fake_engine.dispose.assert_called_once()