from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Body, Depends, FastAPI, File, HTTPException, Query, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api_schemas import (
    DailyReportResponse,
    DecisionBriefResponse,
    DecisionReviewCreate,
    DecisionReviewResponse,
    RecommendationActionCreate,
    RecommendationHistoryResponse,
    RecommendationOutcomeResponse,
    RecommendationResponse,
    RecommendationTransitionResponse,
    RiskDecisionCreate,
    RiskDecisionHistoryResponse,
    RiskDecisionResponse,
    RiskDetailResponse,
    RiskExplanationResponse,
    RiskHistoryResponse,
    RiskSnapshotResponse,
    RiskSummaryResponse,
    WeeklyReportResponse,
)
from app.config import get_settings
from app.db import engine, get_db
from app.decision_brief_service import (
    DecisionBriefNotFoundError,
    DecisionReviewError,
    decision_brief,
    decision_reviews,
    review_decision,
)
from app.decision_domain import HumanValidationStatus, QADecision
from app.evidence_service import build_evidence_chain
from app.ingestion import (
    ingest_dataset,
    load_csv_content,
    load_csv_payload,
    load_json_payload,
    log_failed_ingestion,
    validate_payload,
)
from app.models import IngestionLog, Metric, Project, Recommendation, RiskAnalysis, Sprint, Ticket
from app.project_service import list_sprints, project_overview
from app.qa_agent import (
    QAAgent,
    QAEntityNotFoundError,
    QAReferenceDateError,
    serialize_contribution,
    serialize_risk,
)
from app.recommendation_domain import RecommendationStatus
from app.recommendation_outcome_service import (
    RecommendationOutcomeError,
    RecommendationOutcomeNotFoundError,
    recommendation_outcome,
)
from app.recommendation_service import (
    RecommendationError,
    RecommendationNotFoundError,
    recommendation_history,
    transition_recommendation,
)
from app.release_readiness_service import release_readiness
from app.report_rendering import render_report_html, render_report_markdown
from app.report_service import ReportNotFoundError, ReportPeriodError, daily_report, weekly_report
from app.risk_decision_service import (
    RiskDecisionError,
    RiskDecisionNotFoundError,
    create_decision,
    decision_history,
    latest_decision,
    serialize_decision,
)
from app.risk_delta_service import compare_snapshots
from app.risk_repository import (
    analysis_contributions,
    analysis_history,
    analysis_risks,
    get_policy_contribution,
    get_risk,
    latest_analysis,
)

settings = get_settings()
SessionDep = Annotated[Session, Depends(get_db)]
MAX_CSV_UPLOAD_SIZE = 5 * 1024 * 1024

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    summary="Ingestion, vue projet et analyse QA explicable",
    description=(
        "API de la semaine 3 : ingestion JSON/CSV, KPI et Agent QA déterministe avec "
        "règles versionnées, score explicable, preuves et validation humaine."
    ),
)
qa_agent = QAAgent()


def _validate_scope(session: Session, project_id: str, sprint_id: str | None = None) -> None:
    if session.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    if sprint_id is not None:
        sprint = session.get(Sprint, sprint_id)
        if sprint is None or sprint.project_id != project_id:
            raise HTTPException(status_code=404, detail="sprint not found for project")


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
    path = Path("data/demo_dataset_v0.1.json" if format == "json" else "data/demo_dataset_v0.1.csv")
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


@app.post("/risks/analyze", tags=["qa"], response_model=RiskSnapshotResponse)
def analyze_risks(
    project_id: str,
    session: SessionDep,
    sprint_id: str | None = None,
    as_of: date | None = None,
) -> dict[str, object]:
    try:
        return qa_agent.analyze(session, project_id, sprint_id, as_of)
    except QAEntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except QAReferenceDateError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/risks", tags=["qa"], response_model=RiskSnapshotResponse)
def risks(
    project_id: str,
    session: SessionDep,
    sprint_id: str | None = None,
    severity: Annotated[str | None, Query(pattern="^(low|medium|high|critical)$")] = None,
) -> dict[str, object]:
    _validate_scope(session, project_id, sprint_id)
    result = qa_agent.latest(session, project_id, sprint_id, severity)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="no QA analysis found; run POST /risks/analyze first",
        )
    return result


