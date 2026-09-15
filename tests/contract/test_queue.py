import pytest

from packages.common.queue import (
    DocumentMessage,
    InMemoryQueue,
)


def test_document_message_requires_required_fields():
    message = DocumentMessage(
        job_id="job-1",
        document_id="document-1",
    )

    assert message.job_id == "job-1"
    assert message.document_id == "document-1"


def test_queue_send_and_receive():
    queue = InMemoryQueue()

    message = DocumentMessage(
        job_id="job-1",
        document_id="document-1",
    )

    queue.send(message)

    received = queue.receive()

    assert received == message


def test_empty_queue_returns_none():
    queue = InMemoryQueue()

    assert queue.receive() is None


def test_queue_preserves_fifo_order():
    queue = InMemoryQueue()

    first = DocumentMessage(
        job_id="job-1",
        document_id="document-1",
    )

    second = DocumentMessage(
        job_id="job-1",
        document_id="document-2",
    )

    queue.send(first)
    queue.send(second)

    assert queue.receive() == first
    assert queue.receive() == second