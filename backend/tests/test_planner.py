import subprocess
from pathlib import Path
from typing import Any

from app.schemas.runs import ProofRun
from app.services.git_diff_context import GitDiffContext, GitDiffContextService
from app.services.llm_planner import LlmVerificationPlanner
from app.services.llm_provider import OpenAiPlannerProvider
from app.services.planner import VerificationPlanner


class FakeProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def generate_checklist(self, claim: str, diff_context: GitDiffContext | None) -> dict[str, Any]:
        assert diff_context is not None
        assert diff_context.changed_files[0].patch
        return {
            "checks": [
                {
                    "layer": "api",
                    "type": "endpoint_contract",
                    "description": "Verify POST /auth/login still returns 200 and includes a token.",
                    "target": "POST /auth/login",
                }
            ],
            "affected_files_hint": [diff_context.changed_files[0].path],
        }


class InvalidProvider:
    provider_name = "invalid"
    model_name = "invalid-model"

    def generate_checklist(self, claim: str, diff_context: GitDiffContext | None) -> dict[str, Any]:
        return {"checks": [{"layer": "not-a-layer", "type": "bad", "description": "bad"}]}


class ErrorProvider:
    provider_name = "error"
    model_name = "error-model"

    def generate_checklist(self, claim: str, diff_context: GitDiffContext | None) -> dict[str, Any]:
        raise RuntimeError("provider unavailable")


class FakeHttpResponse:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._data


class FakeHttpClient:
    def __init__(self) -> None:
        self.request_json: dict[str, Any] | None = None

    def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> FakeHttpResponse:
        self.request_json = json
        return FakeHttpResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"checks":[{"layer":"api","type":"endpoint_contract",'
                                '"description":"Verify login still returns a token.",'
                                '"target":"POST /auth/login"}],'
                                '"affected_files_hint":["backend/app/routers/auth.py"]}'
                            )
                        }
                    }
                ]
            }
        )


def test_llm_planner_uses_git_diff_context_for_specific_checks(tmp_path: Path) -> None:
    repo_path = _repo_with_auth_change(tmp_path)
    planner = VerificationPlanner(
        mode="llm",
        llm_planner=LlmVerificationPlanner(FakeProvider()),
    )

    checklist = planner.create_checklist(
        ProofRun(
            claim="Agent updated login endpoint",
            repo_path=str(repo_path),
        )
    )

    assert checklist.planner.source == "llm"
    assert checklist.planner.provider == "fake"
    assert checklist.planner.used_fallback is False
    assert checklist.planner.diff_files_used == 1
    assert any(check.type == "endpoint_contract" for check in checklist.checks)
    assert checklist.affected_files_hint == ["backend/app/routers/auth.py"]


def test_llm_planner_falls_back_when_provider_output_is_invalid(tmp_path: Path) -> None:
    repo_path = _repo_with_auth_change(tmp_path)
    planner = VerificationPlanner(
        mode="llm",
        llm_planner=LlmVerificationPlanner(InvalidProvider()),
    )

    checklist = planner.create_checklist(
        ProofRun(
            claim="Agent updated login endpoint",
            repo_path=str(repo_path),
            api_base_url="http://localhost:8000/health",
        )
    )

    assert checklist.planner.source == "deterministic_fallback"
    assert checklist.planner.used_fallback is True
    assert checklist.planner.reason == "llm_output_invalid"
    assert any(check.type == "api_health_reachable" for check in checklist.checks)


def test_llm_planner_falls_back_when_provider_raises(tmp_path: Path) -> None:
    repo_path = _repo_with_auth_change(tmp_path)
    planner = VerificationPlanner(
        mode="llm",
        llm_planner=LlmVerificationPlanner(ErrorProvider()),
    )

    checklist = planner.create_checklist(
        ProofRun(
            claim="Agent updated login endpoint",
            repo_path=str(repo_path),
            api_base_url="http://localhost:8000/health",
        )
    )

    assert checklist.planner.source == "deterministic_fallback"
    assert checklist.planner.provider == "error"
    assert checklist.planner.reason == "llm_provider_error"
    assert any(check.type == "api_health_reachable" for check in checklist.checks)


def test_openai_provider_builds_structured_output_request(tmp_path: Path) -> None:
    repo_path = _repo_with_auth_change(tmp_path)
    diff_context = GitDiffContextService().build(str(repo_path))
    fake_client = FakeHttpClient()
    provider = OpenAiPlannerProvider(
        api_key="test-key",
        model_name="test-model",
        base_url="https://example.test/v1",
        http_client=fake_client,  # type: ignore[arg-type]
    )

    response = provider.generate_checklist("Agent updated login endpoint", diff_context)

    assert response["checks"][0]["target"] == "POST /auth/login"
    assert fake_client.request_json is not None
    assert fake_client.request_json["model"] == "test-model"
    assert fake_client.request_json["response_format"]["type"] == "json_schema"
    assert "backend/app/routers/auth.py" in fake_client.request_json["messages"][1]["content"]


def _repo_with_auth_change(tmp_path: Path) -> Path:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _git(repo_path, "init")
    _git(repo_path, "config", "user.name", "ProofMode Test")
    _git(repo_path, "config", "user.email", "proofmode@example.com")

    auth_file = repo_path / "backend" / "app" / "routers" / "auth.py"
    auth_file.parent.mkdir(parents=True)
    auth_file.write_text("def login():\n    return {'token': 'old'}\n", encoding="utf-8")
    _git(repo_path, "add", ".")
    _git(repo_path, "commit", "-m", "initial auth")

    auth_file.write_text(
        "def login():\n    return {'token': 'new', 'expires_in': 3600}\n",
        encoding="utf-8",
    )
    return repo_path


def _git(repo_path: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_path, check=True, capture_output=True)
