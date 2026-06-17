from app.schemas.runs import CheckStatus, ProofCheck, ProofRun


class ApiVerifier:
    layer = "api"

    def verify(self, run: ProofRun) -> ProofCheck:
        if run.api_base_url is None:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.UNCERTAIN,
                summary="No API base URL was provided, so API contracts were not checked.",
            )

        return ProofCheck(
            layer=self.layer,
            status=CheckStatus.UNCERTAIN,
            summary="API verifier is registered. Endpoint contract checks will be added next.",
            evidence={"api_base_url": run.api_base_url},
        )
