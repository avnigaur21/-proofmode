from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


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


class EvidenceVerdict(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT = "insufficient"


VerificationLayer = Literal["ui", "api", "db", "diff"]
TimelineLayer = Literal["run", "planner", "evaluator", "ui", "api", "db", "diff", "report"]


class PlannedCheck(BaseModel):
    layer: VerificationLayer
    type: str
    description: str
    target: str | None = None
    assertions: dict[str, Any] = Field(default_factory=dict)


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


class RunConfiguration(BaseModel):
    ui_enabled: bool = True
    api_enabled: bool = True
    db_enabled: bool = True
    diff_enabled: bool = True
    planner_enabled: bool = True
    approval_required: bool = True

    def is_layer_enabled(self, layer: VerificationLayer) -> bool:
        return bool(getattr(self, f"{layer}_enabled"))


class ProofRunCreate(BaseModel):
    claim: str = Field(..., min_length=1)
    repo_path: str | None = None
    target_url: str | None = None
    api_base_url: str | None = None
    target_db_url: str | None = None
    run_config: RunConfiguration = Field(default_factory=RunConfiguration)

    @model_validator(mode="after")
    def validate_run_setup(self) -> "ProofRunCreate":
        issues: list[str] = []

        if self.run_config.ui_enabled and self._is_blank(self.target_url):
            issues.append("target_url is required when UI verification is enabled")

        if self.run_config.api_enabled and self._is_blank(self.api_base_url):
            issues.append("api_base_url is required when API verification is enabled")

        if self.run_config.db_enabled and self._is_blank(self.target_db_url):
            issues.append("target_db_url is required when database verification is enabled")

        if self.run_config.diff_enabled and self._is_blank(self.repo_path):
            issues.append("repo_path is required when Git diff analysis is enabled")

        if not any(
            (
                self.run_config.ui_enabled,
                self.run_config.api_enabled,
                self.run_config.db_enabled,
                self.run_config.diff_enabled,
            )
        ):
            issues.append("at least one automated proof check must be enabled")

        if issues:
            raise ValueError("; ".join(issues))

        return self

    def _is_blank(self, value: str | None) -> bool:
        return value is None or value.strip() == ""


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


class EvidenceEvaluation(BaseModel):
    verdict: EvidenceVerdict
    confidence: float = Field(ge=0, le=1)
    explanation: str
    reasons: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    evaluator_mode: str = "deterministic"
    provider: str | None = None
    model: str | None = None


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
    run_config: RunConfiguration = Field(default_factory=RunConfiguration)
    checklist: VerificationChecklist = Field(default_factory=VerificationChecklist)
    checks: list[ProofCheck] = Field(default_factory=list)
    evaluation: EvidenceEvaluation | None = None
    timeline: list[TimelineEvent] = Field(default_factory=list)
    approval: ApprovalRecord | None = None
    report_path: str | None = None
    report_url: str | None = None
