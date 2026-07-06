from fastapi import APIRouter, HTTPException

from app.schemas.claims import ClaimIngestionCreate, ClaimIngestionResponse, IngestedClaim
from app.services.claim_ingestion_service import claim_ingestion_service

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("/ingest", response_model=ClaimIngestionResponse)
def ingest_claim(payload: ClaimIngestionCreate) -> ClaimIngestionResponse:
    try:
        return claim_ingestion_service.ingest(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=list[IngestedClaim])
def list_claims() -> list[IngestedClaim]:
    return claim_ingestion_service.list_claims()
