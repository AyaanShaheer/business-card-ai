from dataclasses import dataclass
from queue import Empty, Queue


@dataclass(frozen=True)
class DocumentMessage:
    job_id: str
    document_id: str


class InMemoryQueue:
    """
    Local development queue.

    The interface intentionally mirrors what the worker needs from
    a durable queue implementation such as AWS SQS.
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