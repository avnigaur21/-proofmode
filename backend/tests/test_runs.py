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
