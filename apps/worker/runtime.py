import logging
import time

from apps.worker.worker import Worker

logger = logging.getLogger("business_card_ai.worker")


class WorkerRuntime:
    """Long-running process responsible for consuming worker messages."""

    def __init__(
        self,
        *,
        worker: Worker,
        idle_sleep_seconds: float = 0.5,
    ) -> None:
        if idle_sleep_seconds < 0:
            raise ValueError("idle_sleep_seconds must be non-negative")

        self._worker = worker
        self._idle_sleep_seconds = idle_sleep_seconds
        self._stop_requested = False

    def stop(self) -> None:
        """Request graceful shutdown."""
        self._stop_requested = True

    def run_once(self) -> int:
        """Process queued messages until the queue is empty or stop is requested."""
        processed = 0

        while not self._stop_requested:
            handled = self._worker.process_one()

            if not handled:
                break

            processed += 1

        return processed

    def run_forever(self) -> None:
        """Continuously consume messages until shutdown is requested."""
        while not self._stop_requested:
            try:
                processed = self.run_once()
            except Exception as exc:
                logger.error("Error encountered in worker loop: %s", exc)
                processed = 0

            if processed == 0 and not self._stop_requested:
                time.sleep(self._idle_sleep_seconds)