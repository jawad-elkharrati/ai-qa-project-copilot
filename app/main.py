from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Body, Depends, FastAPI, File, HTTPException, Query, UploadFile
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import engine, get_db
from app.ingestion import (
    ingest_dataset,
    load_csv_content,
    load_csv_payload,
    load_json_payload,
    log_failed_ingestion,
    validate_payload,
)
from app.models import IngestionLog, Metric, Project, Ticket
from app.project_service import list_sprints, project_overview

settings = get_settings()
SessionDep = Annotated[Session, Depends(get_db)]
MAX_CSV_UPLOAD_SIZE = 5 * 1024 * 1024

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    summary="Ingestion et vue projet du Copilote IA pour le QA",
    description=(
        "API d'ingestion JSON/CSV, de consultation projet et de calcul d'indicateurs "
        "déterministes. Aucun moteur d'intelligence artificielle n'est encore actif."
    ),
)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "health": "/health",
        "documentation": "/docs",
    }


@app.get("/health", tags=["system"])
def health() -> dict[str, object]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"status": "unhealthy", "database": "unavailable"},
        ) from exc

    backend = engine.url.get_backend_name()
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "database": {"status": "reachable", "backend": backend},
        "timestamp": datetime.now(UTC).isoformat(),
    }


def _validation_errors(exc: Exception) -> list[dict[str, object]]:
    if isinstance(exc, ValidationError):
        return [
            {"location": list(error["loc"]), "message": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
    return [{"location": [], "message": str(exc), "type": "value_error"}]


@app.post("/ingest/demo", tags=["ingestion"])
def ingest_demo(
    session: SessionDep,
    format: Annotated[str, Query(pattern="^(json|csv)$")] = "json",
    reset: bool = False,
) -> dict[str, object]:
    path = Path(
        "data/demo_dataset_v0.1.json" if format == "json" else "data/demo_dataset_v0.1.csv"
    )
    try:
        payload = load_json_payload(path) if format == "json" else load_csv_payload(path)
        dataset = validate_payload(payload)
    except (OSError, ValueError, ValidationError) as exc:
        errors = _validation_errors(exc)
        ingestion_id = log_failed_ingestion(session, format, str(path), errors)
        raise HTTPException(
            status_code=422, detail={"ingestion_id": ingestion_id, "errors": errors}
        ) from exc
    return ingest_dataset(session, dataset, format, str(path), reset=reset)


@app.post("/ingest", tags=["ingestion"])
def ingest_payload(
    session: SessionDep,
    payload: Annotated[dict, Body()],
    reset: bool = False,
) -> dict[str, object]:
    try:
        dataset = validate_payload(payload)
    except (ValueError, ValidationError) as exc:
        errors = _validation_errors(exc)
        ingestion_id = log_failed_ingestion(session, "json", "request-body", errors)
        raise HTTPException(
            status_code=422, detail={"ingestion_id": ingestion_id, "errors": errors}
        ) from exc
    return ingest_dataset(session, dataset, "json", "request-body", reset=reset)


@app.post("/ingest/csv", tags=["ingestion"])
async def ingest_csv_upload(
    session: SessionDep,
    file: Annotated[UploadFile, File(description="CSV with entity,payload columns")],
    reset: bool = False,
) -> dict[str, object]:
    source_name = file.filename or "uploaded.csv"
    try:
        content = await file.read(MAX_CSV_UPLOAD_SIZE + 1)
        if len(content) > MAX_CSV_UPLOAD_SIZE:
            raise ValueError("CSV file is larger than 5 MB")
        payload = load_csv_content(content)
        dataset = validate_payload(payload)
    except (OSError, ValueError, ValidationError) as exc:
        errors = _validation_errors(exc)
        ingestion_id = log_failed_ingestion(session, "csv", source_name, errors)
        raise HTTPException(
            status_code=422, detail={"ingestion_id": ingestion_id, "errors": errors}
        ) from exc
    finally:
        await file.close()
    return ingest_dataset(session, dataset, "csv", source_name, reset=reset)


@app.get("/projects", tags=["projects"])
def projects(session: SessionDep) -> list[dict[str, object]]:
    rows = session.scalars(select(Project).order_by(Project.key))
    return [
        {"id": row.id, "key": row.key, "name": row.name, "description": row.description}
        for row in rows
    ]


@app.get("/sprints", tags=["projects"])
def sprints(project_id: str, session: SessionDep) -> list[dict[str, object]]:
    if session.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return [
        {
            "id": row.id,
            "name": row.name,
            "goal": row.goal,
            "status": row.status,
            "start_date": row.start_date,
            "end_date": row.end_date,
        }
        for row in list_sprints(session, project_id)
    ]


@app.get("/overview", tags=["projects"])
def overview(
    project_id: str,
    session: SessionDep,
    sprint_id: str | None = None,
    as_of: date | None = None,
) -> dict[str, object]:
    result = project_overview(session, project_id, sprint_id, as_of)
    if result is None:
        raise HTTPException(status_code=404, detail="project not found")
    return result


@app.get("/tickets", tags=["projects"])
def tickets(
    project_id: str,
    session: SessionDep,
    sprint_id: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict[str, object]]:
    query = select(Ticket).where(Ticket.project_id == project_id)
    if sprint_id:
        query = query.where(Ticket.sprint_id == sprint_id)
    if status:
        query = query.where(Ticket.status == status)
    if priority:
        query = query.where(Ticket.priority == priority)
    rows = session.scalars(query.order_by(Ticket.id).offset(offset).limit(limit))
    return [
        {
            "id": row.id,
            "sprint_id": row.sprint_id,
            "title": row.title,
            "type": row.type,
            "status": row.status,
            "priority": row.priority,
            "assignee": row.assignee,
            "story_points": row.story_points,
            "due_date": row.due_date,
        }
        for row in rows
    ]


@app.get("/metrics", tags=["projects"])
def metrics(
    project_id: str,
    session: SessionDep,
    sprint_id: str | None = None,
    name: str | None = None,
) -> list[dict[str, object]]:
    query = select(Metric).where(Metric.project_id == project_id)
    if sprint_id:
        query = query.where(Metric.sprint_id == sprint_id)
    if name:
        query = query.where(Metric.name == name)
    rows = session.scalars(query.order_by(Metric.measured_at.desc()))
    return [
        {
            "id": row.id,
            "sprint_id": row.sprint_id,
            "name": row.name,
            "value": row.value,
            "unit": row.unit,
            "source": row.source,
            "measured_at": row.measured_at,
        }
        for row in rows
    ]


@app.get("/ingestions", tags=["ingestion"])
def ingestions(session: SessionDep) -> list[dict[str, object]]:
    rows = session.scalars(select(IngestionLog).order_by(IngestionLog.started_at.desc()).limit(100))
    return [
        {
            "id": row.id,
            "project_id": row.project_id,
            "source_type": row.source_type,
            "source_name": row.source_name,
            "status": row.status,
            "dataset_version": row.dataset_version,
            "record_counts": row.record_counts,
            "errors": row.errors,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
        }
        for row in rows
    ]
