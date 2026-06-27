import os

from app.schemas.settings import SettingsStatus
from app.services.artifacts import artifact_root


class SettingsStatusService:
    def get_status(self) -> SettingsStatus:
        root = artifact_root()
        return SettingsStatus(
            backend_status="online",
            planner_mode=os.getenv("PROOFMODE_PLANNER_MODE", "deterministic"),
            llm_provider=os.getenv("PROOFMODE_LLM_PROVIDER", "heuristic"),
            llm_model=os.getenv("PROOFMODE_LLM_MODEL", "gpt-4.1-mini"),
            openai_api_key_configured=bool(os.getenv("OPENAI_API_KEY")),
            artifact_root=str(root),
            run_persistence_enabled=True,
            runs_directory=str(root / "runs"),
        )


settings_status_service = SettingsStatusService()
