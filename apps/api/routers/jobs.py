from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from apps.api.schemas import CreateJobRequest, JobResponse
from packages.common.repositories import JobRepository
from packages.common.services import JobService
from packages.common.settings import Settings


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


settings = Settings()


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_job(
    request: CreateJobRequest,
    session: Session = Depends(get_db_session),
) -> JobResponse:
    repository = JobRepository(session)

    service = JobService(
        session=session,
        repository=repository,
        max_files_per_job=settings.max_files_per_job,
    )

    job = service.create_job(
        total_documents=request.total_documents,
    )

    return JobResponse(
        job_id=job.id,
        status=job.status,
        total_documents=job.total_documents,
    )