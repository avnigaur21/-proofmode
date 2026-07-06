import json
from pathlib import Path

from pydantic import ValidationError

from app.schemas.claims import IngestedClaim
from app.services.artifacts import artifact_root


class ClaimStore:
    def __init__(self) -> None:
        self._claims_dir = artifact_root() / "claims"
        self._claims_dir.mkdir(parents=True, exist_ok=True)

    def save(self, claim: IngestedClaim) -> None:
        claim_path = self._claim_path(claim.id)
        claim_path.write_text(
            json.dumps(claim.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def load_all(self) -> dict[str, IngestedClaim]:
        claims: dict[str, IngestedClaim] = {}

        for claim_path in sorted(self._claims_dir.glob("*.json")):
            try:
                claim = IngestedClaim.model_validate_json(claim_path.read_text(encoding="utf-8"))
            except (OSError, ValidationError, ValueError):
                continue

            claims[claim.id] = claim

        return claims

    def _claim_path(self, claim_id: str) -> Path:
        return self._claims_dir / f"{claim_id}.json"
