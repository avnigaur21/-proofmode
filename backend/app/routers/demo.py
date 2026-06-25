from fastapi import APIRouter

from app.schemas.runs import ProofRun
from app.services.demo_seed import demo_seed_service

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/seed", response_model=list[ProofRun])
def seed_demo_runs() -> list[ProofRun]:
    return demo_seed_service.seed()
