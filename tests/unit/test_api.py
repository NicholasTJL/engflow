from fastapi.testclient import TestClient

from engflow.api.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_validate_valid_workflow_returns_order() -> None:
    payload = {
        "name": "demo",
        "steps": [
            {"id": "a", "uses": "command", "command": "echo a"},
            {"id": "b", "uses": "command", "command": "echo b", "depends_on": ["a"]},
        ],
    }

    response = client.post("/validate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["order"] == ["a", "b"]


def test_validate_cycle_returns_error() -> None:
    payload = {
        "name": "demo",
        "steps": [
            {"id": "a", "uses": "command", "command": "echo a", "depends_on": ["b"]},
            {"id": "b", "uses": "command", "command": "echo b", "depends_on": ["a"]},
        ],
    }

    response = client.post("/validate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["error"] is not None
    assert "cycle" in body["error"]


def test_validate_duplicate_ids_returns_normalized_error() -> None:
    payload = {
        "name": "demo",
        "steps": [
            {"id": "a", "uses": "command", "command": "echo a"},
            {"id": "a", "uses": "command", "command": "echo b"},
        ],
    }

    response = client.post("/validate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["error"] is not None
    assert "duplicate" in body["error"].lower()
