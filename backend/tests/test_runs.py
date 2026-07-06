import sqlite3
import subprocess

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.runs import CheckStatus, PlannedCheck, ProofCheck, ProofRun, VerificationChecklist
from app.services.evidence_evaluator import EvidenceEvaluator
from app.services.run_service import RunService
from app.verifiers.db_verifier import DbVerifier


client = TestClient(app)


def test_create_run_returns_structured_report(tmp_path) -> None:
    repo_path = _empty_repo(tmp_path)
    response = client.post("/runs", json=_diff_only_payload("Add login page", repo_path))

    assert response.status_code == 200
    body = response.json()
    assert body["claim"] == "Add login page"
    assert body["status"] == "passed"
    assert body["evaluation"]["verdict"] == "supported"
    assert body["evaluation"]["confidence"] > 0
    assert len(body["evaluation"]["rubrics"]) >= 6
    assert {check["layer"] for check in body["checklist"]["checks"]} == {"diff"}
    assert len(body["checks"]) == 1
    assert len(body["timeline"]) >= 8
    assert body["timeline"][0]["type"] == "run.created"
    assert body["timeline"][-1]["type"] == "run.completed"
    assert body["report_url"].startswith("/artifacts/reports/")

    report_response = client.get(body["report_url"])
    assert report_response.status_code == 200
    assert "ProofMode Report" in report_response.text

    reloaded_service = RunService()
    reloaded_run = reloaded_service.get_run(body["id"])
    assert reloaded_run is not None
    assert reloaded_run.claim == "Add login page"
    assert reloaded_run.report_url == body["report_url"]
    assert reloaded_run.evaluation is not None
    assert reloaded_run.evaluation.verdict == "supported"
    assert reloaded_run.timeline[-1].type == "run.completed"


def test_evidence_evaluator_contradicts_deterministic_failures(tmp_path) -> None:
    repo_path = tmp_path / "not-a-git-repo"
    repo_path.mkdir()

    response = client.post("/runs", json=_diff_only_payload("Claim with invalid repo evidence", repo_path))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["evaluation"]["verdict"] == "contradicted"
    assert len(body["evaluation"]["rubrics"]) >= 6
    assert "cannot be overridden" in " ".join(body["evaluation"]["guardrails"])
    assert "evaluator.completed" in [event["type"] for event in body["timeline"]]


def test_llm_evidence_evaluator_can_downgrade_clean_evidence() -> None:
    run = ProofRun(
        claim="Agent says checkout is complete",
        checks=[
            ProofCheck(
                layer="diff",
                status=CheckStatus.PASSED,
                summary="Git diff review passed.",
            )
        ],
    )

    evaluation = EvidenceEvaluator(mode="llm", provider=_StrictEvaluatorProvider()).evaluate(run)

    assert evaluation.verdict == "insufficient"
    assert evaluation.evaluator_mode == "llm"
    assert evaluation.provider == "fake-strict"
    assert "Deterministic verifier failures cannot be overridden" in " ".join(evaluation.guardrails)


def test_llm_evidence_evaluator_falls_back_on_invalid_output() -> None:
    run = ProofRun(
        claim="Agent says checkout is complete",
        checks=[
            ProofCheck(
                layer="diff",
                status=CheckStatus.PASSED,
                summary="Git diff review passed.",
            )
        ],
    )

    evaluation = EvidenceEvaluator(mode="llm", provider=_BrokenEvaluatorProvider()).evaluate(run)

    assert evaluation.verdict == "supported"
    assert evaluation.evaluator_mode == "deterministic_fallback"
    assert "deterministic evaluation was used" in " ".join(evaluation.guardrails)


def test_create_run_rejects_incomplete_enabled_layers() -> None:
    response = client.post("/runs", json={"claim": "Bare claim should not run"})

    assert response.status_code == 422
    errors = response.json()["detail"]
    message = str(errors)
    assert "target_url is required when UI verification is enabled" in message
    assert "api_base_url is required when API verification is enabled" in message
    assert "target_db_url is required when database verification is enabled" in message
    assert "repo_path is required when Git diff analysis is enabled" in message


def test_create_run_rejects_when_all_automated_checks_are_disabled() -> None:
    response = client.post(
        "/runs",
        json={
            "claim": "Nothing automated selected",
            "run_config": {
                "ui_enabled": False,
                "api_enabled": False,
                "db_enabled": False,
                "diff_enabled": False,
                "planner_enabled": True,
                "approval_required": True,
            },
        },
    )

    assert response.status_code == 422
    assert "at least one automated proof check must be enabled" in str(response.json()["detail"])


def test_artifact_routes_reject_path_traversal() -> None:
    response = client.get("/artifacts/reports/..%2FREADME.md")
    assert response.status_code == 404


def test_settings_status_exposes_runtime_configuration() -> None:
    response = client.get("/settings/status")

    assert response.status_code == 200
    body = response.json()
    assert body["backend_status"] == "online"
    assert body["planner_mode"] in {"deterministic", "llm"}
    assert body["evaluator_mode"] in {"deterministic", "llm"}
    assert body["llm_provider"] in {"heuristic", "openai"}
    assert isinstance(body["openai_api_key_configured"], bool)
    assert body["run_persistence_enabled"] is True
    assert body["runs_directory"].endswith("runs")


