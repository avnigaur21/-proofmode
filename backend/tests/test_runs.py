import sqlite3
import subprocess

from fastapi.testclient import TestClient

from app.main import app
from app.services.run_service import RunService


client = TestClient(app)


def test_create_run_returns_structured_report() -> None:
    response = client.post("/runs", json={"claim": "Add login page"})

    assert response.status_code == 200
    body = response.json()
    assert body["claim"] == "Add login page"
    assert body["status"] == "uncertain"
    assert len(body["checklist"]["checks"]) >= 2
    assert len(body["checks"]) == 4
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
    assert reloaded_run.timeline[-1].type == "run.completed"


def test_artifact_routes_reject_path_traversal() -> None:
    response = client.get("/artifacts/reports/..%2FREADME.md")
    assert response.status_code == 404


def test_approval_gate_persists_human_decision() -> None:
    run_response = client.post("/runs", json={"claim": "Review approval gate"})
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


def _git(repo_path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_path, check=True, capture_output=True)
