from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Recommendation,
    RecommendationTransition,
    Risk,
    RiskAnalysis,
)
from app.recommendation_domain import (
    RecommendationEffort,
    RecommendationImpact,
    RecommendationPriority,
    RecommendationPriorityResult,
    RecommendationStatus,
    RecommendationUrgency,
    recommendation_key,
    risk_identity_key,
)

SYSTEM_ACTOR = "qa-copilot"
SYSTEM_ROLE = "SYSTEM"


class RecommendationError(ValueError):
    pass


class RecommendationNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class RecommendationSyncResult:
    snapshot_id: str
    created_ids: tuple[str, ...]
    reused_ids: tuple[str, ...]
    resolved_ids: tuple[str, ...]


def prioritize_recommendation(
    *,
    severity: str,
    confidence: float,
    impact: RecommendationImpact,
    effort: RecommendationEffort,
    urgency: RecommendationUrgency,
    blocking: bool,
    affected_risk_count: int = 1,
) -> RecommendationPriorityResult:
    severity_points = {"low": 5, "medium": 15, "high": 25, "critical": 30}
    impact_points = {
        RecommendationImpact.LOW: 5,
        RecommendationImpact.MEDIUM: 10,
        RecommendationImpact.HIGH: 15,
    }
    effort_points = {
        RecommendationEffort.LOW: 5,
        RecommendationEffort.MEDIUM: 3,
        RecommendationEffort.HIGH: 1,
    }
    urgency_points = {
        RecommendationUrgency.PLANNED: 5,
        RecommendationUrgency.THIS_WEEK: 10,
        RecommendationUrgency.IMMEDIATE: 15,
    }
    if severity not in severity_points:
        raise RecommendationError(f"unsupported severity: {severity}")
    if not 0 <= confidence <= 1:
        raise RecommendationError("confidence must be between 0 and 1")
    if affected_risk_count < 1:
        raise RecommendationError("affected_risk_count must be positive")
    factors = {
        "severity": severity_points[severity],
        "blocking": 20 if blocking else 0,
        "impact": impact_points[impact],
        "urgency": urgency_points[urgency],
        "confidence": round(confidence * 10),
        "effort": effort_points[effort],
        "affected_risks": min(affected_risk_count, 5),
    }
    score = sum(factors.values())
    priority = (
        RecommendationPriority.CRITICAL
        if score >= 80
        else RecommendationPriority.HIGH
        if score >= 60
        else RecommendationPriority.MEDIUM
        if score >= 35
        else RecommendationPriority.LOW
    )
    justification = (
        f"Priorité {priority.value}: score {score}/100 = "
        + " + ".join(f"{name} {value}" for name, value in factors.items())
        + ". Un effort plus faible augmente légèrement la faisabilité, sans masquer la criticité."
    )
    return RecommendationPriorityResult(
        priority=priority,
        score=score,
        justification=justification,
        factors=factors,
    )


def _impact(severity: str) -> RecommendationImpact:
    if severity in {"critical", "high"}:
        return RecommendationImpact.HIGH
    if severity == "medium":
        return RecommendationImpact.MEDIUM
    return RecommendationImpact.LOW


def _urgency(severity: str) -> RecommendationUrgency:
    if severity == "critical":
        return RecommendationUrgency.IMMEDIATE
    if severity == "high":
        return RecommendationUrgency.THIS_WEEK
    return RecommendationUrgency.PLANNED


def _id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()[:24].upper()
    return f"{prefix}-{digest}"


def _stable_source_id(risk: Risk) -> str:
    if risk.rule_id == "QA-PIPELINE-FAILED":
        pipeline_name = risk.evidence.get("pipeline_name")
        branch = risk.evidence.get("branch")
        if pipeline_name:
            return f"pipeline:{pipeline_name}:{branch or '*'}"
    if risk.rule_id == "QA-COVERAGE-LOW":
        metric_name = risk.evidence.get("metric_name")
        if metric_name:
            return f"metric:{metric_name}:{risk.sprint_id or '*'}"
    return risk.source_id


def stable_risk_key(risk: Risk) -> str:
    """Return the snapshot-independent identity used by recommendations and reports."""

    return risk_identity_key(
        project_id=risk.project_id,
        policy_id=risk.rule_id,
        source_type=risk.source_type,
        source_id=_stable_source_id(risk),
    )


def _payload(recommendation: Recommendation) -> dict[str, object]:
    return {
        "title": recommendation.title,
        "description": recommendation.description,
        "justification": recommendation.justification,
        "due_date": recommendation.due_date.isoformat() if recommendation.due_date else None,
        "assigned_to": recommendation.assigned_to,
    }


