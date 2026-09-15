from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.common.db import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class JobModel(Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    total_documents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    processed_documents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    successful_documents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    failed_documents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    review_documents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    documents: Mapped[list["DocumentModel"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )

    exports: Mapped[list["ExportModel"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "total_documents >= 0",
            name="ck_jobs_total_documents_non_negative",
        ),
        CheckConstraint(
            "processed_documents >= 0",
            name="ck_jobs_processed_documents_non_negative",
        ),
        CheckConstraint(
            "successful_documents >= 0",
            name="ck_jobs_successful_documents_non_negative",
        ),
        CheckConstraint(
            "failed_documents >= 0",
            name="ck_jobs_failed_documents_non_negative",
        ),
        CheckConstraint(
            "review_documents >= 0",
            name="ck_jobs_review_documents_non_negative",
        ),
    )


class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    job_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_uri: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    mime_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    job: Mapped["JobModel"] = relationship(
        back_populates="documents",
    )

    extractions: Mapped[list["ExtractionModel"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="ExtractionModel.attempt_number",
    )

    __table_args__ = (
        CheckConstraint(
            "size_bytes >= 0",
            name="ck_documents_size_bytes_non_negative",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_documents_attempt_count_non_negative",
        ),
        Index(
            "uq_documents_job_content_hash",
            "job_id",
            "content_hash",
            unique=True,
        ),
    )


class ExtractionModel(Base):
    __tablename__ = "extractions"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    document_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    model_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    model_version: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    raw_output: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    validation_status: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    review_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="required",
    )

    processing_latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    document: Mapped["DocumentModel"] = relationship(
        back_populates="extractions",
    )

    lead: Mapped["LeadModel | None"] = relationship(
        back_populates="extraction",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "attempt_number >= 1",
            name="ck_extractions_attempt_number_positive",
        ),
        CheckConstraint(
            "processing_latency_ms IS NULL OR processing_latency_ms >= 0",
            name="ck_extractions_latency_non_negative",
        ),
    )


class LeadModel(Base):
    __tablename__ = "leads"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    extraction_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("extractions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    document_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    first_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    last_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    job_title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    company: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    phone_number: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    email_address: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    extraction: Mapped["ExtractionModel"] = relationship(
        back_populates="lead",
    )


class ExportModel(Base):
    __tablename__ = "exports"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    job_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        index=True,
    )

    format: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    output_uri: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    job: Mapped["JobModel"] = relationship(
        back_populates="exports",
    )