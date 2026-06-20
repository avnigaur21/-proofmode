import sqlite3

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


def _check_for_layer(run: dict, layer: str) -> dict:
    return next(check for check in run["checks"] if check["layer"] == layer)
