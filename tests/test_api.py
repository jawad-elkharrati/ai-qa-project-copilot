from fastapi.testclient import TestClient

from app import main
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


def test_openapi_documents_health_and_explainable_risk_contracts() -> None:
    response = client.get("/openapi.json")
    schema = response.json()

    assert response.status_code == 200
    assert {
        "/health",
        "/risks",
        "/risks/{risk_id}",
        "/risks/{risk_id}/explanation",
        "/risks/{risk_id}/decisions",
        "/projects/{project_id}/risk-summary",
        "/projects/{project_id}/risk-history",
    } <= set(schema["paths"])
    assert (
        schema["paths"]["/risks/{risk_id}/explanation"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        == "#/components/schemas/RiskExplanationResponse"
    )


def test_health_returns_503_when_database_is_unavailable(monkeypatch) -> None:
    def unavailable():
        raise OSError("database unavailable")

    monkeypatch.setattr(main.engine, "connect", unavailable)
    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "status": "unhealthy",
        "database": "unavailable",
    }
