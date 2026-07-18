from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.dataset import dataset_summary
from app.ingestion import load_csv_payload, normalize_dataset_payload, validate_payload
from app.main import app
from app.models import IngestionLog, Ticket

client = TestClient(app)


def test_csv_and_json_represent_the_same_dataset() -> None:
    csv_dataset = validate_payload(load_csv_payload("data/demo_dataset_v0.1.csv"))
    assert dataset_summary(csv_dataset)["tickets"] == 50
    assert csv_dataset.project.id == "PRJ-COPILOTE"
    assert len(csv_dataset.expected_anomalies) == 9


def test_normalization_maps_common_status_priority_and_identifiers() -> None:
    payload = {
        "project": {"id": " prj-demo ", "key": " demo "},
        "tickets": [
            {
                "id": " tkt-1 ",
                "project_id": " prj-demo ",
                "status": "In Progress",
                "priority": "P0",
                "labels": "api, urgent",
            }
        ],
    }
    normalized = normalize_dataset_payload(payload)
    assert normalized["project"] == {"id": "PRJ-DEMO", "key": "DEMO"}
    assert normalized["tickets"][0]["id"] == "TKT-1"
    assert normalized["tickets"][0]["status"] == "in_progress"
    assert normalized["tickets"][0]["priority"] == "critical"
    assert normalized["tickets"][0]["labels"] == ["api", "urgent"]


def test_demo_ingestion_is_idempotent_and_journaled(db_session) -> None:
    first = client.post("/ingest/demo")
    second = client.post("/ingest/demo")
    assert first.status_code == 200
    assert first.json()["status"] == "seeded"
    assert second.status_code == 200
    assert second.json()["status"] == "already_seeded"
    assert db_session.scalar(select(func.count()).select_from(Ticket)) == 50
    assert db_session.scalar(select(func.count()).select_from(IngestionLog)) == 2


def test_uploaded_csv_is_validated_ingested_and_journaled(db_session) -> None:
    content = Path("data/demo_dataset_v0.1.csv").read_bytes()
    response = client.post(
        "/ingest/csv",
        files={"file": ("novashop.csv", content, "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["tickets"] == 50
    assert response.json()["ingestion_status"] == "success"
    log = db_session.get(IngestionLog, response.json()["ingestion_id"])
    assert log is not None
    assert log.source_name == "novashop.csv"
    assert log.source_type == "csv"


def test_invalid_ingestion_returns_controlled_errors_and_log(db_session) -> None:
    response = client.post("/ingest", json={"version": "broken"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["ingestion_id"].startswith("ING-")
    assert detail["errors"]
    log = db_session.get(IngestionLog, detail["ingestion_id"])
    assert log is not None
    assert log.status == "failed"
