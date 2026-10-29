"""All persistent entities. Adapted single-module layout (the brief allows adapting
the structure where implementation simplicity justifies it)."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Sequence,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import Base


def new_id() -> str:
    return uuid.uuid4().hex


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    subscription_plan: Mapped[str] = mapped_column(String(50), default="trial", nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="organization")
    sites: Mapped[list["Site"]] = relationship(back_populates="organization")


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_users_org_email"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")  # admin|reviewer|viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_active: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization: Mapped[Organization] = relationship(back_populates="users")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Site(Base, TimestampMixin):
    __tablename__ = "sites"
    __table_args__ = (UniqueConstraint("organization_id", "domain", name="uq_sites_org_domain"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(10), default="US", nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    scan_interval_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    pages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_scan_status: Mapped[str | None] = mapped_column(String(20))

    organization: Mapped[Organization] = relationship(back_populates="sites")
    scans: Mapped[list["Scan"]] = relationship(back_populates="site", cascade="all, delete-orphan")


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("site_id", "url", name="uq_pages_site_url"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_snapshot_id: Mapped[str | None] = mapped_column(String(32))


class Snapshot(Base):
    """Versioned page snapshot: content, extracted text, hash, fetch metadata."""

    __tablename__ = "snapshots"
    __table_args__ = (
        Index("ix_snapshots_page_hash", "page_id", "content_hash"),
        Index("uq_snapshots_page_version", "page_id", "version", unique=True),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    scan_id: Mapped[str | None] = mapped_column(String(32), index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    html_path: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    changed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    extraction_error: Mapped[str | None] = mapped_column(Text)


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    # queued | running | completed | failed | cancelled
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pages_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pages_done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    changed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claims_extracted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_s: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)  # manual|scheduled|recheck
    task_id: Mapped[str | None] = mapped_column(String(64))
    max_pages: Mapped[int] = mapped_column(Integer, default=25, nullable=False)

    site: Mapped[Site] = relationship(back_populates="scans")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    context_label: Mapped[str | None] = mapped_column(Text)
    offsets_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    offsets_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    category: Mapped[str | None] = mapped_column(String(60))
    medication: Mapped[str | None] = mapped_column(String(200))
    population: Mapped[str | None] = mapped_column(String(200))
    formulation: Mapped[str | None] = mapped_column(String(200))
    dosage: Mapped[str | None] = mapped_column(String(200))
    extraction_model: Mapped[str] = mapped_column(String(120), nullable=False)
    extraction_confidence: Mapped[float | None] = mapped_column(Float)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    snapshot: Mapped[Snapshot] = relationship()


class ReferenceDocument(Base):
    __tablename__ = "reference_documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "authority", "title", "version", name="uq_refdoc_identity"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    authority: Mapped[str] = mapped_column(String(200), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(120), nullable=False, default="guidance")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1")
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    publication_date: Mapped[date | None] = mapped_column(Date)
    effective_date: Mapped[date | None] = mapped_column(Date)
    jurisdiction: Mapped[str | None] = mapped_column(String(10))
    identifiers: Mapped[dict | None] = mapped_column(JSONB)
    is_fictional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chunks: Mapped[list["ReferenceChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


# This dimension matches the initial pgvector schema migration. Changing it
# requires a new migration and rebuilding every stored embedding.
EMB_DIM = 384


class ReferenceChunk(Base):
    __tablename__ = "reference_chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("reference_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section: Mapped[str | None] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMB_DIM))

    document: Mapped[ReferenceDocument] = relationship(back_populates="chunks")


# Incident public numbers: INC-<seq>
incident_number_seq = Sequence("incident_number_seq", metadata=Base.metadata)


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint("organization_id", "dedupe_key", name="uq_incidents_dedupe"),
        Index("ix_incidents_org_status_priority", "organization_id", "status", "priority"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    public_id: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)
    number: Mapped[int] = mapped_column(Integer, incident_number_seq, server_default=incident_number_seq.next_value())
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("snapshots.id", ondelete="SET NULL"))
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    agent_run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    scan_id: Mapped[str | None] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str] = mapped_column(String(40), nullable=False)
    # SUPPORTED | POTENTIAL_CONTRADICTION | POSSIBLY_OUTDATED | INCOMPLETE_INFORMATION | INSUFFICIENT_EVIDENCE
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="low")  # critical|high|medium|low
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    # open | in_review | awaiting_correction | resolved | dismissed
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    harm: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    exposure: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    evidence_strength: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    uncertainty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    recheck_of: Mapped[str | None] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    claim: Mapped[Claim] = relationship()
    snapshot: Mapped[Snapshot | None] = relationship()
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan", order_by="Evidence.rank"
    )
    trace: Mapped[list["IncidentTrace"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan", order_by="IncidentTrace.at"
    )
    reviews: Mapped[list["Review"]] = relationship(back_populates="incident")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("reference_chunks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("reference_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    section: Mapped[str | None] = mapped_column(String(300))
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    offsets_start: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    offsets_end: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    similarity: Mapped[float | None] = mapped_column(Float)
    retrieval_method: Mapped[str] = mapped_column(String(30), default="hybrid", nullable=False)

    incident: Mapped[Incident] = relationship(back_populates="evidence")
    document: Mapped[ReferenceDocument] = relationship()


class IncidentTrace(Base):
    __tablename__ = "incident_trace"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    step: Mapped[str] = mapped_column(String(80), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    incident: Mapped[Incident] = relationship(back_populates="trace")


class Review(Base):
    """Immutable audit event for a reviewer decision."""

    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # confirm|dismiss|needs_info
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    previous_status: Mapped[str] = mapped_column(String(30), nullable=False)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    incident: Mapped[Incident] = relationship(back_populates="reviews")
    reviewer: Mapped[User] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    object: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    incident_id: Mapped[str | None] = mapped_column(String(32))
    site: Mapped[str | None] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)  # finding|resolved|scan_failed
    tone: Mapped[str | None] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    href: Mapped[str | None] = mapped_column(String(300))
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class OrgSetting(Base):
    __tablename__ = "org_settings"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    notifications: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    organization_profile: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class AgentRun(Base):
    """Persisted investigation run so interrupted jobs can be diagnosed or resumed."""

    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # run_<hex>
    organization_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scan_id: Mapped[str | None] = mapped_column(String(32), index=True)
    current_step: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    state: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsageMeter(Base):
    """Subscription usage metering (plan limits without a payment gateway)."""

    __tablename__ = "usage_meters"
    __table_args__ = (UniqueConstraint("organization_id", "period", name="uq_usage_org_period"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    scans_run: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pages_scanned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claims_extracted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


# Convenience re-export for alembic / tests
__all__ = [name for name in dir() if not name.startswith("_")]
