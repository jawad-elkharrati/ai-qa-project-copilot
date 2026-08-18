from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.decision_domain import HumanValidationStatus, QADecision
from app.decision_engine import evaluate_decision
from app.decision_signal_service import signals_from_snapshot
from app.models import QADecisionReview, Recommendation, Risk, RiskAnalysis
from app.risk_repository import latest_analysis


class DecisionBriefNotFoundError(LookupError):
    pass


class DecisionReviewError(ValueError):
    pass


def _review_payload(review: QADecisionReview) -> dict[str, object]:
    return {
        "id": review.id,
        "project_id": review.project_id,
        "snapshot_id": review.snapshot_id,
        "suggested_decision": review.suggested_decision,
        "final_decision": review.final_decision,
        "status": review.status,
        "actor": review.actor,
        "actor_role": review.actor_role,
        "justification": review.justification,
        "comment": review.comment,
        "created_at": review.created_at,
        "previous_review_id": review.previous_review_id,
        "external_action_executed": False,
    }


def decision_reviews(session: Session, project_id: str) -> list[dict[str, object]]:
    rows = session.scalars(
        select(QADecisionReview)
        .where(QADecisionReview.project_id == project_id)
        .order_by(QADecisionReview.created_at, QADecisionReview.id)
    )
    return [_review_payload(item) for item in rows]


def decision_brief(
    session: Session,
    project_id: str,
    sprint_id: str | None = None,
    snapshot_id: str | None = None,
) -> dict[str, object]:
    snapshot = (
        session.get(RiskAnalysis, snapshot_id)
        if snapshot_id
        else latest_analysis(session, project_id, sprint_id)
    )
    if (
        snapshot is None
        or snapshot.project_id != project_id
        or (snapshot_id is None and snapshot.sprint_id != sprint_id)
    ):
        raise DecisionBriefNotFoundError("risk snapshot not found for project scope")
    risks = list(
        session.scalars(
            select(Risk)
            .where(Risk.analysis_id == snapshot.id, Risk.status == "open")
            .order_by(Risk.priority, Risk.score.desc(), Risk.id)
        )
    )
    result = evaluate_decision(signals_from_snapshot(session, snapshot.id))
    latest_review = session.scalar(
        select(QADecisionReview)
        .where(QADecisionReview.snapshot_id == snapshot.id)
        .order_by(QADecisionReview.created_at.desc(), QADecisionReview.id.desc())
        .limit(1)
    )
    recommendations = list(
        session.scalars(
            select(Recommendation)
            .where(
                Recommendation.project_id == project_id,
                Recommendation.last_seen_snapshot_id == snapshot.id,
            )
            .order_by(Recommendation.priority_score.desc(), Recommendation.id)
        )
    )
    return {
        "project_id": project_id,
        "sprint_id": sprint_id,
        "scope": "project" if sprint_id is None else f"sprint:{sprint_id}",
        "snapshot_id": snapshot.id,
        "generated_at": snapshot.analyzed_at,
        "score": snapshot.score,
        "risk_level": snapshot.severity,
        "confidence_score": snapshot.confidence_score,
        "evidence_coverage": snapshot.evidence_coverage,
        "top_risks": [
            {
                "id": risk.id,
                "policy_id": risk.rule_id,
                "title": risk.title,
                "severity": risk.severity,
                "score": risk.score,
                "evidence": risk.evidence,
            }
            for risk in risks[:5]
        ],
        "violated_policies": sorted({risk.rule_id for risk in risks}),
        "blockers": list(result.blockers),
        "conditions": list(result.conditions),
        "suggested_decision": result.suggested_decision.value,
        "justification": result.justification,
        "triggered_rules": list(result.triggered_rules),
        "recommendations": [item.id for item in recommendations],
        "evidence": [risk.evidence for risk in risks if risk.evidence],
        "missing_information": list(result.missing_information),
        "human_validation_status": (
            latest_review.status if latest_review else HumanValidationStatus.PENDING.value
        ),
        "latest_review": _review_payload(latest_review) if latest_review else None,
        "human_validation_required": True,
        "external_action_executed": False,
    }


def review_decision(
    session: Session,
    *,
    project_id: str,
    snapshot_id: str,
    status: HumanValidationStatus,
    final_decision: QADecision | None,
    actor: str,
    actor_role: str,
    justification: str,
    comment: str | None,
) -> dict[str, object]:
    if status is HumanValidationStatus.PENDING:
        raise DecisionReviewError("PENDING is not a review action")
    values = (actor.strip(), actor_role.strip(), justification.strip())
    if not all(values):
        raise DecisionReviewError("actor, actor_role and justification are required")
    brief = decision_brief(session, project_id, snapshot_id=snapshot_id)
    suggested = QADecision(str(brief["suggested_decision"]))
    if status is HumanValidationStatus.CONFIRMED:
        final_decision = suggested
    elif final_decision is None:
        raise DecisionReviewError("final_decision is required when overriding or rejecting")
    previous = session.scalar(
        select(QADecisionReview)
        .where(QADecisionReview.snapshot_id == snapshot_id)
        .order_by(QADecisionReview.created_at.desc(), QADecisionReview.id.desc())
        .limit(1)
    )
    created_at = datetime.now(UTC)
    digest = (
        hashlib.sha256(f"{snapshot_id}|{created_at.isoformat()}|{actor}".encode())
        .hexdigest()[:24]
        .upper()
    )
    review = QADecisionReview(
        id=f"QDR-{digest}",
        project_id=project_id,
        snapshot_id=snapshot_id,
        suggested_decision=suggested.value,
        final_decision=final_decision.value,
        status=status.value,
        actor=values[0],
        actor_role=values[1],
        justification=values[2],
        comment=comment.strip() if comment else None,
        created_at=created_at,
        previous_review_id=previous.id if previous else None,
        external_action_executed=False,
    )
    session.add(review)
    session.commit()
    return _review_payload(review)
