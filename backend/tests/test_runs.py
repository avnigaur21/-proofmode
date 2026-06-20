import sqlite3
import subprocess

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_run_returns_structured_report() -> None:
    response = client.post("/runs", json={"claim": "Add login page"})

    assert response.status_code == 200
    body = response.json()
    assert body["claim"] == "Add login page"
    assert body["status"] == "uncertain"
    assert len(body["checklist"]["checks"]) >= 2
    assert len(body["checks"]) == 4


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
