from app.schemas.runs import PlannedCheck, ProofRun, VerificationChecklist


class VerificationPlanner:
    def create_checklist(self, run: ProofRun) -> VerificationChecklist:
        checks: list[PlannedCheck] = [
            PlannedCheck(
                layer="diff",
                type="changed_files_detected",
                description="Inspect changed files to decide which verification layers are required.",
                target=run.repo_path,
            )
        ]

        if run.target_url is not None:
            checks.extend(
                [
                    PlannedCheck(
                        layer="ui",
                        type="page_loads",
                        description="Open the target page and confirm the browser can load it.",
                        target=run.target_url,
                    ),
                    PlannedCheck(
                        layer="ui",
                        type="console_errors_absent",
                        description="Capture browser console output and fail on runtime errors.",
                        target=run.target_url,
                    ),
                ]
            )

        if run.api_base_url is not None:
            checks.append(
                PlannedCheck(
                    layer="api",
                    type="api_health_reachable",
                    description="Call the API base URL and confirm it responds before contract checks run.",
                    target=run.api_base_url,
                )
            )

        checks.append(
            PlannedCheck(
                layer="db",
                type="state_snapshot_ready",
                description="Prepare database state snapshot checks when a target database is configured.",
            )
        )

        return VerificationChecklist(
            checks=checks,
            affected_files_hint=self._affected_files_hint(run),
        )

    def _affected_files_hint(self, run: ProofRun) -> list[str]:
        claim = run.claim.lower()
        hints: list[str] = []

        if any(word in claim for word in ["button", "page", "screen", "ui", "frontend"]):
            hints.append("frontend/")
        if any(word in claim for word in ["api", "endpoint", "route", "request"]):
            hints.append("backend/app/routers/")
        if any(word in claim for word in ["database", "db", "migration", "table", "row"]):
            hints.append("backend/app/models/")

        return hints
