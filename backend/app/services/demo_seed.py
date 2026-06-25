import json
from datetime import datetime, timezone
from typing import Any

from app.schemas.runs import (
    CheckStatus,
    PlannedCheck,
    ProofCheck,
    ProofRun,
    RunStatus,
    TimelineEvent,
    VerificationChecklist,
)
from app.services.artifacts import artifact_root
from app.services.run_service import RunService, run_service


class DemoSeedService:
    def __init__(self, runs: RunService = run_service) -> None:
        self._runs = runs

    def seed(self) -> list[ProofRun]:
        self._write_demo_artifacts()
        seeded_runs = [
            self._ghost_completion_run(),
            self._contract_drift_run(),
            self._state_blindness_run(),
        ]
        return [self._runs.save_run(run) for run in seeded_runs]

    def _write_demo_artifacts(self) -> None:
        api_snapshot_dir = artifact_root() / "snapshots" / "api"
        db_snapshot_dir = artifact_root() / "snapshots" / "db"
        api_snapshot_dir.mkdir(parents=True, exist_ok=True)
        db_snapshot_dir.mkdir(parents=True, exist_ok=True)

        (api_snapshot_dir / "demo-contract-drift.json").write_text(
            json.dumps(
                {
                    "endpoint": "GET /api/user/profile",
                    "baseline": {"user": {"id": "string", "email": "string", "name": "string"}},
                    "current": {"user": {"id": "number", "name": "string"}},
                    "issues": ["user.email removed", "user.id changed from string to number"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (db_snapshot_dir / "demo-state-blindness.json").write_text(
            json.dumps(
                {
                    "table": "projects",
                    "before": {"row_count": 12},
                    "after": {"row_count": 12},
                    "expected_delta": 1,
                    "issues": ["Expected one new project row, but row count did not change"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _ghost_completion_run(self) -> ProofRun:
        checks = [
            ProofCheck(
                layer="ui",
                status=CheckStatus.FAILED,
                summary="The login button rendered, but clicking it did not trigger navigation or a network request.",
                evidence={
                    "issues": [
                        {
                            "type": "click_no_effect",
                            "severity": "high",
                            "selector": "[data-testid='login-submit']",
                            "expected": "Submit credentials or navigate to authentication flow",
                            "actual": "No request, route change, or visible state update was observed",
                        }
                    ],
                    "console_errors": [],
                    "network_failures": [],
                },
            ),
            ProofCheck(
                layer="api",
                status=CheckStatus.UNCERTAIN,
                summary="No authentication endpoint was provided for this demo claim.",
                evidence={"issues": [{"type": "missing_api_target", "severity": "medium"}]},
            ),
            ProofCheck(
                layer="db",
                status=CheckStatus.UNCERTAIN,
                summary="No database target was provided, so login state persistence could not be checked.",
                evidence={"issues": [{"type": "missing_db_target", "severity": "medium"}]},
            ),
            ProofCheck(
                layer="diff",
                status=CheckStatus.PASSED,
                summary="Frontend login files changed, so UI proof was required.",
                evidence={
                    "changed_files": [
                        {"path": "frontend/src/pages/Login.tsx", "categories": ["ui"]},
                        {"path": "frontend/src/components/LoginButton.tsx", "categories": ["ui"]},
                    ],
                    "recommended_layers": ["ui"],
                    "category_summary": {"ui": 2},
                },
            ),
        ]
        return self._demo_run(
            run_id="demo-ghost-completion",
            claim="Demo: Agent says the login button is done, but the click is not wired.",
            status=RunStatus.FAILED,
            checklist=[
                PlannedCheck(
                    layer="ui",
                    type="element_clickable",
                    description="Click the login button and confirm it produces a visible app action.",
                    target="[data-testid='login-submit']",
                ),
                PlannedCheck(
                    layer="diff",
                    type="changed_files_detected",
                    description="Confirm UI files changed and require browser-level proof.",
                ),
            ],
            checks=checks,
            scenario="ghost_completion",
        )

    def _contract_drift_run(self) -> ProofRun:
        checks = [
            ProofCheck(
                layer="ui",
                status=CheckStatus.UNCERTAIN,
                summary="The UI target was not part of this API-focused demo.",
                evidence={},
            ),
            ProofCheck(
                layer="api",
                status=CheckStatus.FAILED,
                summary="The user profile API response no longer matches the saved contract baseline.",
                evidence={
                    "issues": [
                        {
                            "type": "field_removed",
                            "severity": "high",
                            "endpoint": "GET /api/user/profile",
                            "field": "user.email",
                        },
                        {
                            "type": "field_type_changed",
                            "severity": "medium",
                            "endpoint": "GET /api/user/profile",
                            "field": "user.id",
                            "before": "string",
                            "after": "number",
                        },
                    ],
                    "snapshot_url": "/artifacts/snapshots/api/demo-contract-drift.json",
                },
            ),
            ProofCheck(
                layer="db",
                status=CheckStatus.UNCERTAIN,
                summary="Database state was not required to prove this contract drift demo.",
                evidence={},
            ),
            ProofCheck(
                layer="diff",
                status=CheckStatus.PASSED,
                summary="API route files changed, so contract verification was required.",
                evidence={
                    "changed_files": [
                        {"path": "backend/app/routers/users.py", "categories": ["api"]},
                        {"path": "frontend/src/services/userApi.ts", "categories": ["ui", "api"]},
                    ],
                    "recommended_layers": ["api", "ui"],
                    "category_summary": {"api": 2, "ui": 1},
                },
            ),
        ]
        return self._demo_run(
            run_id="demo-contract-drift",
            claim="Demo: Agent says the user API update is safe, but the response contract drifted.",
            status=RunStatus.FAILED,
            checklist=[
                PlannedCheck(
                    layer="api",
                    type="schema_matches_baseline",
                    description="Compare the current user profile response shape against the saved API baseline.",
                    target="GET /api/user/profile",
                ),
                PlannedCheck(
                    layer="diff",
                    type="api_files_changed",
                    description="Confirm backend route changes require API contract proof.",
                ),
            ],
            checks=checks,
            scenario="contract_drift",
        )

    def _state_blindness_run(self) -> ProofRun:
        checks = [
            ProofCheck(
                layer="ui",
                status=CheckStatus.UNCERTAIN,
                summary="The UI did not provide enough evidence that data was persisted.",
                evidence={},
            ),
            ProofCheck(
                layer="api",
                status=CheckStatus.PASSED,
                summary="The save endpoint returned a successful response.",
                evidence={"status_code": 200, "endpoint": "POST /api/projects"},
            ),
            ProofCheck(
                layer="db",
                status=CheckStatus.FAILED,
                summary="The API claimed success, but the projects table row count did not change.",
                evidence={
                    "issues": [
                        {
                            "type": "expected_row_count_change_missing",
                            "severity": "high",
                            "table": "projects",
                            "before_count": 12,
                            "after_count": 12,
                            "expected_delta": 1,
                        }
                    ],
                    "snapshot_url": "/artifacts/snapshots/db/demo-state-blindness.json",
                },
            ),
            ProofCheck(
                layer="diff",
                status=CheckStatus.PASSED,
                summary="Backend model and API files changed, so DB proof was required.",
                evidence={
                    "changed_files": [
                        {"path": "backend/app/routers/projects.py", "categories": ["api"]},
                        {"path": "backend/app/models/project.py", "categories": ["db"]},
                    ],
                    "recommended_layers": ["api", "db"],
                    "category_summary": {"api": 1, "db": 1},
                },
            ),
        ]
        return self._demo_run(
            run_id="demo-state-blindness",
            claim="Demo: Agent says project save works, but no database row was created.",
            status=RunStatus.FAILED,
            checklist=[
                PlannedCheck(
                    layer="api",
                    type="status_code_ok",
                    description="Confirm the save endpoint returns a successful response.",
                    target="POST /api/projects",
                ),
                PlannedCheck(
                    layer="db",
                    type="row_count_changed",
                    description="Compare project table row counts before and after the save claim.",
                    target="projects",
                ),
            ],
            checks=checks,
            scenario="state_blindness",
        )

    def _demo_run(
        self,
        *,
        run_id: str,
        claim: str,
        status: RunStatus,
        checklist: list[PlannedCheck],
        checks: list[ProofCheck],
        scenario: str,
    ) -> ProofRun:
        run = ProofRun(
            id=run_id,
            claim=claim,
            status=status,
            checklist=VerificationChecklist(checks=checklist, affected_files_hint=[]),
            checks=checks,
        )
        run.timeline = self._timeline_for(run, scenario)
        return run

    def _timeline_for(self, run: ProofRun, scenario: str) -> list[TimelineEvent]:
        events: list[TimelineEvent] = [
            self._event(
                "demo.seeded",
                "Demo verification run seeded for product walkthrough.",
                layer="run",
                status="completed",
                metadata={"scenario": scenario},
            ),
            self._event(
                "planner.completed",
                f"Generated {len(run.checklist.checks)} demo verification checks.",
                layer="planner",
                status="completed",
                metadata={"scenario": scenario},
            ),
        ]
        events.extend(
            self._event(
                f"{check.layer}.completed",
                check.summary,
                layer=check.layer,
                status=check.status,
                evidence=self._evidence_for_timeline(check.evidence),
            )
            for check in run.checks
        )
        events.extend(
            [
                self._event(
                    "run.verdict_assigned",
                    f"Final verdict assigned: {run.status}.",
                    layer="run",
                    status=run.status,
                    metadata={"scenario": scenario},
                ),
                self._event(
                    "run.completed",
                    "Demo verification run completed and persisted.",
                    layer="run",
                    status=run.status,
                    metadata={"scenario": scenario},
                ),
            ]
        )
        return events

    def _event(
        self,
        event_type: str,
        message: str,
        *,
        layer: str,
        status: str,
        evidence: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TimelineEvent:
        return TimelineEvent(
            timestamp=datetime.now(timezone.utc),
            type=event_type,
            layer=layer,  # type: ignore[arg-type]
            status=status,
            message=message,
            evidence=evidence or {},
            metadata=metadata or {},
        )

    def _evidence_for_timeline(self, evidence: dict[str, Any]) -> dict[str, Any]:
        keys = ("issues", "snapshot_url", "changed_files", "recommended_layers")
        return {key: evidence[key] for key in keys if key in evidence}


demo_seed_service = DemoSeedService()
