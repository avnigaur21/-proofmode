from app.schemas.claims import ClaimIngestionCreate, ClaimIngestionResponse, IngestedClaim
from app.schemas.runs import ClaimSourceMetadata, ProofRunCreate, RunConfiguration
from app.services.claim_store import ClaimStore
from app.services.project_service import project_service
from app.services.run_service import run_service


class ClaimIngestionService:
    def __init__(self) -> None:
        self._store = ClaimStore()
        self._claims: dict[str, IngestedClaim] = self._store.load_all()

    def ingest(self, payload: ClaimIngestionCreate) -> ClaimIngestionResponse:
        project = project_service.get_project(payload.project_id) if payload.project_id else None
        if payload.project_id and project is None:
            raise LookupError("Project not found")

        run_payload = ProofRunCreate(
            claim=payload.claim,
            agent_report=payload.agent_report,
            repo_path=self._first_defined(payload.repo_path, project.repo_path if project else None),
            target_url=self._first_defined(payload.target_url, project.target_url if project else None),
            api_base_url=self._first_defined(payload.api_base_url, project.api_base_url if project else None),
            target_db_url=self._first_defined(payload.target_db_url, project.target_db_url if project else None),
            run_config=payload.run_config or (project.default_run_config if project else RunConfiguration()),
            claim_source=ClaimSourceMetadata(
                source=payload.source,
                agent_name=payload.agent_name,
                project_id=payload.project_id,
                external_id=payload.external_id,
                metadata=payload.metadata,
            ),
        )
        run = run_service.create_run(run_payload)

        claim_record = IngestedClaim(
            claim=payload.claim,
            agent_report=payload.agent_report,
            source=payload.source,
            agent_name=payload.agent_name,
            project_id=payload.project_id,
            external_id=payload.external_id,
            metadata=payload.metadata,
            raw_payload=payload.raw_payload or payload.model_dump(mode="json", exclude={"raw_payload"}),
            run_id=run.id,
        )
        self._claims[claim_record.id] = claim_record
        self._store.save(claim_record)
        return ClaimIngestionResponse(claim_record=claim_record, run=run)

    def list_claims(self) -> list[IngestedClaim]:
        return sorted(self._claims.values(), key=lambda claim: claim.created_at, reverse=True)

    def _first_defined(self, preferred: str | None, fallback: str | None) -> str | None:
        if preferred is not None:
            return preferred
        return fallback


claim_ingestion_service = ClaimIngestionService()
