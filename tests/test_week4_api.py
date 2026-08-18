from fastapi.testclient import TestClient

from app.dataset import load_dataset
from app.main import app
from app.seed import seed_dataset

client = TestClient(app)


def _seed(db_session) -> None:
    seed_dataset(db_session, load_dataset("data/demo_dataset_v0.1.json"))


def test_week4_read_api_exposes_typed_decision_and_reports(db_session) -> None:
    _seed(db_session)

    brief = client.get("/projects/PRJ-COPILOTE/decision-brief")
    daily = client.get("/projects/PRJ-COPILOTE/reports/daily", params={"report_date": "2026-07-18"})
    weekly = client.get(
        "/projects/PRJ-COPILOTE/reports/weekly",
        params={"period_start": "2026-07-14", "period_end": "2026-07-20"},
    )

    assert brief.status_code == 200
    assert brief.json()["snapshot_id"] == "QAH-NS-20260720"
    assert brief.json()["human_validation_status"] == "PENDING"
    assert brief.json()["external_action_executed"] is False
    assert daily.status_code == 200
    assert daily.json()["report_type"] == "DAILY"
    assert daily.json()["resolved_risks"]
    assert weekly.status_code == 200
    assert weekly.json()["snapshot_ids"] == [f"QAH-NS-202607{day:02d}" for day in range(14, 21)]
    assert weekly.json()["trend"] == "IMPROVING"


def test_recommendation_acceptance_is_append_only_and_never_external(db_session) -> None:
    _seed(db_session)
    recommendations = client.get("/projects/PRJ-COPILOTE/recommendations")
    recommendation = next(
        item for item in recommendations.json() if item["policy_id"] == "QA-TICKET-OVERDUE"
    )

    response = client.post(
        f"/recommendations/{recommendation['id']}/accept",
        json={
            "actor": "qa.lead",
            "actor_role": "QA_LEAD",
            "justification": "Le plan de correction est approuv?.",
            "comment": "Suivi quotidien requis.",
        },
    )
    history = client.get(f"/recommendations/{recommendation['id']}/history")

    assert response.status_code == 200
    assert response.json()["to_status"] == "ACCEPTED"
    assert response.json()["external_action_executed"] is False
    assert [item["to_status"] for item in history.json()["items"]] == [
        "PROPOSED",
        "ACCEPTED",
    ]
    assert history.json()["items"][1]["actor_role"] == "QA_LEAD"


def test_recommendation_modify_preserves_original_payload_through_api(db_session) -> None:
    _seed(db_session)
    recommendation = client.get("/projects/PRJ-COPILOTE/recommendations").json()[0]
    original = recommendation["original_payload"]

    response = client.post(
        f"/recommendations/{recommendation['id']}/modify",
        json={
            "actor": "pm.user",
            "actor_role": "PROJECT_MANAGER",
            "justification": "Responsabilit? pr?cis?e.",
            "comment": "Le fond de la recommandation reste inchang?.",
            "changes": {"assigned_to": "qa-team"},
        },
    )
    current = client.get(f"/recommendations/{recommendation['id']}").json()

    assert response.status_code == 200
    assert response.json()["previous_payload"]["assigned_to"] is None
    assert current["original_payload"] == original
    assert current["assigned_to"] == "qa-team"


def test_human_decision_review_updates_brief_without_external_action(db_session) -> None:
    _seed(db_session)
    snapshot_id = "QAH-NS-20260720"
    response = client.post(
        "/projects/PRJ-COPILOTE/decisions",
        json={
            "snapshot_id": snapshot_id,
            "status": "CONFIRMED",
            "actor": "qa.lead",
            "actor_role": "QA_LEAD",
            "justification": "Les conditions propos?es sont retenues.",
        },
    )
    history = client.get("/projects/PRJ-COPILOTE/decisions")
    brief = client.get("/projects/PRJ-COPILOTE/decision-brief")

    assert response.status_code == 201
    assert response.json()["final_decision"] == response.json()["suggested_decision"]
    assert response.json()["external_action_executed"] is False
    assert len(history.json()) == 1
    assert brief.json()["human_validation_status"] == "CONFIRMED"
    assert brief.json()["latest_review"]["actor"] == "qa.lead"


