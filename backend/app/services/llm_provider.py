from typing import Any, Protocol

from app.services.git_diff_context import GitDiffContext


class LlmPlannerProvider(Protocol):
    provider_name: str
    model_name: str | None

    def generate_checklist(self, claim: str, diff_context: GitDiffContext | None) -> dict[str, Any]:
        ...


class HeuristicLlmPlannerProvider:
    provider_name = "heuristic"
    model_name = "local-diff-heuristic-v1"

    def generate_checklist(self, claim: str, diff_context: GitDiffContext | None) -> dict[str, Any]:
        checks: list[dict[str, str | None]] = []
        affected_files: list[str] = []

        if diff_context is None:
            return {"checks": checks, "affected_files_hint": affected_files}

        for changed_file in diff_context.changed_files:
            affected_files.append(changed_file.path)
            lower_path = changed_file.path.lower()
            patch = changed_file.patch.lower()

            if "ui" in changed_file.categories:
                checks.append(
                    {
                        "layer": "ui",
                        "type": "diff_targeted_ui_behavior",
                        "description": f"Verify the UI behavior affected by {changed_file.path} still renders and responds without browser errors.",
                        "target": changed_file.path,
                    }
                )

            if "api" in changed_file.categories:
                endpoint_hint = self._endpoint_hint(lower_path, patch)
                checks.append(
                    {
                        "layer": "api",
                        "type": "diff_targeted_api_contract",
                        "description": f"Verify {endpoint_hint} still returns the expected status and response shape after changes in {changed_file.path}.",
                        "target": endpoint_hint,
                    }
                )

            if "db" in changed_file.categories:
                checks.append(
                    {
                        "layer": "db",
                        "type": "diff_targeted_data_state",
                        "description": f"Verify schema and row-count expectations for the data changes in {changed_file.path}.",
                        "target": changed_file.path,
                    }
                )

            if "logic" in changed_file.categories and "api" not in changed_file.categories:
                checks.append(
                    {
                        "layer": "api",
                        "type": "shared_logic_regression",
                        "description": f"Exercise API paths that depend on shared logic changed in {changed_file.path}.",
                        "target": changed_file.path,
                    }
                )

        if not checks:
            checks.append(
                {
                    "layer": "diff",
                    "type": "manual_diff_review",
                    "description": "Review the changed files because no specific UI, API, or DB layer was confidently inferred.",
                    "target": None,
                }
            )

        return {
            "checks": self._dedupe_checks(checks),
            "affected_files_hint": affected_files[:10],
        }

    def _endpoint_hint(self, path: str, patch: str) -> str:
        if "auth" in path or "login" in path or "login" in patch:
            return "authentication endpoint"
        if "user" in path or "profile" in patch:
            return "user/profile endpoint"
        if "project" in path:
            return "project endpoint"
        return "changed API endpoint"

    def _dedupe_checks(self, checks: list[dict[str, str | None]]) -> list[dict[str, str | None]]:
        seen: set[tuple[str | None, str | None, str | None]] = set()
        deduped: list[dict[str, str | None]] = []
        for check in checks:
            key = (check.get("layer"), check.get("type"), check.get("target"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(check)
        return deduped
