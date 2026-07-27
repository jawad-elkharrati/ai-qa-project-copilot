from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.data_quality_service import assess_data_quality
from app.models import Build, IngestionLog, Metric, Project, Risk, RiskAnalysis, Sprint, Ticket
from app.policy_loader import get_policy_set
from app.qa_domain import RuleContext
from app.qa_rules import evaluate_rules
from app.qa_scoring import calculate_risk_score
from app.risk_repository import (
    analysis_contributions,
    analysis_risks,
    latest_analysis,
)
from app.risk_snapshot_service import persist_snapshot
from app.time_utils import require_utc_datetime

AGENT_NAME = "qa-agent-v1"


class QAEntityNotFoundError(LookupError):
    pass


class QAReferenceDateError(ValueError):
    pass


def _scope_filter(query, model, project_id: str, sprint_id: str | None):
    query = query.where(model.project_id == project_id)
    return query.where(model.sprint_id == sprint_id) if sprint_id else query


def _latest_reference_date(session: Session, project_id: str) -> date:
    reference = session.scalar(
        select(IngestionLog.reference_date)
        .where(
            IngestionLog.project_id == project_id,
            IngestionLog.reference_date.is_not(None),
            IngestionLog.status.in_(("success", "skipped")),
        )
        .order_by(IngestionLog.finished_at.desc())
        .limit(1)
    )
    if reference is not None:
        return reference

    observed_at = session.scalar(
        select(func.max(Metric.measured_at)).where(Metric.project_id == project_id)
    )
    if observed_at is None:
        observed_at = session.scalar(
            select(func.max(Build.started_at)).where(Build.project_id == project_id)
        )
    if observed_at is None:
        observed_at = session.scalar(
            select(func.max(Ticket.updated_at)).where(Ticket.project_id == project_id)
        )
    if observed_at is None:
        raise QAReferenceDateError("no reliable reference date found; provide the as_of parameter")
    return require_utc_datetime(observed_at).date()


def serialize_risk(risk: Risk) -> dict[str, object]:
    return {
        "id": risk.id,
        "rule_id": risk.rule_id,
        "title": risk.title,
        "description": risk.description,
        "severity": risk.severity,
        "priority": risk.priority,
        "score": risk.score,
        "confidence": risk.confidence,
        "source_type": risk.source_type,
        "source_id": risk.source_id,
        "sprint_id": risk.sprint_id,
        "evidence": risk.evidence,
        "recommendation": risk.recommendation,
        "requires_human_validation": risk.requires_human_validation,
        "status": risk.status,
        "detected_at": risk.detected_at,
    }


def serialize_contribution(contribution) -> dict[str, object]:
    return {
        "id": contribution.id,
        "policy_id": contribution.policy_id,
        "policy_version": contribution.policy_version,
        "factor": contribution.factor,
        "raw_value": contribution.raw_value,
        "normalized_value": contribution.normalized_value,
        "weight": contribution.weight,
        "contribution": contribution.contribution,
        "finding_count": contribution.finding_count,
        "explanation": contribution.explanation,
        "source_type": contribution.source_type,
        "source_id": contribution.source_id,
        "observed_at": contribution.observed_at,
    }


