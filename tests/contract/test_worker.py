from uuid import uuid4

import pytest

from packages.common.queue import (
    DocumentMessage,
    InMemoryQueue,
)
from apps.worker.worker import Worker


class FakeProcessor:
    def __init__(self) -> None:
        self.processed = []

    def process(
        self,
        *,
        job_id,
        document_id,
    ) -> None:
        self.processed.append(
            {
                "job_id": job_id,
                "document_id": document_id,
            }
        )


def test_worker_processes_one_message():
    queue = InMemoryQueue()
    processor = FakeProcessor()

    job_id = uuid4()
    document_id = uuid4()

    message = DocumentMessage(
        job_id=str(job_id),
        document_id=str(document_id),
    )

    queue.send(message)

    worker = Worker(
        queue=queue,
        processor=processor,
    )

    assert worker.process_one() is True

    assert processor.processed == [
        {
            "job_id": job_id,
            "document_id": document_id,
        }
    ]


def test_worker_returns_false_when_queue_is_empty():
    queue = InMemoryQueue()
    processor = FakeProcessor()

    worker = Worker(
        queue=queue,
        processor=processor,
    )

    assert worker.process_one() is False
    assert processor.processed == []


def test_worker_rejects_malformed_uuid_message():
    queue = InMemoryQueue()
    processor = FakeProcessor()

    message = DocumentMessage(
        job_id="not-a-uuid",
        document_id="also-not-a-uuid",
    )

    queue.send(message)

    worker = Worker(
        queue=queue,
        processor=processor,
    )

    with pytest.raises(ValueError):
        worker.process_one()

    assert processor.processed == []