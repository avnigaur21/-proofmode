from fastapi import APIRouter, HTTPException

from app.schemas.runs import ProofRun, ProofRunCreate
from app.services.run_service import run_service

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=ProofRun)
def create_run(payload: ProofRunCreate) -> ProofRun:
    return run_service.create_run(payload)


@router.get("", response_model=list[ProofRun])
def list_runs() -> list[ProofRun]:
    return run_service.list_runs()


@router.get("/{run_id}", response_model=ProofRun)
def get_run(run_id: str) -> ProofRun:
    run = run_service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run

