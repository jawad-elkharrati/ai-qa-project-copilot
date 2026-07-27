from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app import models as db_models
from app.dataset import load_dataset
from app.ingestion import ingest_dataset
from app.main import app
from app.models import Build, Metric, PullRequest, Risk, RiskEvidence

client = TestClient(app)


def load_demo(db_session) -> None:
    dataset = load_dataset("data/demo_dataset_v0.1.json")
    ingest_dataset(db_session, dataset, "json", "test-fixture")


def analyze_critical():
    return client.post(
        "/risks/analyze",
        params={
            "project_id": "PRJ-COPILOTE",
            "sprint_id": "SPR-003",
            "as_of": "2026-07-13",
        },
    )


def test_pipeline_explanation_returns_and_persists_a_readable_evidence_chain(
    db_session,
) -> None:
    load_demo(db_session)
    analysis = analyze_critical().json()
    pipeline = next(
        item for item in analysis["findings"] if item["rule_id"] == "QA-PIPELINE-FAILED"
    )

    response = client.get(f"/risks/{pipeline['id']}/explanation")
    payload = response.json()
    node_types = {node["type"] for node in payload["evidence_chain"]["nodes"]}
    relations = {edge["relation"] for edge in payload["evidence_chain"]["edges"]}
    persisted = list(
        db_session.scalars(
            select(RiskEvidence)
            .where(RiskEvidence.risk_id == pipeline["id"])
            .order_by(RiskEvidence.evidence_order)
        )
    )

    assert response.status_code == 200
    assert {
        "risk",
        "ticket",
        "pull_request",
        "commit",
        "build",
        "test_result",
    } <= node_types
    assert {"supports", "implemented_by", "triggered", "contains"} <= relations
    assert payload["evidence_chain"]["missing_links"] == []
    assert payload["score_contribution"] == 25.0
    assert persisted
    assert persisted[0].source_type == "build"
    assert persisted[0].contribution == 25.0
    assert payload["human_validation_required"] is True


def test_missing_coverage_lowers_confidence_and_is_reported(db_session) -> None:
    load_demo(db_session)
    db_session.execute(
        delete(Metric).where(
            Metric.sprint_id == "SPR-003",
            Metric.name == "test_coverage",
        )
    )
    db_session.commit()

    result = analyze_critical().json()
    missing_codes = {item["code"] for item in result["missing_information"]}

    assert result["score"] == 75.3
    assert result["confidence_score"] == 0.75
    assert result["evidence_coverage"] == 0.88
    assert "coverage_metric_missing" in missing_codes
    assert result["confidence_details"]["is_probability"] is False
    assert result["confidence_details"]["method"] == "deterministic-data-coverage-v1"


def test_missing_test_result_is_visible_in_confidence_and_evidence_chain(
    db_session,
) -> None:
    load_demo(db_session)
    db_session.execute(
        delete(db_models.TestResult).where(db_models.TestResult.build_id == "BLD-012")
    )
    db_session.commit()

    analysis = analyze_critical().json()
    pipeline = next(
        item for item in analysis["findings"] if item["rule_id"] == "QA-PIPELINE-FAILED"
    )
    explanation = client.get(f"/risks/{pipeline['id']}/explanation").json()
    missing_codes = {item["code"] for item in analysis["missing_information"]}

    assert analysis["confidence_score"] < 1.0
    assert "test_results_incomplete" in missing_codes
    assert {link["relation"] for link in explanation["evidence_chain"]["missing_links"]} == {
        "build_to_test_result"
    }


def test_stale_build_and_coverage_sources_are_reported(db_session) -> None:
    load_demo(db_session)
    old = datetime(2026, 6, 1, 8, tzinfo=UTC)
    for build in db_session.scalars(select(Build).where(Build.sprint_id == "SPR-003")):
        build.started_at = old
        build.finished_at = old
    metric = db_session.scalar(
        select(Metric).where(
            Metric.sprint_id == "SPR-003",
            Metric.name == "test_coverage",
        )
    )
    metric.measured_at = old
    db_session.commit()

    result = analyze_critical().json()
    stale_codes = {item["code"] for item in result["stale_information"]}

    assert result["confidence_score"] == 0.8
    assert stale_codes == {"builds_stale", "coverage_metric_stale"}


def test_missing_pull_request_is_reported_without_crashing(db_session) -> None:
    load_demo(db_session)
    build = db_session.get(Build, "BLD-012")
    build.pull_request_id = None
    db_session.commit()

    analysis = analyze_critical().json()
    pipeline = next(
        item for item in analysis["findings"] if item["rule_id"] == "QA-PIPELINE-FAILED"
    )
    chain = client.get(f"/risks/{pipeline['id']}/explanation").json()["evidence_chain"]
    assert {(item["relation"], item["target_id"]) for item in chain["missing_links"]} >= {
        ("build_to_pull_request", "missing")
    }


def test_missing_ticket_relation_is_reported_without_crashing(db_session) -> None:
    load_demo(db_session)
    pull_request = db_session.get(PullRequest, "PR-012")
    pull_request.ticket_id = None
    db_session.commit()

    analysis = analyze_critical().json()
    pipeline = next(
        item for item in analysis["findings"] if item["rule_id"] == "QA-PIPELINE-FAILED"
    )
    chain = client.get(f"/risks/{pipeline['id']}/explanation").json()["evidence_chain"]
    assert {(item["relation"], item["target_id"]) for item in chain["missing_links"]} >= {
        ("pull_request_to_ticket", "missing")
    }


def test_unsupported_evidence_source_is_explicit(db_session) -> None:
    load_demo(db_session)
    analysis = analyze_critical().json()
    risk_id = analysis["findings"][0]["id"]
    risk = db_session.get(Risk, risk_id)
    risk.source_type = "deployment"
    db_session.commit()

    chain = client.get(f"/risks/{risk_id}/explanation").json()["evidence_chain"]
    assert chain["missing_links"] == [
        {
            "relation": "unsupported_source_type",
            "source_id": risk_id,
            "target_id": "deployment",
        }
    ]
