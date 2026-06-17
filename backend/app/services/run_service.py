from app.schemas.runs import ProofCheck, ProofRun, ProofRunCreate, RunStatus
from app.verifiers.api_verifier import ApiVerifier
from app.verifiers.db_verifier import DbVerifier
from app.verifiers.diff_verifier import DiffVerifier
from app.verifiers.ui_verifier import UiVerifier


class RunService:
    def __init__(self) -> None:
        self._runs: dict[str, ProofRun] = {}
        self._verifiers = [
            UiVerifier(),
            ApiVerifier(),
            DbVerifier(),
            DiffVerifier(),
        ]

    def create_run(self, payload: ProofRunCreate) -> ProofRun:
        run = ProofRun(
            claim=payload.claim,
            repo_path=payload.repo_path,
            target_url=payload.target_url,
            api_base_url=payload.api_base_url,
            status=RunStatus.RUNNING,
        )

        checks = [verifier.verify(run) for verifier in self._verifiers]
        run.checks = checks
        run.status = self._calculate_status(checks)
        self._runs[run.id] = run
        return run

    def list_runs(self) -> list[ProofRun]:
        return sorted(self._runs.values(), key=lambda run: run.created_at, reverse=True)

    def get_run(self, run_id: str) -> ProofRun | None:
        return self._runs.get(run_id)

    def _calculate_status(self, checks: list[ProofCheck]) -> RunStatus:
        if any(check.status == "failed" for check in checks):
            return RunStatus.FAILED
        if any(check.status == "uncertain" for check in checks):
            return RunStatus.UNCERTAIN
        return RunStatus.PASSED


run_service = RunService()