def _serialize_analysis(
    analysis: RiskAnalysis,
    risks: list[Risk],
    contributions: list,
    severity: str | None = None,
    snapshot_created: bool = False,
) -> dict[str, object]:
    visible = [risk for risk in risks if severity is None or risk.severity == severity]
    if contributions:
        serialized_contributions = [serialize_contribution(item) for item in contributions]
    else:
        serialized_contributions = [
            {
                "id": None,
                "policy_id": item.get("policy_id") or item.get("rule_id"),
                "policy_version": item.get("policy_version"),
                "factor": item.get("factor") or item.get("rule_id"),
                "raw_value": item.get("raw_value"),
                "normalized_value": item.get(
                    "normalized_value",
                    item.get("normalized_signal", 0.0),
                ),
                "weight": item.get("weight", 0.0),
                "contribution": item.get("contribution", 0.0),
                "finding_count": item.get("finding_count", 0),
                "explanation": item.get("explanation", ""),
                "source_type": item.get("source_type"),
                "source_id": item.get("source_id"),
                "observed_at": item.get("observed_at"),
            }
            for item in analysis.breakdown
        ]
    return {
        "analysis_id": analysis.id,
        "snapshot_id": analysis.id,
        "snapshot_created": snapshot_created,
        "previous_snapshot_id": analysis.previous_snapshot_id,
        "agent": analysis.agent_name,
        "ruleset_version": analysis.ruleset_version,
        "policy_hash": analysis.policy_hash,
        "input_fingerprint": analysis.input_fingerprint,
        "project_id": analysis.project_id,
        "sprint_id": analysis.sprint_id,
        "reference_date": analysis.reference_date,
        "score": analysis.score,
        "severity": analysis.severity,
        "score_breakdown": analysis.breakdown,
        "contributions": serialized_contributions,
        "finding_count": analysis.finding_count,
        "returned_findings": len(visible),
        "analyzed_at": analysis.analyzed_at,
        "confidence_score": analysis.confidence_score,
        "evidence_coverage": analysis.evidence_coverage,
        "confidence_details": analysis.confidence_details,
        "missing_information": analysis.missing_information,
        "stale_information": analysis.stale_information,
        "human_validation_required": True,
        "findings": [serialize_risk(risk) for risk in visible],
    }


class QAAgent:
    """Deterministic QA agent: facts, policies, scoring and immutable snapshots."""

    def analyze(
        self,
        session: Session,
        project_id: str,
        sprint_id: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, object]:
        if session.get(Project, project_id) is None:
            raise QAEntityNotFoundError("project not found")
        if sprint_id:
            sprint = session.get(Sprint, sprint_id)
            if sprint is None or sprint.project_id != project_id:
                raise QAEntityNotFoundError("sprint not found for project")

        reference_date = as_of or _latest_reference_date(session, project_id)
        analyzed_at = datetime.now(UTC)
        tickets = list(
            session.scalars(
                _scope_filter(select(Ticket), Ticket, project_id, sprint_id).order_by(Ticket.id)
            )
        )
        builds = list(
            session.scalars(
                _scope_filter(select(Build), Build, project_id, sprint_id).order_by(
                    Build.started_at,
                    Build.id,
                )
            )
        )
        metrics = list(
            session.scalars(
                _scope_filter(select(Metric), Metric, project_id, sprint_id).order_by(
                    Metric.measured_at,
                    Metric.id,
                )
            )
        )
        sprints = list(
            session.scalars(
                select(Sprint)
                .where(Sprint.project_id == project_id)
                .order_by(Sprint.start_date, Sprint.id)
            )
        )
        context = RuleContext(
            project_id=project_id,
            reference_date=reference_date,
            analyzed_at=analyzed_at,
            tickets=tickets,
            builds=builds,
            metrics=metrics,
            sprints=sprints,
            sprint_id=sprint_id,
        )
        policy_set = get_policy_set()
        findings = evaluate_rules(context, policy_set)
        score, severity, breakdown = calculate_risk_score(findings, policy_set)
        data_quality = assess_data_quality(session, context)
        analysis, risks, contributions, created = persist_snapshot(
            session,
            context=context,
            policy_set=policy_set,
            score=score,
            severity=severity,
            breakdown=breakdown,
            findings=findings,
            agent_name=AGENT_NAME,
            confidence_score=data_quality.confidence_score,
            evidence_coverage=data_quality.evidence_coverage,
            confidence_details=data_quality.details,
            missing_information=data_quality.missing_information,
            stale_information=data_quality.stale_information,
        )
        return _serialize_analysis(
            analysis,
            risks,
            contributions,
            snapshot_created=created,
        )

    def latest(
        self,
        session: Session,
        project_id: str,
        sprint_id: str | None = None,
        severity: str | None = None,
    ) -> dict[str, object] | None:
        analysis = latest_analysis(session, project_id, sprint_id)
        if analysis is None:
            return None
        risks = analysis_risks(session, analysis.id)
        contributions = analysis_contributions(session, analysis.id)
        return _serialize_analysis(analysis, risks, contributions, severity)
