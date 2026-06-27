from fastapi import APIRouter

from app.schemas.settings import SettingsStatus
from app.services.settings_status import settings_status_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/status", response_model=SettingsStatus)
def get_settings_status() -> SettingsStatus:
    return settings_status_service.get_status()
