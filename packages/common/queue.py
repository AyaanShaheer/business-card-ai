import json
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Any

from packages.common.settings import Settings


@dataclass(frozen=True)
class DocumentMessage:
    job_id: str
    document_id: str


class InMemoryQueue:
    """
    Local development queue.

    The interface intentionally mirrors what the worker needs from
    a durable queue implementation such as AWS SQS or Redis.
    """

    def __init__(self) -> None:
        self._queue: Queue[DocumentMessage] = Queue()

    def send(self, message: DocumentMessage) -> None:
        self._queue.put(message)

    def receive(self) -> DocumentMessage | None:
        try:
            return self._queue.get_nowait()
        except Empty:
            return None

    def task_done(self) -> None:
        self._queue.task_done()


class RedisQueue:
    """
    Redis-backed queue for production asynchronous processing.
    """

    def __init__(
        self,
        redis_url: str,
        queue_name: str = "document_processing_queue",
        client: Any = None,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            import redis

            self._client = redis.from_url(redis_url, decode_responses=True)
        self._queue_name = queue_name

    def send(self, message: DocumentMessage) -> None:
        payload = json.dumps(
            {
                "job_id": str(message.job_id),
                "document_id": str(message.document_id),
            }
        )
        self._client.rpush(self._queue_name, payload)

    def receive(self) -> DocumentMessage | None:
        item = self._client.lpop(self._queue_name)
        if item is None:
            return None
        data = json.loads(item)
        return DocumentMessage(
            job_id=str(data["job_id"]),
            document_id=str(data["document_id"]),
        )

    def task_done(self) -> None:
        pass


def create_queue(settings: Settings | None = None):
    """
    Factory creating a RedisQueue if settings.redis_url is configured,
    otherwise falling back to InMemoryQueue (for tests and local dev).
    """
    try:
        settings = settings or Settings()
        if settings.redis_url:
            return RedisQueue(redis_url=str(settings.redis_url))
    except Exception:
        pass
    return InMemoryQueue()