from pydantic import BaseModel


class SettingsStatus(BaseModel):
    backend_status: str
    planner_mode: str
    evaluator_mode: str
    llm_provider: str
    llm_model: str
    openai_api_key_configured: bool
    artifact_root: str
    run_persistence_enabled: bool
    runs_directory: str