@app.get("/risks/{risk_id}", tags=["qa"], response_model=RiskDetailResponse)
def risk_detail(risk_id: str, session: SessionDep) -> dict[str, object]:
    risk = get_risk(session, risk_id)
    if risk is None or risk.analysis_id is None:
        raise HTTPException(status_code=404, detail="risk not found")
    contribution = get_policy_contribution(session, risk.analysis_id, risk.rule_id)
    return {
        "risk": serialize_risk(risk),
        "snapshot_id": risk.analysis_id,
        "contribution": (
            serialize_contribution(contribution) if contribution is not None else None
        ),
        "human_validation_required": True,
    }


@app.get(
    "/risks/{risk_id}/decisions",
    tags=["qa"],
    response_model=RiskDecisionHistoryResponse,
)
def risk_decisions(risk_id: str, session: SessionDep) -> dict[str, object]:
    if get_risk(session, risk_id) is None:
        raise HTTPException(status_code=404, detail="risk not found")
    items = decision_history(session, risk_id)
    current = latest_decision(session, risk_id)
    return {
        "risk_id": risk_id,
        "current_status": current.status if current else "pending",
        "current_decision": serialize_decision(current) if current else None,
        "items": [serialize_decision(item) for item in items],
    }


@app.post(
    "/risks/{risk_id}/decisions",
    tags=["qa"],
    response_model=RiskDecisionResponse,
    status_code=201,
)
def record_risk_decision(
    risk_id: str,
    payload: RiskDecisionCreate,
    session: SessionDep,
) -> dict[str, object]:
    try:
        decision = create_decision(
            session,
            risk_id=risk_id,
            status=payload.status,
            decided_by=payload.decided_by,
            comment=payload.comment,
            modified_recommendation=payload.modified_recommendation,
        )
    except RiskDecisionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RiskDecisionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return serialize_decision(decision)


@app.get(
    "/risks/{risk_id}/explanation",
    tags=["qa"],
    response_model=RiskExplanationResponse,
)
def risk_explanation(risk_id: str, session: SessionDep) -> dict[str, object]:
    risk = get_risk(session, risk_id)
    if risk is None or risk.analysis_id is None:
        raise HTTPException(status_code=404, detail="risk not found")
    analysis = session.get(RiskAnalysis, risk.analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="risk snapshot not found")
    contribution = get_policy_contribution(session, analysis.id, risk.rule_id)
    return {
        "risk_id": risk.id,
        "snapshot_id": analysis.id,
        "policy_id": risk.rule_id,
        "summary": risk.description,
        "severity": risk.severity,
        "score_contribution": contribution.contribution if contribution else 0.0,
        "confidence_score": analysis.confidence_score,
        "evidence_coverage": analysis.evidence_coverage,
        "confidence_details": analysis.confidence_details,
        "missing_information": analysis.missing_information,
        "stale_information": analysis.stale_information,
        "evidence_chain": build_evidence_chain(session, risk),
        "recommendation": risk.recommendation,
        "human_validation_required": True,
    }


@app.get(
    "/projects/{project_id}/risk-summary",
    tags=["qa"],
    response_model=RiskSummaryResponse,
)
def risk_summary(
    project_id: str,
    session: SessionDep,
    sprint_id: str | None = None,
) -> dict[str, object]:
    _validate_scope(session, project_id, sprint_id)
    analysis = latest_analysis(session, project_id, sprint_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="no QA analysis found")
    contributions = sorted(
        (serialize_contribution(item) for item in analysis_contributions(session, analysis.id)),
        key=lambda item: (-float(item["contribution"]), str(item["policy_id"])),
    )
    risks = analysis_risks(session, analysis.id)
    pending_count = sum(latest_decision(session, risk.id) is None for risk in risks)
    return {
        "project_id": project_id,
        "sprint_id": sprint_id,
        "snapshot_id": analysis.id,
        "score": analysis.score,
        "severity": analysis.severity,
        "confidence_score": analysis.confidence_score,
        "evidence_coverage": analysis.evidence_coverage,
        "confidence_details": analysis.confidence_details,
        "missing_information": analysis.missing_information,
        "stale_information": analysis.stale_information,
        "delta": compare_snapshots(session, analysis),
        "top_contributions": contributions[:5],
        "human_validation_required": True,
        "pending_recommendation_count": pending_count,
        "decision_summary": release_readiness(
            analysis,
            risks,
            pending_count,
        ),
    }


