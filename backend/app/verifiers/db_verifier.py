from app.schemas.runs import CheckStatus, ProofCheck, ProofRun


class DbVerifier:
    layer = "db"

    def verify(self, run: ProofRun) -> ProofCheck:
        return ProofCheck(
            layer=self.layer,
            status=CheckStatus.UNCERTAIN,
            summary="Database verifier is registered. Snapshot and schema checks will be added later.",
        )
