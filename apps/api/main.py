from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from apps.api.routers.documents import router as documents_router
from apps.api.routers.jobs import router as jobs_router


app = FastAPI(
    title="Business Card AI",
    version="0.1.0",
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


app.include_router(jobs_router)
app.include_router(documents_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}