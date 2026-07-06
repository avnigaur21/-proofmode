import os

from app.schemas.runs import PlannedCheck, ProofRun, VerificationChecklist
from app.services.diff_analysis import recommended_layers, summarize_categories
from app.services.git_diff_context import GitDiffContextService
from app.services.llm_planner import LlmVerificationPlanner


class VerificationPlanner:
    def __init__(
        self,
        *,
        mode: str | None = None,
        diff_context_service: GitDiffContextService | None = None,
        llm_planner: LlmVerificationPlanner | None = None,
    ) -> None:
        self._mode = mode or os.getenv("PROOFMODE_PLANNER_MODE", "deterministic")
        self._diff_context_service = diff_context_service or GitDiffContextService()
        self._llm_planner = llm_planner or LlmVerificationPlanner()

    def create_checklist(self, run: ProofRun) -> VerificationChecklist:
        if self._mode == "llm":
            return self._create_llm_checklist(run)
        return self._create_deterministic_checklist(run)

    def _create_llm_checklist(self, run: ProofRun) -> VerificationChecklist:
        diff_context = self._diff_context_service.build(
            run.repo_path,
            diff_base=self._metadata_string(run, "diff_base"),
            diff_head=self._metadata_string(run, "diff_head"),
        )
        llm_result = self._llm_planner.create_checklist(run.claim, diff_context)
        if llm_result.checklist is not None:
            return self._ensure_diff_check(llm_result.checklist, run)

        fallback = self._create_deterministic_checklist(run)
        fallback.planner.mode = "llm"
        fallback.planner.source = "deterministic_fallback"
        fallback.planner.provider = llm_result.metadata.provider
        fallback.planner.model = llm_result.metadata.model
        fallback.planner.used_fallback = True
        fallback.planner.reason = llm_result.metadata.reason or "llm_planner_failed"
        fallback.planner.diff_files_used = llm_result.metadata.diff_files_used
        fallback.planner.diff_truncated = llm_result.metadata.diff_truncated
        return fallback

    def _create_deterministic_checklist(self, run: ProofRun) -> VerificationChecklist:
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
                        assertions={"url_contains": self._url_path_hint(run.target_url)},
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
                    assertions={"method": "GET", "path": run.api_base_url, "expected_status": 200},
                )
            )

        if run.target_db_url is not None:
            checks.extend(
                [
                    PlannedCheck(
                        layer="db",
                        type="schema_snapshot",
                        description="Snapshot table names, columns, column types, and schema hashes.",
                        target=self._mask_db_url(run.target_db_url),
                        assertions={},
                    ),
                    PlannedCheck(
                        layer="db",
                        type="row_count_snapshot",
                        description="Track row counts to detect insertions, deletions, and unexpected state changes.",
                        target=self._mask_db_url(run.target_db_url),
                        assertions={},
                    ),
                ]
            )
        else:
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

    def _ensure_diff_check(self, checklist: VerificationChecklist, run: ProofRun) -> VerificationChecklist:
        if any(check.layer == "diff" for check in checklist.checks):
            return checklist

        checklist.checks.insert(
            0,
            PlannedCheck(
                layer="diff",
                type="changed_files_detected",
                description="Inspect changed files to ground the generated verification checklist.",
                target=run.repo_path,
            ),
        )
        return checklist

    def from_changed_files(self, changed_files: list[str]) -> list[str]:
        return recommended_layers(summarize_categories(changed_files))

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

    def _mask_db_url(self, db_url: str) -> str:
        if "@" not in db_url:
            return db_url

        scheme, rest = db_url.split("://", 1) if "://" in db_url else ("", db_url)
        location = rest.split("@", 1)[1]
        return f"{scheme}://***@{location}" if scheme else f"***@{location}"

    def _url_path_hint(self, url: str) -> str:
        if "://" not in url:
            return url
        return "/" + url.split("://", 1)[1].split("/", 1)[1] if "/" in url.split("://", 1)[1] else ""

    def _metadata_string(self, run: ProofRun, key: str) -> str | None:
        value = run.claim_source.metadata.get(key) if run.claim_source else None
        return value if isinstance(value, str) else None
