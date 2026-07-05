from app.schemas.runs import (
    ApprovalCreate,
    ApprovalRecord,
    PlannedCheck,
    PlannerMetadata,
    ProofCheck,
    ProofRun,
    ProofRunCreate,
    RunStatus,
    VerificationChecklist,
    VerificationLayer,
)
from app.services.evidence_evaluator import EvidenceEvaluator
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
        self._evaluator = EvidenceEvaluator()
        self._report_generator = ReportGenerator()
        self._timeline = TimelineRecorder()
        self._verifiers: list[tuple[VerificationLayer, object]] = [
            ("ui", UiVerifier()),
            ("api", ApiVerifier()),
            ("db", DbVerifier()),
            ("diff", DiffVerifier()),
        ]

    def create_run(self, payload: ProofRunCreate) -> ProofRun:
        run = ProofRun(
            claim=payload.claim,
            repo_path=payload.repo_path,
            target_url=payload.target_url,
            api_base_url=payload.api_base_url,
            target_db_url=payload.target_db_url,
            run_config=payload.run_config,
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
                "run_config": payload.run_config.model_dump(mode="json"),
            },
        )

        run.checklist = self._create_checklist(run)
        planner_event_type = "planner.completed"
        if run.checklist.planner.used_fallback:
            planner_event_type = "planner.fallback_used"
        elif run.checklist.planner.source == "disabled":
            planner_event_type = "planner.disabled"
        elif run.checklist.planner.source == "llm":
            planner_event_type = "planner.llm_completed"

        self._timeline.record(
            run,
            planner_event_type,
            f"Generated {len(run.checklist.checks)} verification checks.",
            layer="planner",
            status="completed",
            metadata={
                "check_count": len(run.checklist.checks),
                "layers": [check.layer for check in run.checklist.checks],
                "planner": run.checklist.planner.model_dump(mode="json"),
            },
        )

        checks: list[ProofCheck] = []
        for layer, verifier in self._verifiers:
            if not self._is_verifier_enabled(layer, run):
                self._timeline.record(
                    run,
                    f"{layer}.skipped",
                    f"{layer.upper()} verification skipped by run configuration.",
                    layer=layer,
                    status="skipped",
                    metadata={"run_config": run.run_config.model_dump(mode="json")},
                )
                continue

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
        run.evaluation = self._evaluator.evaluate(run)
        self._timeline.record(
            run,
            "evaluator.completed",
            run.evaluation.explanation,
            layer="evaluator",
            status=run.evaluation.verdict,
            metadata={
                "confidence": run.evaluation.confidence,
                "verdict": run.evaluation.verdict,
                "evaluator_mode": run.evaluation.evaluator_mode,
                "guardrails": run.evaluation.guardrails,
            },
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

    def _create_checklist(self, run: ProofRun) -> VerificationChecklist:
        if not run.run_config.planner_enabled:
            return VerificationChecklist(
                checks=self._configured_checks(run),
                affected_files_hint=[],
                planner=PlannerMetadata(
                    mode="disabled",
                    source="disabled",
                    provider="local",
                    reason="planner_disabled_by_run_configuration",
                ),
            )

        checklist = self._planner.create_checklist(run)
        checklist.checks = [
            check for check in checklist.checks if run.run_config.is_layer_enabled(check.layer)
        ]
        return checklist

    def _configured_checks(self, run: ProofRun) -> list[PlannedCheck]:
        checks: list[PlannedCheck] = []

        if run.run_config.diff_enabled:
            checks.append(
                PlannedCheck(
                    layer="diff",
                    type="changed_files_detected",
                    description="Inspect changed files because Git diff verification is enabled for this run.",
                    target=run.repo_path,
                )
            )

        if run.run_config.ui_enabled:
            checks.append(
                PlannedCheck(
                    layer="ui",
                    type="page_loads",
                    description="Open the configured target URL and capture browser evidence.",
                    target=run.target_url,
                )
            )

        if run.run_config.api_enabled:
            checks.append(
                PlannedCheck(
                    layer="api",
                    type="api_contract_check",
                    description="Call the configured API URL and compare contract evidence.",
                    target=run.api_base_url,
                )
            )

        if run.run_config.db_enabled:
            checks.append(
                PlannedCheck(
                    layer="db",
                    type="data_state_snapshot",
                    description="Snapshot configured database schema and row counts.",
                    target=self._mask_db_url(run.target_db_url) if run.target_db_url else None,
                )
            )

        return checks

    def _is_verifier_enabled(self, layer: VerificationLayer, run: ProofRun) -> bool:
        return run.run_config.is_layer_enabled(layer)

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
        if not checks:
            return RunStatus.UNCERTAIN
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

    def _mask_db_url(self, db_url: str) -> str:
        if "@" not in db_url:
            return db_url

        scheme, rest = db_url.split("://", 1) if "://" in db_url else ("", db_url)
        location = rest.split("@", 1)[1]
        return f"{scheme}://***@{location}" if scheme else f"***@{location}"


run_service = RunService()
