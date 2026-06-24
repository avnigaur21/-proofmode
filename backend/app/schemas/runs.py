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


VerificationLayer = Literal["ui", "api", "db", "diff"]


class PlannedCheck(BaseModel):
    layer: VerificationLayer
    type: str
    description: str
    target: str | None = None


class VerificationChecklist(BaseModel):
    checks: list[PlannedCheck] = Field(default_factory=list)
    affected_files_hint: list[str] = Field(default_factory=list)


class ProofRunCreate(BaseModel):
    claim: str = Field(..., min_length=1)
    repo_path: str | None = None
    target_url: str | None = None
    api_base_url: str | None = None
    target_db_url: str | None = None


class ProofCheck(BaseModel):
    layer: VerificationLayer
    status: CheckStatus
    summary: str
    evidence: dict[str, Any] = Field(default_factory=dict)


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
    report_path: str | None = None
    report_url: str | None = None