def _append_transition(
    session: Session,
    recommendation: Recommendation,
    *,
    from_status: str | None,
    to_status: RecommendationStatus,
    actor: str,
    actor_role: str,
    justification: str,
    comment: str | None,
    previous_payload: dict[str, object] | None,
) -> RecommendationTransition:
    previous = list(
        session.scalars(
            select(RecommendationTransition)
            .where(RecommendationTransition.recommendation_id == recommendation.id)
            .order_by(RecommendationTransition.sequence.desc())
            .limit(1)
        )
    )
    sequence = previous[0].sequence + 1 if previous else 1
    transition = RecommendationTransition(
        id=_id("RTR", recommendation.id, str(sequence)),
        recommendation_id=recommendation.id,
        source_snapshot_id=recommendation.last_seen_snapshot_id,
        sequence=sequence,
        from_status=from_status,
        to_status=to_status.value,
        actor=actor,
        actor_role=actor_role,
        comment=comment,
        justification=justification,
        previous_payload=previous_payload,
        resulting_payload=_payload(recommendation),
        created_at=recommendation.updated_at,
        external_action_executed=False,
    )
    session.add(transition)
    return transition


def _scope_recommendations(
    session: Session, project_id: str, sprint_id: str | None
) -> list[Recommendation]:
    query = select(Recommendation).where(Recommendation.project_id == project_id)
    query = (
        query.where(Recommendation.sprint_id == sprint_id)
        if sprint_id is not None
        else query.where(Recommendation.sprint_id.is_(None))
    )
    return list(session.scalars(query.order_by(Recommendation.created_at, Recommendation.id)))


def _create_recommendation(
    session: Session,
    analysis: RiskAnalysis,
    risk: Risk,
    risk_key: str,
    stable_recommendation_key: str,
) -> Recommendation:
    impact = _impact(risk.severity)
    urgency = _urgency(risk.severity)
    effort = RecommendationEffort.MEDIUM
    priority = prioritize_recommendation(
        severity=risk.severity,
        confidence=risk.confidence,
        impact=impact,
        effort=effort,
        urgency=urgency,
        blocking=risk.severity == "critical",
    )
    original_payload = {
        "title": risk.title,
        "description": risk.recommendation,
        "justification": risk.description,
        "source_risk_id": risk.id,
        "source_snapshot_id": analysis.id,
    }
    recommendation = Recommendation(
        id=_id("REC", analysis.id, stable_recommendation_key),
        project_id=analysis.project_id,
        sprint_id=analysis.sprint_id,
        source_snapshot_id=analysis.id,
        source_risk_id=risk.id,
        last_seen_snapshot_id=analysis.id,
        last_seen_risk_id=risk.id,
        resolved_snapshot_id=None,
        resolved_at=None,
        observation_count=1,
        policy_id=risk.rule_id,
        risk_key=risk_key,
        recommendation_key=stable_recommendation_key,
        title=risk.title,
        description=risk.recommendation,
        justification=risk.description,
        evidence=[risk.evidence],
        priority=priority.priority.value,
        priority_score=priority.score,
        priority_factors=priority.factors,
        priority_justification=priority.justification,
        severity=risk.severity,
        impact=impact.value,
        effort=effort.value,
        urgency=urgency.value,
        confidence=risk.confidence,
        latest_evidence=[risk.evidence],
        latest_severity=risk.severity,
        latest_score=risk.score,
        latest_confidence=risk.confidence,
        status=RecommendationStatus.PROPOSED.value,
        original_payload=original_payload,
        due_date=None,
        assigned_to=None,
        created_at=analysis.analyzed_at,
        updated_at=analysis.analyzed_at,
    )
    session.add(recommendation)
    session.flush()
    _append_transition(
        session,
        recommendation,
        from_status=None,
        to_status=RecommendationStatus.PROPOSED,
        actor=SYSTEM_ACTOR,
        actor_role=SYSTEM_ROLE,
        justification="Recommandation déterministe créée à partir du risque observé.",
        comment=None,
        previous_payload=None,
    )
    return recommendation


def sync_recommendations_for_snapshot(
    session: Session, snapshot_id: str
) -> RecommendationSyncResult:
    analysis = session.get(RiskAnalysis, snapshot_id)
    if analysis is None:
        raise RecommendationNotFoundError("risk snapshot not found")
    risks = list(
        session.scalars(
            select(Risk)
            .where(Risk.analysis_id == analysis.id, Risk.status == "open")
            .order_by(Risk.priority, Risk.rule_id, Risk.source_id)
        )
    )
    scoped = _scope_recommendations(session, analysis.project_id, analysis.sprint_id)
    created: list[str] = []
    reused: list[str] = []
    current_keys: set[str] = set()

    for risk in risks:
        risk_key = stable_risk_key(risk)
        current_keys.add(risk_key)
        stable_key = recommendation_key(risk_key=risk_key)
        episodes = [item for item in scoped if item.risk_key == risk_key]
        latest = max(episodes, key=lambda item: (item.created_at, item.id), default=None)
        if latest is not None and latest.resolved_snapshot_id is None:
            if latest.last_seen_snapshot_id != analysis.id:
                latest.last_seen_snapshot_id = analysis.id
                latest.last_seen_risk_id = risk.id
                latest.observation_count += 1
                latest.latest_evidence = [risk.evidence]
                latest.latest_severity = risk.severity
                latest.latest_score = risk.score
                latest.latest_confidence = risk.confidence
                latest.updated_at = analysis.analyzed_at
            reused.append(latest.id)
            continue
        recommendation = _create_recommendation(session, analysis, risk, risk_key, stable_key)
        scoped.append(recommendation)
        created.append(recommendation.id)

    resolved: list[str] = []
    for recommendation in scoped:
        if (
            recommendation.resolved_snapshot_id is not None
            or recommendation.risk_key in current_keys
        ):
            continue
        last_seen = session.get(RiskAnalysis, recommendation.last_seen_snapshot_id)
        if last_seen is not None and last_seen.reference_date < analysis.reference_date:
            recommendation.resolved_snapshot_id = analysis.id
            recommendation.resolved_at = analysis.analyzed_at
            recommendation.updated_at = analysis.analyzed_at
            resolved.append(recommendation.id)
    session.commit()
    return RecommendationSyncResult(
        snapshot_id=analysis.id,
        created_ids=tuple(created),
        reused_ids=tuple(reused),
        resolved_ids=tuple(resolved),
    )


