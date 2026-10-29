"""Pydantic v2 schemas — exact shapes from frontend/src/api/mock.js (see docs/API_CONTRACT.md)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Verdict = Literal[
    "SUPPORTED",
    "POTENTIAL_CONTRADICTION",
    "POSSIBLY_OUTDATED",
    "INCOMPLETE_INFORMATION",
    "INSUFFICIENT_EVIDENCE",
]
Priority = Literal["critical", "high", "medium", "low"]
Status = Literal["open", "in_review", "awaiting_correction", "resolved", "dismissed"]
Decision = Literal["confirm", "needs_info", "dismiss"]
Role = Literal["admin", "reviewer", "viewer"]


# ---------- auth ----------
EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"


class LoginRequest(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN)
    password: str
    organization_id: str | None = None


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=320)
    organization_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=12, max_length=200)

    @field_validator("name", "organization_name")
    @classmethod
    def trim_non_empty_names(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, password: str) -> str:
        if len(password.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return password


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class MeOut(BaseModel):
    id: str
    name: str
    email: str
    role: Role
    organization_id: str
    is_active: bool = True


# ---------- sites ----------
class SiteOut(BaseModel):
    id: str
    domain: str
    jurisdiction: str
    language: str
    scan_interval_hours: int
    enabled: bool
    pages: int
    last_scan_at: datetime | None
    last_scan_status: str | None

    model_config = {"from_attributes": True}


class SiteCreate(BaseModel):
    domain: str
    jurisdiction: str | None = None
    language: str | None = None
    scan_interval_hours: int | None = None


class SitePatch(BaseModel):
    jurisdiction: str | None = None
    language: str | None = None
    scan_interval_hours: int | None = None
    enabled: bool | None = None


# ---------- scans ----------
class ScanOut(BaseModel):
    id: str
    site_id: str
    status: str
    error: str | None
    started_at: datetime
    pages_total: int
    pages_done: int
    changed: int
    claims_extracted: int
    duration_s: int
    trigger: str

    model_config = {"from_attributes": True}


class ScanCreate(BaseModel):
    site_id: str


# ---------- claims ----------
class ClaimOut(BaseModel):
    id: str
    statement: str
    context: str | None = None
    offsets: list[int]
    snapshot_id: str
    snapshot_fetched_at: datetime | None
    content_hash: str | None
    site: str | None = None
    page_url: str | None = None
    incident_id: str | None = None


# ---------- incidents ----------
class ClaimDetail(BaseModel):
    id: str
    statement: str
    context: str | None
    offsets: list[int]
    snapshot_id: str
    snapshot_fetched_at: datetime | None
    content_hash: str | None


class EvidenceOut(BaseModel):
    id: str
    document_id: str
    authority: str
    doc_type: str
    title: str
    version: str
    effective_date: date | None
    url: str
    section: str | None
    quote: str
    offsets: list[int]


class RiskOut(BaseModel):
    harm: float
    exposure: float
    evidence_strength: float
    uncertainty: float


class DecisionOut(BaseModel):
    decision: str
    rationale: str
    reviewer: str
    at: datetime


class TraceEntry(BaseModel):
    step: str
    detail: str
    at: datetime


class IncidentSummary(BaseModel):
    id: str
    title: str
    priority: str
    verdict: str
    status: str
    site: str
    page_url: str | None
    claim_statement: str
    evidence_authority: str | None
    evidence_date: date | None
    created_at: datetime


class IncidentDetail(BaseModel):
    id: str
    title: str
    priority: str
    verdict: str
    status: str
    site: str
    page_url: str | None
    created_at: datetime
    agent_run_id: str | None
    claim: ClaimDetail
    evidence: list[EvidenceOut]
    rationale: str
    risk: RiskOut
    decision: DecisionOut | None
    trace: list[TraceEntry]


class ReviewRequest(BaseModel):
    decision: Decision
    rationale: str


# ---------- references ----------
class ReferenceChunkOut(BaseModel):
    section: str | None
    text: str


class ReferenceDocOut(BaseModel):
    id: str
    authority: str
    doc_type: str
    title: str
    version: str
    effective_date: date | None
    url: str
    identifiers: dict | None = None
    is_fictional: bool = False
    chunks: list[ReferenceChunkOut] = []


# ---------- admin ----------
class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    last_active: datetime | None


class UserPatch(BaseModel):
    role: Role


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=320)
    password: str = Field(min_length=12, max_length=200)
    role: Role = "viewer"

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, password: str) -> str:
        if len(password.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return password


class NotificationSettings(BaseModel):
    min_priority: Priority = "high"


class OrganizationProfile(BaseModel):
    name: str = ""
    default_scan_interval_hours: int = Field(default=24, ge=1, le=168)
    jurisdictions: list[str] = ["US"]
    retention_days: int = Field(default=365, ge=30, le=3650)


class SettingsOut(BaseModel):
    notifications: NotificationSettings
    organization: OrganizationProfile


class SettingsPatch(BaseModel):
    notifications: NotificationSettings | None = None
    organization: OrganizationProfile | None = None


class AuditEventOut(BaseModel):
    id: str
    at: datetime
    actor: str
    action: str
    object: str
    incident_id: str | None = None
    site: str | None = None
    detail: str


class NotificationOut(BaseModel):
    id: str
    kind: str
    tone: str | None = None
    title: str
    detail: str | None = None
    at: datetime
    href: str | None = None
    read: bool


# ---------- analytics ----------
class Kpi(BaseModel):
    key: str
    label: str
    value: int | float | str
    delta: str = ""
    series: list[int | float] = []


class ScanActivityDay(BaseModel):
    day: str
    changed: int
    flagged: int


class VerdictCount(BaseModel):
    verdict: str
    count: int


class RecentRun(BaseModel):
    id: str
    site: str
    status: str
    pages: int
    changed: int
    at: datetime
    duration_s: int
    error: str | None = None


class AnalyticsSummary(BaseModel):
    kpis: list[Kpi]
    scan_activity: list[ScanActivityDay]
    by_verdict: list[VerdictCount]
    by_priority: dict[str, int]
    recent_runs: list[RecentRun]