@app.get(
    "/projects/{project_id}/risk-history",
    tags=["qa"],
    response_model=RiskHistoryResponse,
)
def risk_history(
    project_id: str,
    session: SessionDep,
    sprint_id: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict[str, object]:
    _validate_scope(session, project_id, sprint_id)
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be before to_date")
    rows = analysis_history(
        session,
        project_id,
        sprint_id,
        limit=limit,
        from_date=from_date,
        to_date=to_date,
    )
    return {
        "project_id": project_id,
        "sprint_id": sprint_id,
        "items": [
            {
                "snapshot_id": row.id,
                "previous_snapshot_id": row.previous_snapshot_id,
                "reference_date": row.reference_date,
                "calculated_at": row.analyzed_at,
                "score": row.score,
                "severity": row.severity,
                "confidence_score": row.confidence_score,
                "finding_count": row.finding_count,
                "policy_version": row.ruleset_version,
            }
            for row in rows
        ],
    }


@app.get(
    "/projects/{project_id}/decision-brief",
    tags=["qa-decisions"],
    response_model=DecisionBriefResponse,
)
def get_decision_brief(
    project_id: str,
    session: SessionDep,
    sprint_id: str | None = None,
    snapshot_id: str | None = None,
) -> dict[str, object]:
    _validate_scope(session, project_id, sprint_id)
    try:
        return decision_brief(session, project_id, sprint_id, snapshot_id)
    except DecisionBriefNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/reports/daily", tags=["reports"], response_model=DailyReportResponse
)
def get_daily_report(
    project_id: str,
    report_date: date,
    session: SessionDep,
    sprint_id: str | None = None,
) -> dict[str, object]:
    _validate_scope(session, project_id, sprint_id)
    try:
        return daily_report(session, project_id, report_date, sprint_id)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/reports/weekly", tags=["reports"], response_model=WeeklyReportResponse
)
def get_weekly_report(
    project_id: str,
    period_start: date,
    period_end: date,
    session: SessionDep,
    sprint_id: str | None = None,
) -> dict[str, object]:
    _validate_scope(session, project_id, sprint_id)
    try:
        return weekly_report(session, project_id, period_start, period_end, sprint_id)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReportPeriodError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _report_export_response(
    report: dict[str, object],
    export_format: Literal["markdown", "html"],
    filename_stem: str,
) -> Response:
    if export_format == "html":
        content = render_report_html(report)
        media_type = "text/html"
        extension = "html"
    else:
        content = render_report_markdown(report)
        media_type = "text/markdown"
        extension = "md"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename_stem}.{extension}"'},
    )


@app.get("/projects/{project_id}/reports/daily/export", tags=["reports"])
def export_daily_report(
    project_id: str,
    report_date: date,
    session: SessionDep,
    sprint_id: str | None = None,
    export_format: Literal["markdown", "html"] = Query("markdown", alias="format"),
) -> Response:
    _validate_scope(session, project_id, sprint_id)
    try:
        report = daily_report(session, project_id, report_date, sprint_id)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _report_export_response(
        report,
        export_format,
        f"qa-daily-{project_id}-{report_date.isoformat()}",
    )


@app.get("/projects/{project_id}/reports/weekly/export", tags=["reports"])
def export_weekly_report(
    project_id: str,
    period_start: date,
    period_end: date,
    session: SessionDep,
    sprint_id: str | None = None,
    export_format: Literal["markdown", "html"] = Query("markdown", alias="format"),
) -> Response:
    _validate_scope(session, project_id, sprint_id)
    try:
        report = weekly_report(session, project_id, period_start, period_end, sprint_id)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReportPeriodError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _report_export_response(
        report,
        export_format,
        f"qa-weekly-{project_id}-{period_start.isoformat()}-{period_end.isoformat()}",
    )


@app.get(
    "/projects/{project_id}/recommendations",
    tags=["recommendations"],
    response_model=list[RecommendationResponse],
)
def project_recommendations(
    project_id: str,
    session: SessionDep,
    sprint_id: str | None = None,
    status: str | None = None,
    priority: str | None = None,
) -> list[Recommendation]:
    _validate_scope(session, project_id, sprint_id)
    query = select(Recommendation).where(Recommendation.project_id == project_id)
    query = query.where(
        Recommendation.sprint_id == sprint_id
        if sprint_id is not None
        else Recommendation.sprint_id.is_(None)
    )
    if status:
        query = query.where(Recommendation.status == status)
    if priority:
        query = query.where(Recommendation.priority == priority)
    return list(
        session.scalars(query.order_by(Recommendation.priority_score.desc(), Recommendation.id))
    )