ALLOWED_TRANSITIONS = {
    RecommendationStatus.PROPOSED: {
        RecommendationStatus.ACCEPTED,
        RecommendationStatus.MODIFIED,
        RecommendationStatus.REJECTED,
    },
    RecommendationStatus.ACCEPTED: {
        RecommendationStatus.IN_PROGRESS,
        RecommendationStatus.COMPLETED,
    },
    RecommendationStatus.MODIFIED: {
        RecommendationStatus.IN_PROGRESS,
        RecommendationStatus.COMPLETED,
    },
    RecommendationStatus.IN_PROGRESS: {RecommendationStatus.COMPLETED},
    RecommendationStatus.REJECTED: set(),
    RecommendationStatus.COMPLETED: set(),
}


def transition_recommendation(
    session: Session,
    *,
    recommendation_id: str,
    to_status: RecommendationStatus,
    actor: str,
    actor_role: str,
    justification: str,
    comment: str | None = None,
    changes: dict[str, object] | None = None,
) -> RecommendationTransition:
    recommendation = session.get(Recommendation, recommendation_id)
    if recommendation is None:
        raise RecommendationNotFoundError("recommendation not found")
    current = RecommendationStatus(recommendation.status)
    if to_status not in ALLOWED_TRANSITIONS[current]:
        raise RecommendationError(f"transition {current.value} -> {to_status.value} is not allowed")
    normalized = {
        "actor": actor.strip(),
        "actor_role": actor_role.strip(),
        "justification": justification.strip(),
        "comment": comment.strip() if comment else None,
    }
    for field in ("actor", "actor_role", "justification"):
        if not normalized[field]:
            raise RecommendationError(f"{field} is required")
    if to_status is RecommendationStatus.REJECTED and not normalized["comment"]:
        raise RecommendationError("comment is required when rejecting a recommendation")
    previous_payload = _payload(recommendation)
    if to_status is RecommendationStatus.COMPLETED and not normalized["comment"]:
        raise RecommendationError("comment is required when completing a recommendation")
    if to_status is RecommendationStatus.IN_PROGRESS:
        allowed_operational_changes = {"assigned_to", "due_date"}
        supplied = changes or {}
        if set(supplied) - allowed_operational_changes:
            raise RecommendationError("only operational changes are allowed when starting work")
        for field, value in supplied.items():
            if field == "due_date" and isinstance(value, str):
                value = date.fromisoformat(value)
            setattr(recommendation, field, value)
    if to_status is RecommendationStatus.MODIFIED:
        allowed_changes = {"title", "description", "justification", "assigned_to", "due_date"}
        supplied = changes or {}
        if not supplied or set(supplied) - allowed_changes:
            raise RecommendationError("valid changes are required when modifying a recommendation")
        for field, value in supplied.items():
            if field == "due_date" and isinstance(value, str):
                value = date.fromisoformat(value)
            setattr(recommendation, field, value)
    recommendation.updated_at = datetime.now(UTC)
    recommendation.status = to_status.value
    transition = _append_transition(
        session,
        recommendation,
        from_status=current.value,
        to_status=to_status,
        actor=str(normalized["actor"]),
        actor_role=str(normalized["actor_role"]),
        justification=str(normalized["justification"]),
        comment=normalized["comment"],
        previous_payload=previous_payload,
    )
    session.commit()
    session.refresh(transition)
    return transition


def recommendation_history(
    session: Session, recommendation_id: str
) -> list[RecommendationTransition]:
    if session.get(Recommendation, recommendation_id) is None:
        raise RecommendationNotFoundError("recommendation not found")
    return list(
        session.scalars(
            select(RecommendationTransition)
            .where(RecommendationTransition.recommendation_id == recommendation_id)
            .order_by(RecommendationTransition.sequence)
        )
    )
