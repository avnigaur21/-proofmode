from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.runs import ProofRun, RunConfiguration, TestCommandCheck


class ClaimIngestionCreate(BaseModel):
    claim: str = Field(..., min_length=1)
    agent_report: str | None = None
    source: str = Field(default="manual", min_length=1)
    agent_name: str | None = None
    project_id: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    repo_path: str | None = None
    target_url: str | None = None
    api_base_url: str | None = None
    target_db_url: str | None = None
    test_commands: list[TestCommandCheck] = Field(default_factory=list)
    run_config: RunConfiguration | None = None


class IngestedClaim(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    claim: str
    agent_report: str | None = None
    source: str
    agent_name: str | None = None
    project_id: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClaimIngestionResponse(BaseModel):
    claim_record: IngestedClaim
    run: ProofRun
