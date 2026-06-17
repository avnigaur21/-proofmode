from app.schemas.runs import CheckStatus, ProofCheck, ProofRun


class DiffVerifier:
    layer = "diff"

    def verify(self, run: ProofRun) -> ProofCheck:
        if run.repo_path is None:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.UNCERTAIN,
                summary="No repository path was provided, so Git diff analysis was not checked.",
            )

        return ProofCheck(
            layer=self.layer,
            status=CheckStatus.UNCERTAIN,
            summary="Diff verifier is registered. Changed-file analysis will be added next.",
            evidence={"repo_path": run.repo_path},
        )
