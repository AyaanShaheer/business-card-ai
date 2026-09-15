import logging
import signal
from types import FrameType

from apps.worker.factory import create_worker_application
from apps.worker.runtime import WorkerRuntime
from packages.common.queue import InMemoryQueue
from packages.common.settings import Settings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> None:
    settings = Settings()

    queue = InMemoryQueue()

    application = create_worker_application(
        settings=settings,
        queue=queue,
    )

    runtime = WorkerRuntime(
        worker=application.worker,
    )

    def handle_shutdown(
        signum: int,
        _frame: FrameType | None,
    ) -> None:
        logger.info(
            "Shutdown signal received: %s",
            signal.Signals(signum).name,
        )
        runtime.stop()

    signal.signal(
        signal.SIGINT,
        handle_shutdown,
    )
    signal.signal(
        signal.SIGTERM,
        handle_shutdown,
    )

    logger.info("Business Card AI worker started")

    try:
        runtime.run_forever()
    finally:
        logger.info("Shutting down worker dependencies")
        application.close()
        logger.info("Business Card AI worker stopped")


if __name__ == "__main__":
    main()