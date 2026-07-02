from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.runs import RunConfiguration


class ProjectProfileCreate(BaseModel):
    name: str = Field(..., min_length=1)
    repo_path: str | None = None
    target_url: str | None = None
    api_base_url: str | None = None
    target_db_url: str | None = None
    default_run_config: RunConfiguration = Field(default_factory=RunConfiguration)


class ProjectProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    repo_path: str | None = None
    target_url: str | None = None
    api_base_url: str | None = None
    target_db_url: str | None = None
    default_run_config: RunConfiguration | None = None


class ProjectProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    repo_path: str | None = None
    target_url: str | None = None
    api_base_url: str | None = None
    target_db_url: str | None = None
    default_run_config: RunConfiguration = Field(default_factory=RunConfiguration)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
