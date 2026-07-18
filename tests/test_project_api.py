from fastapi.testclient import TestClient

from app.dataset import load_dataset
from app.ingestion import ingest_dataset
from app.main import app

client = TestClient(app)


def load_demo(db_session) -> None:
    dataset = load_dataset("data/demo_dataset_v0.1.json")
    ingest_dataset(db_session, dataset, "json", "test-fixture")


def test_projects_and_sprints_are_exposed(db_session) -> None:
    load_demo(db_session)
    projects = client.get("/projects")
    sprints = client.get("/sprints", params={"project_id": "PRJ-COPILOTE"})
    assert projects.status_code == 200
    assert projects.json()[0]["key"] == "COPQA"
    assert sprints.status_code == 200
    assert len(sprints.json()) == 3


def test_critical_sprint_kpis_match_reference_dataset(db_session) -> None:
    load_demo(db_session)
    response = client.get(
        "/overview",
        params={
            "project_id": "PRJ-COPILOTE",
            "sprint_id": "SPR-003",
            "as_of": "2026-07-13",
        },
    )
    assert response.status_code == 200
    overview = response.json()
    assert overview["total_tickets"] == 17
    assert overview["blocked_tickets"] == 1
    assert overview["overdue_tickets"] == 2
    assert overview["failed_builds"] == 2
    assert overview["test_coverage"] == 54.0


def test_ticket_and_metric_filters(db_session) -> None:
    load_demo(db_session)
    tickets = client.get(
        "/tickets",
        params={"project_id": "PRJ-COPILOTE", "sprint_id": "SPR-003", "priority": "critical"},
    )
    metrics = client.get(
        "/metrics",
        params={"project_id": "PRJ-COPILOTE", "sprint_id": "SPR-003", "name": "test_coverage"},
    )
    assert [ticket["id"] for ticket in tickets.json()] == ["TKT-038"]
    assert metrics.json()[0]["value"] == 54.0


def test_unknown_project_returns_404(db_session) -> None:
    response = client.get("/overview", params={"project_id": "UNKNOWN"})
    assert response.status_code == 404
