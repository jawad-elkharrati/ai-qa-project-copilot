import csv
import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import TextIO
from uuid import uuid4

from sqlalchemy.orm import Session

from app.dataset import dataset_summary
from app.models import IngestionLog
from app.schemas import DemoDataset
from app.seed import seed_dataset

STATUS_ALIASES = {
    "to do": "todo",
    "to_do": "todo",
    "in progress": "in_progress",
    "in-progress": "in_progress",
    "closed": "done",
    "complete": "done",
    "completed": "done",
    "successful": "success",
    "passed": "passed",
    "failure": "failed",
}
PRIORITY_ALIASES = {
    "p0": "critical",
    "p1": "high",
    "p2": "medium",
    "p3": "low",
    "urgent": "critical",
    "normal": "medium",
}
COLLECTIONS = (
    "sprints",
    "tickets",
    "commits",
    "pull_requests",
    "builds",
    "test_results",
    "metrics",
    "risks",
    "reports",
    "expected_anomalies",
)
ID_FIELDS = {
    "id",
    "project_id",
    "sprint_id",
    "ticket_id",
    "pull_request_id",
    "build_id",
    "source_id",
}


def normalize_dataset_payload(payload: dict) -> dict:
    normalized = deepcopy(payload)
    project = normalized.get("project", {})
    if isinstance(project, dict):
        for field in ("id", "key"):
            if isinstance(project.get(field), str):
                project[field] = project[field].strip().upper()

    for collection in COLLECTIONS:
        for row in normalized.get(collection, []) or []:
            if not isinstance(row, dict):
                continue
            for field in ID_FIELDS:
                if isinstance(row.get(field), str):
                    row[field] = row[field].strip().upper()
            for field in ("status", "type", "severity", "name", "unit"):
                if isinstance(row.get(field), str):
                    value = row[field].strip().lower()
                    row[field] = STATUS_ALIASES.get(value, value.replace(" ", "_"))
            if isinstance(row.get("priority"), str):
                value = row["priority"].strip().lower()
                row["priority"] = PRIORITY_ALIASES.get(value, value)
            if isinstance(row.get("labels"), str):
                row["labels"] = [
                    label.strip() for label in row["labels"].split(",") if label.strip()
                ]
    return normalized


def load_json_payload(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def _parse_csv_payload(stream: TextIO) -> dict:
    result: dict = {key: [] for key in COLLECTIONS}
    reader = csv.DictReader(stream)
    if reader.fieldnames != ["entity", "payload"]:
        raise ValueError("CSV columns must be exactly: entity,payload")
    for line_number, row in enumerate(reader, start=2):
        entity = (row.get("entity") or "").strip()
        try:
            value = json.loads(row.get("payload") or "")
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON payload on CSV line {line_number}") from exc
        if entity == "metadata":
            result.update(value)
        elif entity == "project":
            result["project"] = value
        elif entity in COLLECTIONS:
            result[entity].append(value)
        else:
            raise ValueError(f"unknown CSV entity '{entity}' on line {line_number}")
    return result


def load_csv_payload(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return _parse_csv_payload(stream)


def load_csv_content(content: bytes) -> dict:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV file must use UTF-8 encoding") from exc
    return _parse_csv_payload(StringIO(text, newline=""))


def validate_payload(payload: dict) -> DemoDataset:
    return DemoDataset.model_validate(normalize_dataset_payload(payload))


def _checksum(dataset: DemoDataset) -> str:
    content = json.dumps(dataset.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def ingest_dataset(
    session: Session,
    dataset: DemoDataset,
    source_type: str,
    source_name: str,
    reset: bool = False,
) -> dict[str, object]:
    started_at = datetime.now(UTC)
    result = seed_dataset(session, dataset, reset=reset)
    status = "success" if result["status"] == "seeded" else "skipped"
    log = IngestionLog(
        id=f"ING-{uuid4().hex.upper()}",
        project_id=dataset.project.id,
        source_type=source_type,
        source_name=source_name,
        dataset_version=dataset.version,
        reference_date=dataset.reference_date,
        status=status,
        checksum=_checksum(dataset),
        record_counts=dataset_summary(dataset),
        errors=[],
        started_at=started_at,
        finished_at=datetime.now(UTC),
    )
    session.add(log)
    session.commit()
    return {**result, "ingestion_id": log.id, "ingestion_status": status}


def log_failed_ingestion(
    session: Session, source_type: str, source_name: str, errors: list[dict]
) -> str:
    now = datetime.now(UTC)
    log = IngestionLog(
        id=f"ING-{uuid4().hex.upper()}",
        project_id=None,
        source_type=source_type,
        source_name=source_name,
        dataset_version=None,
        reference_date=None,
        status="failed",
        checksum=None,
        record_counts={},
        errors=errors,
        started_at=now,
        finished_at=now,
    )
    session.add(log)
    session.commit()
    return log.id