def test_project_profiles_can_be_created_listed_updated_and_deleted() -> None:
    create_response = client.post(
        "/projects",
        json={
            "name": "ProofMode workspace",
            "repo_path": "C:\\path\\to\\repo",
            "target_url": "http://localhost:5173",
            "api_base_url": "http://localhost:8000/health",
            "target_db_url": "sqlite:///./proofmode-runs/demo.db",
            "default_run_config": {
                "ui_enabled": True,
                "api_enabled": True,
                "db_enabled": False,
                "diff_enabled": True,
                "planner_enabled": True,
                "approval_required": False,
            },
        },
    )

    assert create_response.status_code == 200
    project = create_response.json()
    assert project["name"] == "ProofMode workspace"
    assert project["default_run_config"]["db_enabled"] is False

    list_response = client.get("/projects")
    assert list_response.status_code == 200
    assert any(item["id"] == project["id"] for item in list_response.json())

    update_response = client.patch(
        f"/projects/{project['id']}",
        json={
            "name": "ProofMode saved profile",
            "default_run_config": {
                "ui_enabled": False,
                "api_enabled": True,
                "db_enabled": True,
                "diff_enabled": True,
                "planner_enabled": False,
                "approval_required": True,
            },
        },
    )

    assert update_response.status_code == 200
    updated_project = update_response.json()
    assert updated_project["name"] == "ProofMode saved profile"
    assert updated_project["default_run_config"]["ui_enabled"] is False
    assert updated_project["default_run_config"]["planner_enabled"] is False

    delete_response = client.delete(f"/projects/{project['id']}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/projects/{project['id']}")
    assert missing_response.status_code == 404

    missing_delete_response = client.delete(f"/projects/{project['id']}")
    assert missing_delete_response.status_code == 404


def test_approval_gate_persists_human_decision(tmp_path) -> None:
    repo_path = _empty_repo(tmp_path)
    run_response = client.post("/runs", json=_diff_only_payload("Review approval gate", repo_path))
    assert run_response.status_code == 200
    run_id = run_response.json()["id"]

    approval_response = client.post(
        f"/runs/{run_id}/approval",
        json={
            "decision": "fix_requested",
            "reviewer": "Avni",
            "note": "Wire the button before calling it done.",
        },
    )

    assert approval_response.status_code == 200
    body = approval_response.json()
    assert body["approval"]["decision"] == "fix_requested"
    assert body["approval"]["reviewer"] == "Avni"
    assert body["approval"]["note"] == "Wire the button before calling it done."
    assert body["timeline"][-1]["type"] == "approval.fix_requested"

    reloaded_service = RunService()
    reloaded_run = reloaded_service.get_run(run_id)
    assert reloaded_run is not None
    assert reloaded_run.approval is not None
    assert reloaded_run.approval.decision == "fix_requested"


