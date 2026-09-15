from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from packages.common.models import (
    DocumentModel,
    ExtractionModel,
    LeadModel,
)
from packages.schemas import Lead


class DocumentProcessor:
    """
    Coordinates object retrieval, model inference, validation,
    and persistence.
    """

    def __init__(
        self,
        *,
        engine: Engine,
        object_reader,
        inference_client,
    ) -> None:
        self._engine = engine
        self._object_reader = object_reader
        self._inference_client = inference_client

    def process(
        self,
        *,
        job_id: UUID,
        document_id: UUID,
    ) -> None:
        started_at = perf_counter()

        with Session(self._engine) as session:
            document = session.get(
                DocumentModel,
                document_id,
            )

            if document is None or document.job_id != job_id:
                raise ValueError("document not found")

            document.status = "processing"
            session.commit()

            try:
                image_bytes = self._object_reader.read(
                    source_uri=document.source_uri,
                )

                raw_output = self._inference_client.extract(
                    image_bytes=image_bytes,
                    mime_type=document.mime_type,
                )

                lead = Lead.model_validate(raw_output)

                latency_ms = int(
                    (perf_counter() - started_at) * 1000
                )

                attempt_number = (
                    document.attempt_count + 1
                )

                extraction = ExtractionModel(
                    document_id=document.id,
                    attempt_number=attempt_number,
                    model_name=getattr(
                        self._inference_client,
                        "model_name",
                        "unknown",
                    ),
                    model_version=getattr(
                        self._inference_client,
                        "model_version",
                        "unknown",
                    ),
                    status="extracted",
                    raw_output=raw_output,
                    validation_status=True,
                    review_status="low",
                    processing_latency_ms=latency_ms,
                    created_at=datetime.now(UTC),
                )

                session.add(extraction)
                session.flush()

                lead_model = LeadModel(
                    extraction_id=extraction.id,
                    document_id=document.id,
                    first_name=lead.first_name,
                    last_name=lead.last_name,
                    job_title=lead.job_title,
                    company=lead.company,
                    location=lead.location,
                    phone_number=lead.phone_number,
                    email_address=lead.email_address,
                )

                session.add(lead_model)

                document.status = "extracted"
                document.attempt_count = attempt_number

                session.commit()

            except (
                ValidationError,
                ValueError,
                FileNotFoundError,
                RuntimeError,
            ):
                session.rollback()

                document = session.get(DocumentModel, document_id)

                if document is not None:
                    document.status = "failed"
                    document.attempt_count += 1
                    session.commit()

                raise