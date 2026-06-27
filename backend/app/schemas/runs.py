from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class CheckStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    FIX_REQUESTED = "fix_requested"


VerificationLayer = Literal["ui", "api", "db", "diff"]
TimelineLayer = Literal["run", "planner", "ui", "api", "db", "diff", "report"]


class PlannedCheck(BaseModel):
    layer: VerificationLayer
    type: str
    description: str
    target: str | None = None


class PlannerMetadata(BaseModel):
    mode: str = "deterministic"
    source: str = "deterministic"
    provider: str | None = None
    model: str | None = None
    used_fallback: bool = False
    reason: str | None = None
    diff_files_used: int = 0
    diff_truncated: bool = False


class VerificationChecklist(BaseModel):
    checks: list[PlannedCheck] = Field(default_factory=list)
    affected_files_hint: list[str] = Field(default_factory=list)
    planner: PlannerMetadata = Field(default_factory=PlannerMetadata)


class ProofRunCreate(BaseModel):
    claim: str = Field(..., min_length=1)
    repo_path: str | None = None
    target_url: str | None = None
    api_base_url: str | None = None
    target_db_url: str | None = None


class ApprovalCreate(BaseModel):
    decision: ApprovalDecision
    note: str | None = None
    reviewer: str | None = None


class ApprovalRecord(BaseModel):
    decision: ApprovalDecision
    note: str | None = None
    reviewer: str | None = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProofCheck(BaseModel):
    layer: VerificationLayer
    status: CheckStatus
    summary: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class TimelineEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    type: str
    layer: TimelineLayer
    status: str | None = None
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProofRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    claim: str
    status: RunStatus = RunStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    repo_path: str | None = None
    target_url: str | None = None
    api_base_url: str | None = None
    target_db_url: str | None = None
    checklist: VerificationChecklist = Field(default_factory=VerificationChecklist)
    checks: list[ProofCheck] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    approval: ApprovalRecord | None = None
    report_path: str | None = None
    report_url: str | None = None
