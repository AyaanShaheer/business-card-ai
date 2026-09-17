import pytest

from packages.common.queue import (
    DocumentMessage,
    InMemoryQueue,
    RedisQueue,
    create_queue,
)
from packages.common.settings import Settings


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


class FakeRedisClient:
    def __init__(self):
        self.lists: dict[str, list[str]] = {}

    def rpush(self, key: str, value: str) -> None:
        self.lists.setdefault(key, []).append(value)

    def lpop(self, key: str) -> str | None:
        items = self.lists.get(key, [])
        if items:
            return items.pop(0)
        return None


def test_redis_queue_send_and_receive():
    fake_client = FakeRedisClient()
    queue = RedisQueue(
        redis_url="redis://localhost:6379/0",
        client=fake_client,
    )

    message = DocumentMessage(
        job_id="job-123",
        document_id="doc-456",
    )

    queue.send(message)
    received = queue.receive()

    assert received == message
    assert queue.receive() is None


def test_redis_queue_fifo_order():
    fake_client = FakeRedisClient()
    queue = RedisQueue(
        redis_url="redis://localhost:6379/0",
        client=fake_client,
    )

    msg1 = DocumentMessage(job_id="job-1", document_id="doc-1")
    msg2 = DocumentMessage(job_id="job-2", document_id="doc-2")

    queue.send(msg1)
    queue.send(msg2)

    assert queue.receive() == msg1
    assert queue.receive() == msg2
    assert queue.receive() is None


def test_create_queue_factory_returns_in_memory_by_default():
    queue = create_queue(Settings(redis_url=None))
    assert isinstance(queue, InMemoryQueue)


def test_create_queue_factory_returns_redis_queue_when_url_provided():
    queue = create_queue(Settings(redis_url="redis://localhost:6379/0"))
    assert isinstance(queue, RedisQueue)