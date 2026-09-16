"""Export router for downloading lead data."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from packages.common.export import generate_leads_xlsx
from packages.common.repositories import JobRepository


router = APIRouter(
    prefix="/jobs/{job_id}/export",
    tags=["export"],
)


@router.get("/xlsx")
def export_leads_xlsx(
    job_id: UUID,
    session: Session = Depends(get_db_session),
) -> Response:
    """Download all leads for a job as an Excel file."""
    job_repo = JobRepository(session)
    job = job_repo.get_by_id(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="job not found",
        )

    xlsx_bytes = generate_leads_xlsx(
        session=session,
        job_id=job_id,
    )

    filename = f"leads_{job_id}.xlsx"

    return Response(
        content=xlsx_bytes,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            ),
        },
    )