def test_recommendation_operational_lifecycle_through_api(db_session) -> None:
    _seed(db_session)
    recommendation = next(
        item
        for item in client.get("/projects/PRJ-COPILOTE/recommendations").json()
        if item["policy_id"] == "QA-PIPELINE-FAILED"
    )
    action = {
        "actor": "qa.lead",
        "actor_role": "QA_LEAD",
        "justification": "Traitement manuel gouverné.",
    }
    accepted = client.post(f"/recommendations/{recommendation['id']}/accept", json=action)
    started = client.post(
        f"/recommendations/{recommendation['id']}/start",
        json={**action, "changes": {"assigned_to": "qa-team"}},
    )
    completed = client.post(
        f"/recommendations/{recommendation['id']}/complete",
        json={**action, "comment": "Correction contrôlée localement."},
    )

    assert [accepted.status_code, started.status_code, completed.status_code] == [200, 200, 200]
    assert started.json()["to_status"] == "IN_PROGRESS"
    assert completed.json()["to_status"] == "COMPLETED"
    assert completed.json()["external_action_executed"] is False


def test_recommendation_outcome_api_is_typed_and_idempotent(db_session) -> None:
    _seed(db_session)
    recommendation = next(
        item
        for item in client.get("/projects/PRJ-COPILOTE/recommendations").json()
        if item["policy_id"] == "QA-PIPELINE-FAILED"
    )
    endpoint = f"/recommendations/{recommendation['id']}/outcome"
    pending = client.get(endpoint)
    client.post(
        f"/recommendations/{recommendation['id']}/accept",
        json={
            "actor": "qa.lead",
            "actor_role": "QA_LEAD",
            "justification": "Traitement manuel approuvé.",
        },
    )
    measured = client.get(endpoint)
    repeated = client.get(endpoint)

    assert pending.status_code == 200
    assert pending.json()["status"] == "NOT_YET_MEASURABLE"
    assert measured.status_code == 200
    assert measured.json() == repeated.json()
    assert measured.json()["status"] == "IMPROVEMENT_OBSERVED"
    assert measured.json()["persisted"] is True
    assert measured.json()["external_action_executed"] is False


def test_report_exports_expose_downloadable_markdown_and_html(db_session) -> None:
    _seed(db_session)
    daily = client.get(
        "/projects/PRJ-COPILOTE/reports/daily/export",
        params={"report_date": "2026-07-20", "format": "markdown"},
    )
    weekly = client.get(
        "/projects/PRJ-COPILOTE/reports/weekly/export",
        params={
            "period_start": "2026-07-14",
            "period_end": "2026-07-20",
            "format": "html",
        },
    )
    invalid = client.get(
        "/projects/PRJ-COPILOTE/reports/daily/export",
        params={"report_date": "2026-07-20", "format": "pdf"},
    )

    assert daily.status_code == 200
    assert daily.headers["content-type"].startswith("text/markdown")
    assert daily.headers["content-disposition"].endswith('.md"')
    assert "Aucune action externe n’a été exécutée" in daily.text
    assert weekly.status_code == 200
    assert weekly.headers["content-type"].startswith("text/html")
    assert weekly.headers["content-disposition"].endswith('.html"')
    assert "Rapport QA hebdomadaire" in weekly.text
    assert invalid.status_code == 422


def test_week4_api_maps_domain_errors_to_http_statuses(db_session) -> None:
    _seed(db_session)

    missing = client.get(
        "/projects/PRJ-COPILOTE/reports/daily", params={"report_date": "2026-01-01"}
    )
    invalid = client.get(
        "/projects/PRJ-COPILOTE/reports/weekly",
        params={"period_start": "2026-07-20", "period_end": "2026-07-14"},
    )
    unknown = client.get("/recommendations/UNKNOWN")

    assert missing.status_code == 404
    assert invalid.status_code == 422
    assert unknown.status_code == 404


def test_openapi_documents_the_p0_week4_contracts() -> None:
    schema = client.get("/openapi.json").json()

    assert {
        "/projects/{project_id}/decision-brief",
        "/projects/{project_id}/reports/daily",
        "/projects/{project_id}/reports/weekly",
        "/projects/{project_id}/recommendations",
        "/recommendations/{recommendation_id}",
        "/recommendations/{recommendation_id}/accept",
        "/recommendations/{recommendation_id}/modify",
        "/recommendations/{recommendation_id}/reject",
        "/recommendations/{recommendation_id}/history",
        "/projects/{project_id}/decisions",
    } <= set(schema["paths"])
    response_schema = schema["paths"]["/projects/{project_id}/decision-brief"]["get"]["responses"][
        "200"
    ]["content"]["application/json"]["schema"]
    assert response_schema["$ref"] == "#/components/schemas/DecisionBriefResponse"