@app.get(
    "/recommendations/{recommendation_id}",
    tags=["recommendations"],
    response_model=RecommendationResponse,
)
def get_recommendation(recommendation_id: str, session: SessionDep) -> Recommendation:
    recommendation = session.get(Recommendation, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=404, detail="recommendation not found")
    return recommendation


def _recommendation_action(
    recommendation_id: str,
    payload: RecommendationActionCreate,
    session: Session,
    status: RecommendationStatus,
):
    try:
        return transition_recommendation(
            session,
            recommendation_id=recommendation_id,
            to_status=status,
            actor=payload.actor,
            actor_role=payload.actor_role,
            justification=payload.justification,
            comment=payload.comment,
            changes=payload.changes,
        )
    except RecommendationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RecommendationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/recommendations/{recommendation_id}/accept",
    tags=["recommendations"],
    response_model=RecommendationTransitionResponse,
)
def accept_recommendation(
    recommendation_id: str, payload: RecommendationActionCreate, session: SessionDep
):
    return _recommendation_action(
        recommendation_id, payload, session, RecommendationStatus.ACCEPTED
    )


@app.post(
    "/recommendations/{recommendation_id}/modify",
    tags=["recommendations"],
    response_model=RecommendationTransitionResponse,
)
def modify_recommendation(
    recommendation_id: str, payload: RecommendationActionCreate, session: SessionDep
):
    return _recommendation_action(
        recommendation_id, payload, session, RecommendationStatus.MODIFIED
    )


@app.post(
    "/recommendations/{recommendation_id}/reject",
    tags=["recommendations"],
    response_model=RecommendationTransitionResponse,
)
def reject_recommendation(
    recommendation_id: str, payload: RecommendationActionCreate, session: SessionDep
):
    return _recommendation_action(
        recommendation_id, payload, session, RecommendationStatus.REJECTED
    )


@app.post(
    "/recommendations/{recommendation_id}/start",
    tags=["recommendations"],
    response_model=RecommendationTransitionResponse,
)
def start_recommendation(
    recommendation_id: str, payload: RecommendationActionCreate, session: SessionDep
):
    return _recommendation_action(
        recommendation_id, payload, session, RecommendationStatus.IN_PROGRESS
    )


@app.post(
    "/recommendations/{recommendation_id}/complete",
    tags=["recommendations"],
    response_model=RecommendationTransitionResponse,
)
def complete_recommendation(
    recommendation_id: str, payload: RecommendationActionCreate, session: SessionDep
):
    return _recommendation_action(
        recommendation_id, payload, session, RecommendationStatus.COMPLETED
    )


@app.get(
    "/recommendations/{recommendation_id}/history",
    tags=["recommendations"],
    response_model=RecommendationHistoryResponse,
)
def get_recommendation_history(recommendation_id: str, session: SessionDep) -> dict[str, object]:
    try:
        items = recommendation_history(session, recommendation_id)
    except RecommendationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"recommendation_id": recommendation_id, "items": items}


@app.get(
    "/recommendations/{recommendation_id}/outcome",
    tags=["recommendations"],
    response_model=RecommendationOutcomeResponse,
)
def get_recommendation_outcome(
    recommendation_id: str,
    session: SessionDep,
    observed_snapshot_id: str | None = None,
):
    try:
        return recommendation_outcome(session, recommendation_id, observed_snapshot_id)
    except RecommendationOutcomeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RecommendationOutcomeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/decisions",
    tags=["qa-decisions"],
    response_model=list[DecisionReviewResponse],
)
def get_project_decisions(project_id: str, session: SessionDep) -> list[dict[str, object]]:
    _validate_scope(session, project_id)
    return decision_reviews(session, project_id)


@app.post(
    "/projects/{project_id}/decisions",
    tags=["qa-decisions"],
    response_model=DecisionReviewResponse,
    status_code=201,
)
def create_project_decision(
    project_id: str, payload: DecisionReviewCreate, session: SessionDep
) -> dict[str, object]:
    _validate_scope(session, project_id)
    try:
        return review_decision(
            session,
            project_id=project_id,
            snapshot_id=payload.snapshot_id,
            status=HumanValidationStatus(payload.status),
            final_decision=QADecision(payload.final_decision) if payload.final_decision else None,
            actor=payload.actor,
            actor_role=payload.actor_role,
            justification=payload.justification,
            comment=payload.comment,
        )
    except DecisionBriefNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DecisionReviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
