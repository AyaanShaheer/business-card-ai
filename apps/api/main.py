import logging
import os
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.routers.documents import queue as documents_queue
from apps.api.routers.documents import router as documents_router
from apps.api.routers.exports import router as exports_router
from apps.api.routers.jobs import router as jobs_router
from apps.worker.factory import create_worker_application
from apps.worker.runtime import WorkerRuntime
from packages.common.models import DocumentModel
from packages.common.queue import DocumentMessage
from packages.common.settings import Settings

logger = logging.getLogger("business_card_ai")

# Resolve the frontend build directory relative to apps/ directory.
_FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


def _recover_unprocessed_documents(engine, queue) -> None:
    """Find any documents that were uploaded but not yet processed (e.g. before server restart)
    and push them to the worker queue."""
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    is_testing = (
        "pytest" in sys.modules
        or os.getenv("TESTING", "").lower() in ("true", "1")
    )
    runtime = None
    worker_app = None

    if not is_testing:
        settings = Settings()
        worker_app = create_worker_application(
            settings=settings,
            queue=documents_queue,
        )
        runtime = WorkerRuntime(
            worker=worker_app.worker,
            idle_sleep_seconds=0.5,
        )

        _recover_unprocessed_documents(worker_app._engine, documents_queue)

        worker_thread = threading.Thread(
            target=runtime.run_forever,
            daemon=True,
            name="BusinessCardWorkerThread",
        )
        worker_thread.start()
        logger.info("Background document processing worker started successfully")

    yield

    if runtime is not None:
        runtime.stop()
    if worker_app is not None:
        worker_app.close()
        logger.info("Background document processing worker stopped")


app = FastAPI(
    title="Business Card AI",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def value_error_handler(
    request: Request,
    exc: ValueError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": str(exc),
        },
    )


# ── API routes ──────────────────────────────────────────────────
# Mount all API routers under /api so the frontend can call
# /api/jobs, /api/jobs/{id}/leads, etc. without a proxy.
# The same routers are also kept at their original paths (e.g. /jobs)
# so that existing tests and local dev (Vite proxy) continue to work.

app.include_router(jobs_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(exports_router, prefix="/api")

# Keep original un-prefixed routes for backward compat / tests
app.include_router(jobs_router)
app.include_router(documents_router)
app.include_router(exports_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Static frontend (production) ────────────────────────────────
# In production the React build is served from apps/frontend/dist/.
# This block is skipped if the dist directory doesn't exist (e.g. in
# tests or local dev where Vite handles the frontend).

if _FRONTEND_DIST.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
        name="static-assets",
    )

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        """SPA fallback — serve index.html for any path not matched by API routes."""
        file_path = _FRONTEND_DIST / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_FRONTEND_DIST / "index.html"))