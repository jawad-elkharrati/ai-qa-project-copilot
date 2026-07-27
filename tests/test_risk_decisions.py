from fastapi.testclient import TestClient

from app.dataset import load_dataset
from app.ingestion import ingest_dataset
from app.main import app

client = TestClient(app)


def analyzed_risk(db_session) -> str:
    dataset = load_dataset("data/demo_dataset_v0.1.json")
    ingest_dataset(db_session, dataset, "json", "decision-test")
    response = client.post(
        "/risks/analyze",
        params={
            "project_id": "PRJ-COPILOTE",
            "sprint_id": "SPR-003",
            "as_of": "2026-07-13",
        },
    )
    assert response.status_code == 200
    return response.json()["findings"][0]["id"]


def test_decision_history_is_pending_before_human_action(db_session) -> None:
    risk_id = analyzed_risk(db_session)
    response = client.get(f"/risks/{risk_id}/decisions")

    assert response.status_code == 200
    assert response.json() == {
        "risk_id": risk_id,
        "current_status": "pending",
        "current_decision": None,
        "items": [],
    }


def test_accept_modify_and_reject_are_append_only(db_session) -> None:
    risk_id = analyzed_risk(db_session)
    requests = [
        {
            "status": "accepted",
            "decided_by": "Responsable QA",
            "comment": "Traitement prioritaire confirmé.",
        },
        {
            "status": "modified",
            "decided_by": "Lead technique",
            "comment": "Précision du périmètre.",
            "modified_recommendation": "Corriger puis rejouer les tests de paiement.",
        },
        {
            "status": "rejected",
            "decided_by": "Product Owner",
            "comment": "Le risque doit être réévalué avec le fournisseur.",
        },
    ]

    created = [client.post(f"/risks/{risk_id}/decisions", json=payload) for payload in requests]

    assert [response.status_code for response in created] == [201, 201, 201]
    assert all(response.json()["external_action_executed"] is False for response in created)
    assert created[0].json()["previous_decision_id"] is None
    assert created[1].json()["previous_decision_id"] == created[0].json()["id"]
    assert created[2].json()["previous_decision_id"] == created[1].json()["id"]

    history = client.get(f"/risks/{risk_id}/decisions").json()
    assert history["current_status"] == "rejected"
    assert history["current_decision"]["decided_by"] == "Product Owner"
    assert [item["status"] for item in history["items"]] == [
        "accepted",
        "modified",
        "rejected",
    ]


def test_invalid_decisions_return_controlled_errors(db_session) -> None:
    risk_id = analyzed_risk(db_session)
    cases = [
        (
            {
                "status": "accepted",
                "decided_by": "   ",
            },
            "decided_by is required",
        ),
        (
            {
                "status": "modified",
                "decided_by": "QA",
            },
            "modified_recommendation is required",
        ),
        (
            {
                "status": "rejected",
                "decided_by": "QA",
            },
            "comment is required",
        ),
    ]

    for payload, expected in cases:
        response = client.post(f"/risks/{risk_id}/decisions", json=payload)
        assert response.status_code == 422
        assert expected in str(response.json())


def test_unknown_risk_decision_routes_return_404(db_session) -> None:
    assert client.get("/risks/RSK-UNKNOWN/decisions").status_code == 404
    response = client.post(
        "/risks/RSK-UNKNOWN/decisions",
        json={"status": "accepted", "decided_by": "QA"},
    )
    assert response.status_code == 404
