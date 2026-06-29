import json
import os
from typing import Any, Protocol

import httpx

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
                        "assertions": {},
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
                        "assertions": {
                            "method": "GET",
                            "path": self._path_hint(endpoint_hint),
                            "expected_status": 200,
                        },
                    }
                )

            if "db" in changed_file.categories:
                checks.append(
                    {
                        "layer": "db",
                        "type": "diff_targeted_data_state",
                        "description": f"Verify schema and row-count expectations for the data changes in {changed_file.path}.",
                        "target": changed_file.path,
                        "assertions": self._db_assertions(changed_file.path),
                    }
                )

            if "logic" in changed_file.categories and "api" not in changed_file.categories:
                checks.append(
                    {
                        "layer": "api",
                        "type": "shared_logic_regression",
                        "description": f"Exercise API paths that depend on shared logic changed in {changed_file.path}.",
                        "target": changed_file.path,
                        "assertions": {},
                    }
                )

        if not checks:
            checks.append(
                {
                    "layer": "diff",
                    "type": "manual_diff_review",
                    "description": "Review the changed files because no specific UI, API, or DB layer was confidently inferred.",
                    "target": None,
                    "assertions": {},
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

    def _path_hint(self, endpoint_hint: str) -> str:
        if "authentication" in endpoint_hint:
            return "/auth/login"
        if "user/profile" in endpoint_hint:
            return "/api/user/profile"
        if "project" in endpoint_hint:
            return "/api/projects"
        return ""

    def _db_assertions(self, path: str) -> dict[str, object]:
        normalized = path.lower()
        if "user" in normalized:
            return {"table": "users"}
        if "project" in normalized:
            return {"table": "projects"}
        return {}

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


class OpenAiPlannerProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
        base_url: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model_name or os.getenv("PROOFMODE_LLM_MODEL", "gpt-4.1-mini")
        self._base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self._http_client = http_client or httpx.Client(timeout=30)

    def generate_checklist(self, claim: str, diff_context: GitDiffContext | None) -> dict[str, Any]:
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY is required when PROOFMODE_LLM_PROVIDER=openai.")

        response = self._http_client.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=self._request_payload(claim, diff_context),
        )
        response.raise_for_status()
        return self._parse_response(response.json())

    def _request_payload(self, claim: str, diff_context: GitDiffContext | None) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are ProofMode's verification planner. Generate a concise checklist of "
                        "specific checks needed to verify an AI coding agent's completion claim. "
                        "Use only these layers: ui, api, db, diff. Do not invent precise endpoints "
                        "unless the diff strongly implies them. Return JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "claim": claim,
                            "diff_context": diff_context.model_dump(mode="json") if diff_context else None,
                        "required_output": {
                            "checks": [
                                {
                                    "layer": "ui | api | db | diff",
                                    "type": "short_snake_case_check_type",
                                    "description": "human-readable verification instruction",
                                    "target": "specific endpoint, selector, table, file, or null",
                                    "assertions": {
                                        "method": "GET",
                                        "path": "/health",
                                        "expected_status": 200,
                                        "required_fields": ["status"],
                                        "selector": "[data-testid='submit']",
                                        "text": "Login",
                                        "table": "users",
                                        "column": "email",
                                        "expected_row_delta": 1,
                                    },
                                }
                            ],
                            "affected_files_hint": ["changed/file/path.py"],
                        },
                        },
                        indent=2,
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "proofmode_verification_checklist",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "checks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "layer": {"type": "string", "enum": ["ui", "api", "db", "diff"]},
                                        "type": {"type": "string"},
                                        "description": {"type": "string"},
                                        "target": {"type": ["string", "null"]},
                                        "assertions": {
                                            "type": "object",
                                            "additionalProperties": {
                                                "anyOf": [
                                                    {"type": "string"},
                                                    {"type": "number"},
                                                    {"type": "boolean"},
                                                    {"type": "null"},
                                                    {
                                                        "type": "array",
                                                        "items": {"type": "string"},
                                                    },
                                                ]
                                            },
                                        },
                                    },
                                    "required": ["layer", "type", "description", "target", "assertions"],
                                },
                            },
                            "affected_files_hint": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["checks", "affected_files_hint"],
                    },
                },
            },
        }

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            message = data["choices"][0]["message"]
            content = message["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("OpenAI planner response did not include message content.") from error

        if not isinstance(content, str) or not content.strip():
            raise ValueError("OpenAI planner response content was empty.")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError("OpenAI planner response was not valid JSON.") from error

        if not isinstance(parsed, dict):
            raise ValueError("OpenAI planner response JSON must be an object.")

        return parsed


def create_llm_planner_provider() -> LlmPlannerProvider:
    provider = os.getenv("PROOFMODE_LLM_PROVIDER", "heuristic").lower()
    if provider == "openai":
        return OpenAiPlannerProvider()
    return HeuristicLlmPlannerProvider()
