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


class SelfReportVerdict(StrEnum):
    ALIGNED = "aligned"
    PARTIALLY_UNSUPPORTED = "partially_unsupported"
    CONTRADICTED = "contradicted"
    NOT_PROVIDED = "not_provided"


VerificationLayer = Literal["ui", "api", "db", "diff", "tests"]
TimelineLayer = Literal["run", "planner", "evaluator", "ui", "api", "db", "diff", "tests", "report"]


class PlannedCheck(BaseModel):
    layer: VerificationLayer
    type: str
    description: str
    target: str | None = None
    assertions: dict[str, Any] = Field(default_factory=dict)


class ApiEndpointCheck(BaseModel):
    name: str = Field(..., min_length=1)
    method: str = "GET"
    path: str = Field(..., min_length=1)
    expected_status: int = 200
    required_fields: list[str] = Field(default_factory=list)


class UiFlowStep(BaseModel):
    action: Literal["click", "fill", "expect_text", "expect_url", "expect_selector"]
    selector: str | None = None
    text: str | None = None
    value: str | None = None
    url_contains: str | None = None


class UiFlowCheck(BaseModel):
    name: str = Field(..., min_length=1)
    path: str | None = None
    steps: list[UiFlowStep] = Field(default_factory=list)


class TestCommandCheck(BaseModel):
    name: str = Field(..., min_length=1)
    command: str = Field(..., min_length=1)
    working_directory: str | None = None
    timeout_seconds: int = Field(default=120, ge=1, le=900)


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
    tests_enabled: bool = False
    planner_enabled: bool = True
    approval_required: bool = True

    def is_layer_enabled(self, layer: VerificationLayer) -> bool:
        return bool(getattr(self, f"{layer}_enabled"))


class ClaimSourceMetadata(BaseModel):
    source: str = "manual"
    agent_name: str | None = None
    project_id: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProofRunCreate(BaseModel):
    claim: str = Field(..., min_length=1)
    agent_report: str | None = None
    repo_path: str | None = None
    target_url: str | None = None
    api_base_url: str | None = None
    target_db_url: str | None = None
    api_checks: list[ApiEndpointCheck] = Field(default_factory=list)
    ui_flows: list[UiFlowCheck] = Field(default_factory=list)
    test_commands: list[TestCommandCheck] = Field(default_factory=list)
    run_config: RunConfiguration = Field(default_factory=RunConfiguration)
    claim_source: ClaimSourceMetadata = Field(default_factory=ClaimSourceMetadata)

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
                self.run_config.tests_enabled,
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


class EvaluationRubricScore(BaseModel):
    name: str
    score: float = Field(ge=0, le=1)
    label: str
    explanation: str


class EvidenceEvaluation(BaseModel):
    verdict: EvidenceVerdict
    confidence: float = Field(ge=0, le=1)
    explanation: str
    reasons: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    rubrics: list[EvaluationRubricScore] = Field(default_factory=list)
    evaluator_mode: str = "deterministic"
    provider: str | None = None
    model: str | None = None


class SelfReportMismatch(BaseModel):
    topic: str
    severity: str
    agent_statement: str
    evidence_status: str
    explanation: str


class SelfReportComparison(BaseModel):
    verdict: SelfReportVerdict = SelfReportVerdict.NOT_PROVIDED
    confidence: float = Field(ge=0, le=1, default=0)
    summary: str = "No agent self-report was provided."
    detected_claims: list[str] = Field(default_factory=list)
    mismatches: list[SelfReportMismatch] = Field(default_factory=list)
    supported_statements: list[str] = Field(default_factory=list)


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
    api_checks: list[ApiEndpointCheck] = Field(default_factory=list)
    ui_flows: list[UiFlowCheck] = Field(default_factory=list)
    test_commands: list[TestCommandCheck] = Field(default_factory=list)
    run_config: RunConfiguration = Field(default_factory=RunConfiguration)
    claim_source: ClaimSourceMetadata = Field(default_factory=ClaimSourceMetadata)
    checklist: VerificationChecklist = Field(default_factory=VerificationChecklist)
    checks: list[ProofCheck] = Field(default_factory=list)
    evaluation: EvidenceEvaluation | None = None
    timeline: list[TimelineEvent] = Field(default_factory=list)
    approval: ApprovalRecord | None = None
    report_path: str | None = None
    report_url: str | None = None
    agent_report: str | None = None
    self_report_comparison: SelfReportComparison | None = None
