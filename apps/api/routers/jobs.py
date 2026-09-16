from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from apps.api.schemas import (
    CreateJobRequest,
    JobResponse,
    JobStatusResponse,
    LeadListResponse,
    LeadResponse,
)
from packages.common.repositories import JobRepository, LeadRepository
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


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
)
def get_job(
    job_id: UUID,
    session: Session = Depends(get_db_session),
) -> JobStatusResponse:
    repository = JobRepository(session)

    service = JobService(
        session=session,
        repository=repository,
    )

    job = service.get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="job not found",
        )

    progress_percent = 0.0
    if job.total_documents > 0:
        progress_percent = min(
            (job.processed_documents / job.total_documents) * 100,
            100.0,
        )

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        total_documents=job.total_documents,
        processed_documents=job.processed_documents,
        successful_documents=job.successful_documents,
        failed_documents=job.failed_documents,
        review_documents=job.review_documents,
        progress_percent=round(progress_percent, 1),
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.get(
    "/{job_id}/leads",
    response_model=LeadListResponse,
)
def get_job_leads(
    job_id: UUID,
    session: Session = Depends(get_db_session),
) -> LeadListResponse:
    job_repo = JobRepository(session)

    job = job_repo.get_by_id(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="job not found",
        )

    lead_repo = LeadRepository(session)

    leads = lead_repo.get_by_job_id(job_id)

    return LeadListResponse(
        job_id=job_id,
        total=len(leads),
        items=[
            LeadResponse(
                lead_id=lead.id,
                document_id=lead.document_id,
                first_name=lead.first_name,
                last_name=lead.last_name,
                job_title=lead.job_title,
                company=lead.company,
                location=lead.location,
                phone_number=lead.phone_number,
                email_address=lead.email_address,
            )
            for lead in leads
        ],
    )