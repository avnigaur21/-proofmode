from app.schemas.runs import CheckStatus, ProofCheck, ProofRun


class UiVerifier:
    layer = "ui"

    def verify(self, run: ProofRun) -> ProofCheck:
        if run.target_url is None:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.UNCERTAIN,
                summary="No target URL was provided, so UI behavior was not checked.",
            )

        return ProofCheck(
            layer=self.layer,
            status=CheckStatus.UNCERTAIN,
            summary="UI verifier is registered. Playwright browser checks will be added next.",
            evidence={"target_url": run.target_url},
        )
