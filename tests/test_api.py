from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_exposes_discovery_links() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["health"] == "/health"
    assert response.json()["documentation"] == "/docs"


def test_health_checks_database() -> None:
    response = client.get("/health")
    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "healthy"
    assert payload["environment"] == "test"
    assert payload["database"] == {"status": "reachable", "backend": "sqlite"}
    assert payload["timestamp"].endswith("+00:00")


def test_openapi_contains_health_route() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/health" in response.json()["paths"]

