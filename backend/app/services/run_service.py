from app.schemas.runs import ApprovalCreate, ApprovalRecord, ProofCheck, ProofRun, ProofRunCreate, RunStatus
from app.services.planner import VerificationPlanner
from app.services.report_generator import ReportGenerator
from app.services.run_store import RunStore
from app.services.timeline import TimelineRecorder
from app.verifiers.api_verifier import ApiVerifier
from app.verifiers.db_verifier import DbVerifier
from app.verifiers.diff_verifier import DiffVerifier
from app.verifiers.ui_verifier import UiVerifier


class RunService:
    def __init__(self) -> None:
        self._store = RunStore()
        self._runs: dict[str, ProofRun] = self._store.load_all()
        self._planner = VerificationPlanner()
        self._report_generator = ReportGenerator()
        self._timeline = TimelineRecorder()
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
            target_db_url=payload.target_db_url,
            status=RunStatus.RUNNING,
        )
        self._timeline.record(
            run,
            "run.created",
            "Verification run created from agent claim.",
            layer="run",
            status=run.status,
            metadata={
                "has_target_url": bool(payload.target_url),
                "has_api_base_url": bool(payload.api_base_url),
                "has_target_db_url": bool(payload.target_db_url),
                "has_repo_path": bool(payload.repo_path),
            },
        )

        run.checklist = self._planner.create_checklist(run)
        self._timeline.record(
            run,
            "planner.completed",
            f"Generated {len(run.checklist.checks)} verification checks.",
            layer="planner",
            status="completed",
            metadata={
                "check_count": len(run.checklist.checks),
                "layers": [check.layer for check in run.checklist.checks],
            },
        )

        checks: list[ProofCheck] = []
        for verifier in self._verifiers:
            check = verifier.verify(run)
            checks.append(check)
            self._timeline.record(
                run,
                f"{check.layer}.completed",
                check.summary,
                layer=check.layer,
                status=check.status,
                evidence=self._timeline_evidence_for_check(check),
                metadata={"layer": check.layer},
            )

        run.checks = checks
        run.status = self._calculate_status(checks)
        self._timeline.record(
            run,
            "run.verdict_assigned",
            f"Final verdict assigned: {run.status}.",
            layer="run",
            status=run.status,
            metadata={"check_statuses": {check.layer: check.status for check in checks}},
        )
        report_artifact = self._report_generator.artifact_for(run)
        run.report_path = report_artifact["path"]
        run.report_url = report_artifact["url"]
        self._timeline.record(
            run,
            "report.generated",
            "Markdown proof report generated.",
            layer="report",
            status="completed",
            evidence={"report_path": run.report_path, "report_url": run.report_url},
        )
        self._timeline.record(
            run,
            "run.completed",
            "Verification run completed and persisted.",
            layer="run",
            status=run.status,
        )
        self._report_generator.write_markdown(run)
        self._runs[run.id] = run
        self._store.save(run)
        return run

    def list_runs(self) -> list[ProofRun]:
        return sorted(self._runs.values(), key=lambda run: run.created_at, reverse=True)

    def get_run(self, run_id: str) -> ProofRun | None:
        return self._runs.get(run_id)

    def save_run(self, run: ProofRun) -> ProofRun:
        report_artifact = self._report_generator.artifact_for(run)
        run.report_path = report_artifact["path"]
        run.report_url = report_artifact["url"]
        self._report_generator.write_markdown(run)
        self._runs[run.id] = run
        self._store.save(run)
        return run

    def record_approval(self, run_id: str, payload: ApprovalCreate) -> ProofRun | None:
        run = self._runs.get(run_id)
        if run is None:
            return None

        run.approval = ApprovalRecord(
            decision=payload.decision,
            note=payload.note,
            reviewer=payload.reviewer,
        )
        self._timeline.record(
            run,
            f"approval.{payload.decision}",
            self._approval_message(run.approval),
            layer="run",
            status=payload.decision,
            metadata={
                "decision": payload.decision,
                "reviewer": payload.reviewer,
                "has_note": bool(payload.note),
            },
        )
        self._report_generator.write_markdown(run)
        self._store.save(run)
        return run

    def _calculate_status(self, checks: list[ProofCheck]) -> RunStatus:
        if any(check.status == "failed" for check in checks):
            return RunStatus.FAILED
        if any(check.status == "uncertain" for check in checks):
            return RunStatus.UNCERTAIN
        return RunStatus.PASSED

    def _timeline_evidence_for_check(self, check: ProofCheck) -> dict[str, object]:
        evidence_keys = (
            "screenshot_url",
            "snapshot_url",
            "evidence_url",
            "issues",
            "changed_files",
            "recommended_layers",
        )
        return {key: check.evidence[key] for key in evidence_keys if key in check.evidence}

    def _approval_message(self, approval: ApprovalRecord) -> str:
        reviewer = approval.reviewer or "Reviewer"
        if approval.decision == "approved":
            return f"{reviewer} approved the proof."
        if approval.decision == "rejected":
            return f"{reviewer} rejected the proof."
        return f"{reviewer} requested fixes before approval."


run_service = RunService()
