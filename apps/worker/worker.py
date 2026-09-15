from uuid import UUID

from packages.common.queue import DocumentMessage


class DocumentProcessorProtocol:
    def process(
        self,
        *,
        job_id: UUID,
        document_id: UUID,
    ) -> None:
        ...


class Worker:
    """Consumes document-processing messages."""

    def __init__(
        self,
        *,
        queue,
        processor: DocumentProcessorProtocol,
    ) -> None:
        self._queue = queue
        self._processor = processor

    def process_one(self) -> bool:
        message: DocumentMessage | None = self._queue.receive()

        if message is None:
            return False

        try:
            self._processor.process(
                job_id=UUID(message.job_id),
                document_id=UUID(message.document_id),
            )
        finally:
            self._queue.task_done()

        return True