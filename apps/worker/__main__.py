import logging
import signal
from types import FrameType

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.worker.factory import create_worker_application
from apps.worker.runtime import WorkerRuntime
from packages.common.models import DocumentModel
from packages.common.queue import DocumentMessage, create_queue
from packages.common.settings import Settings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)


def recover_unprocessed_documents(engine, queue) -> None:
    """Re-enqueue any documents uploaded but not yet finished (e.g. after worker restart)."""
    try:
        with Session(engine) as session:
            stmt = (
                select(DocumentModel)
                .where(DocumentModel.status.in_(["uploaded", "processing"]))
                .order_by(DocumentModel.created_at.asc())
            )
            pending_docs = session.scalars(stmt).all()
            for doc in pending_docs:
                queue.send(
                    DocumentMessage(
                        job_id=str(doc.job_id),
                        document_id=str(doc.id),
                    )
                )
            if pending_docs:
                logger.info(
                    "Recovered %d unprocessed document(s) into queue for processing",
                    len(pending_docs),
                )
    except Exception as exc:
        logger.warning("Could not recover pending documents: %s", exc)


def main() -> None:
    settings = Settings()

    queue = create_queue(settings)

    application = create_worker_application(
        settings=settings,
        queue=queue,
    )

    recover_unprocessed_documents(application._engine, queue)

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