def test_run_configuration_skips_disabled_layers(tmp_path) -> None:
    repo_path = _empty_repo(tmp_path)
    response = client.post(
        "/runs",
        json={
            "claim": "Verify diff only",
            "repo_path": str(repo_path),
            "target_url": "http://localhost:5173",
            "api_base_url": "http://localhost:8000/health",
            "run_config": {
                "ui_enabled": False,
                "api_enabled": False,
                "db_enabled": False,
                "diff_enabled": True,
                "planner_enabled": True,
                "approval_required": False,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_config"]["ui_enabled"] is False
    assert body["run_config"]["diff_enabled"] is True
    assert body["run_config"]["approval_required"] is False
    assert [check["layer"] for check in body["checks"]] == ["diff"]
    assert {check["layer"] for check in body["checklist"]["checks"]} == {"diff"}
    assert "ui.skipped" in [event["type"] for event in body["timeline"]]
    assert "api.skipped" in [event["type"] for event in body["timeline"]]


def test_demo_seed_creates_walkthrough_runs() -> None:
    response = client.post("/demo/seed")

    assert response.status_code == 200
    body = response.json()
    assert [run["id"] for run in body] == [
        "demo-ghost-completion",
        "demo-contract-drift",
        "demo-state-blindness",
    ]
    assert all(run["status"] == "failed" for run in body)
    assert body[0]["timeline"][0]["type"] == "demo.seeded"
    assert body[1]["report_url"].startswith("/artifacts/reports/")

    report_response = client.get(body[2]["report_url"])
    assert report_response.status_code == 200
    assert "State blindness" in report_response.text or "database row" in report_response.text

    snapshot_response = client.get("/artifacts/snapshots/api/demo-contract-drift.json")
    assert snapshot_response.status_code == 200
    assert "user.email removed" in snapshot_response.text


def test_db_snapshot_tracks_sqlite_row_count_changes(tmp_path) -> None:
    db_path = tmp_path / "proofmode.db"
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL)")
    connection.execute("INSERT INTO users (email) VALUES ('first@example.com')")
    connection.commit()
    connection.close()

    payload = {
        "claim": "Verify database row state",
        "target_db_url": f"sqlite:///{db_path.as_posix()}",
        "run_config": {
            "ui_enabled": False,
            "api_enabled": False,
            "db_enabled": True,
            "diff_enabled": False,
            "planner_enabled": True,
            "approval_required": True,
        },
    }

    first_response = client.post("/runs", json=payload)
    assert first_response.status_code == 200
    first_db_check = _check_for_layer(first_response.json(), "db")
    assert first_db_check["status"] == "uncertain"
    assert first_db_check["evidence"]["tables_checked"] == 1

    connection = sqlite3.connect(db_path)
    connection.execute("INSERT INTO users (email) VALUES ('second@example.com')")
    connection.commit()
    connection.close()

    second_response = client.post("/runs", json=payload)
    assert second_response.status_code == 200
    second_db_check = _check_for_layer(second_response.json(), "db")
    assert second_db_check["status"] == "passed"
    assert second_db_check["evidence"]["issues"][0]["type"] == "row_count_changed"
    assert second_db_check["evidence"]["issues"][0]["delta"] == 1


def test_db_verifier_reports_targeted_table_and_column_assertions(tmp_path) -> None:
    db_path = tmp_path / "targeted.db"
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL)")
    connection.commit()
    connection.close()

    run = ProofRun(
        claim="Verify users table",
        target_db_url=f"sqlite:///{db_path.as_posix()}",
        checklist=VerificationChecklist(
            checks=[
                PlannedCheck(
                    layer="db",
                    type="table_column_exists",
                    description="Verify the users.email column exists.",
                    target="users",
                    assertions={"table": "users", "column": "email"},
                )
            ]
        ),
    )

    check = DbVerifier().verify(run)

    assert check.status == "uncertain"
    assert check.evidence["target_results"][0]["table_exists"] is True
    assert check.evidence["target_results"][0]["column_exists"] is True


def test_diff_verifier_classifies_changed_files(tmp_path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _git(repo_path, "init")
    _git(repo_path, "config", "user.name", "ProofMode Test")
    _git(repo_path, "config", "user.email", "proofmode@example.com")

    frontend_file = repo_path / "frontend" / "src" / "Login.tsx"
    frontend_file.parent.mkdir(parents=True)
    frontend_file.write_text("export function Login() { return null; }\n", encoding="utf-8")

    api_file = repo_path / "backend" / "app" / "routers" / "auth.py"
    api_file.parent.mkdir(parents=True)
    api_file.write_text("def route():\n    return {}\n", encoding="utf-8")

    migration_file = repo_path / "backend" / "migrations" / "001_add_user.sql"
    migration_file.parent.mkdir(parents=True)
    migration_file.write_text("CREATE TABLE users (id INTEGER);\n", encoding="utf-8")

    response = client.post(
        "/runs",
        json={
            "claim": "Verify changed login, auth API, and user migration",
            "repo_path": str(repo_path),
            "run_config": {
                "ui_enabled": False,
                "api_enabled": False,
                "db_enabled": False,
                "diff_enabled": True,
                "planner_enabled": True,
                "approval_required": True,
            },
        },
    )

    assert response.status_code == 200
    diff_check = _check_for_layer(response.json(), "diff")
    assert diff_check["status"] == "passed"
    assert diff_check["evidence"]["category_summary"]["ui"] == 1
    assert diff_check["evidence"]["category_summary"]["api"] == 1
    assert diff_check["evidence"]["category_summary"]["db"] == 1
    assert diff_check["evidence"]["recommended_layers"] == ["ui", "api", "db"]


def _check_for_layer(run: dict, layer: str) -> dict:
    return next(check for check in run["checks"] if check["layer"] == layer)


def _diff_only_payload(claim: str, repo_path) -> dict:
    return {
        "claim": claim,
        "repo_path": str(repo_path),
        "run_config": {
            "ui_enabled": False,
            "api_enabled": False,
            "db_enabled": False,
            "diff_enabled": True,
            "planner_enabled": True,
            "approval_required": True,
        },
    }


def _empty_repo(tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _git(repo_path, "init")
    _git(repo_path, "config", "user.name", "ProofMode Test")
    _git(repo_path, "config", "user.email", "proofmode@example.com")
    return repo_path


def _git(repo_path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_path, check=True, capture_output=True)


class _StrictEvaluatorProvider:
    provider_name = "fake-strict"
    model_name = "fake-evaluator"

    def evaluate(self, run: ProofRun) -> dict:
        return {
            "verdict": "insufficient",
            "confidence": 0.61,
            "explanation": "The claim needs stronger evidence than the executed diff check.",
            "reasons": ["Only Git diff evidence was available."],
            "guardrails": ["LLM evaluator cannot execute missing checks."],
            "rubrics": [
                {
                    "name": "claim_coverage",
                    "score": 0.42,
                    "label": "Partial",
                    "explanation": "Only diff evidence was available.",
                }
            ],
        }


class _BrokenEvaluatorProvider:
    provider_name = "fake-broken"
    model_name = "fake-evaluator"

    def evaluate(self, run: ProofRun) -> dict:
        return {"verdict": "definitely maybe"}
