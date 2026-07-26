from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.dataset import load_dataset
from app.ingestion import ingest_dataset
from app.main import app
from app.models import Risk, RiskAnalysis

client = TestClient(app)


def load_demo(db_session) -> None:
    dataset = load_dataset("data/demo_dataset_v0.1.json")
    ingest_dataset(db_session, dataset, "json", "test-fixture")


def analyze(sprint_id: str):
    return client.post(
        "/risks/analyze",
        params={
            "project_id": "PRJ-COPILOTE",
            "sprint_id": sprint_id,
            "as_of": "2026-07-13",
        },
    )


def test_agent_detects_all_nine_oracle_anomalies_across_three_scenarios(db_session) -> None:
    load_demo(db_session)
    results = {sprint: analyze(sprint).json() for sprint in ("SPR-001", "SPR-002", "SPR-003")}

    assert results["SPR-001"]["findings"] == []
    assert {item["source_id"] for item in results["SPR-002"]["findings"]} == {
        "TKT-024",
        "TKT-027",
        "TKT-029",
    }
    assert {item["source_id"] for item in results["SPR-003"]["findings"]} == {
        "TKT-038",
        "TKT-039",
        "TKT-042",
        "TKT-045",
        "BLD-012",
        "MET-007",
    }
    assert [results[sprint]["severity"] for sprint in results] == ["low", "medium", "critical"]


def test_risk_endpoint_returns_score_proof_actions_and_human_control(db_session) -> None:
    load_demo(db_session)
    response = analyze("SPR-003")
    payload = response.json()

    assert response.status_code == 200
    assert payload["agent"] == "qa-agent-v1"
    assert payload["ruleset_version"] == "qa-rules-v1.0"
    assert payload["finding_count"] == 6
    assert payload["score"] == 83.3
    assert payload["human_validation_required"] is True
    assert round(sum(item["contribution"] for item in payload["score_breakdown"]), 1) == 83.3
    assert all(item["evidence"] for item in payload["findings"])
    assert all(item["recommendation"] for item in payload["findings"])
    assert all(item["requires_human_validation"] for item in payload["findings"])

    critical = client.get(
        "/risks",
        params={
            "project_id": "PRJ-COPILOTE",
            "sprint_id": "SPR-003",
            "severity": "critical",
        },
    ).json()
    assert critical["returned_findings"] == 3
    assert {item["source_id"] for item in critical["findings"]} == {
        "TKT-038",
        "TKT-039",
        "BLD-012",
    }


def test_repeating_same_analysis_is_idempotent(db_session) -> None:
    load_demo(db_session)
    first = analyze("SPR-003").json()
    second = analyze("SPR-003").json()

    assert first["analysis_id"] == second["analysis_id"]
    assert db_session.scalar(select(func.count()).select_from(RiskAnalysis)) == 1
    assert db_session.scalar(select(func.count()).select_from(Risk)) == 6


def test_unknown_scope_and_missing_analysis_return_controlled_404(db_session) -> None:
    load_demo(db_session)
    missing = client.get("/risks", params={"project_id": "PRJ-COPILOTE", "sprint_id": "SPR-003"})
    unknown = client.post("/risks/analyze", params={"project_id": "UNKNOWN"})

    assert missing.status_code == 404
    assert "run POST /risks/analyze" in missing.json()["detail"]
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "project not found"
