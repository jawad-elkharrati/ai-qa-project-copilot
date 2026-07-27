import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.dataset import load_dataset
from app.ingestion import ingest_dataset
from app.main import app
from app.models import Build, IngestionLog, RiskAnalysis, RiskContribution
from app.qa_agent import QAAgent
from app.risk_snapshot_service import SnapshotConsistencyError
from app.seed import seed_dataset

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


def test_identical_analysis_reuses_immutable_snapshot_and_contributions(
    db_session,
) -> None:
    load_demo(db_session)

    first = analyze_critical().json()
    second = analyze_critical().json()

    assert first["snapshot_created"] is True
    assert second["snapshot_created"] is False
    assert first["snapshot_id"] == second["snapshot_id"]
    assert first["input_fingerprint"] == second["input_fingerprint"]
    assert len(first["contributions"]) == 5
    assert db_session.scalar(select(func.count()).select_from(RiskAnalysis)) == 1
    assert db_session.scalar(select(func.count()).select_from(RiskContribution)) == 5


def test_changed_input_creates_snapshot_and_explains_negative_delta(db_session) -> None:
    load_demo(db_session)
    first = analyze_critical().json()
    build = db_session.get(Build, "BLD-012")
    build.status = "success"
    db_session.commit()

    second = analyze_critical().json()
    summary = client.get(
        "/projects/PRJ-COPILOTE/risk-summary",
        params={"sprint_id": "SPR-003"},
    ).json()
    history = client.get(
        "/projects/PRJ-COPILOTE/risk-history",
        params={"sprint_id": "SPR-003"},
    ).json()

    assert second["snapshot_created"] is True
    assert second["previous_snapshot_id"] == first["snapshot_id"]
    assert second["score"] == 58.3
    assert summary["delta"]["delta"] == -25.0
    assert summary["delta"]["direction"] == "decreased"
    assert summary["delta"]["changes"][0]["policy_id"] == "QA-PIPELINE-FAILED"
    assert summary["delta"]["changes"][0]["change"] == "removed"
    assert len(history["items"]) == 2


def test_direct_seed_uses_latest_observed_date_instead_of_system_date(
    db_session,
) -> None:
    dataset = load_dataset("data/demo_dataset_v0.1.json")
    seed_dataset(db_session, dataset)
    assert db_session.scalar(select(func.count()).select_from(IngestionLog)) == 0

    result = QAAgent().analyze(db_session, "PRJ-COPILOTE", "SPR-003")

    assert str(result["reference_date"]) == "2026-07-13"
    assert result["score"] == 83.3


def test_risk_detail_and_scope_errors_are_explicit(db_session) -> None:
    load_demo(db_session)
    result = analyze_critical().json()
    risk_id = result["findings"][0]["id"]

    detail = client.get(f"/risks/{risk_id}")
    unknown_sprint = client.get(
        "/risks",
        params={"project_id": "PRJ-COPILOTE", "sprint_id": "UNKNOWN"},
    )
    invalid_severity = client.get(
        "/risks",
        params={"project_id": "PRJ-COPILOTE", "severity": "urgent"},
    )
    unknown_explanation = client.get("/risks/UNKNOWN/explanation")
    invalid_history_window = client.get(
        "/projects/PRJ-COPILOTE/risk-history",
        params={"from_date": "2026-07-14", "to_date": "2026-07-13"},
    )

    assert detail.status_code == 200
    assert detail.json()["risk"]["id"] == risk_id
    assert detail.json()["contribution"]["policy_id"] == result["findings"][0]["rule_id"]
    assert detail.json()["human_validation_required"] is True
    assert unknown_sprint.status_code == 404
    assert invalid_severity.status_code == 422
    assert unknown_explanation.status_code == 404
    assert invalid_history_window.status_code == 422


def test_same_input_with_changed_result_fingerprint_fails_closed(
    db_session,
) -> None:
    load_demo(db_session)
    agent = QAAgent()
    first = agent.analyze(
        db_session,
        "PRJ-COPILOTE",
        "SPR-003",
        as_of=load_dataset("data/demo_dataset_v0.1.json").reference_date,
    )
    snapshot = db_session.get(RiskAnalysis, first["snapshot_id"])
    snapshot.result_fingerprint = "corrupted-result"
    db_session.commit()

    with pytest.raises(SnapshotConsistencyError, match="different result fingerprint"):
        agent.analyze(
            db_session,
            "PRJ-COPILOTE",
            "SPR-003",
            as_of=load_dataset("data/demo_dataset_v0.1.json").reference_date,
        )


def test_integrity_error_reuses_concurrently_persisted_snapshot(db_session, monkeypatch) -> None:
    load_demo(db_session)
    original_commit = db_session.commit

    def concurrent_commit() -> None:
        original_commit()
        raise IntegrityError("insert risk snapshot", {}, RuntimeError("duplicate"))

    monkeypatch.setattr(db_session, "commit", concurrent_commit)
    result = QAAgent().analyze(
        db_session,
        "PRJ-COPILOTE",
        "SPR-003",
        as_of=load_dataset("data/demo_dataset_v0.1.json").reference_date,
    )

    assert result["snapshot_created"] is False
    assert db_session.get(RiskAnalysis, result["snapshot_id"]) is not None
