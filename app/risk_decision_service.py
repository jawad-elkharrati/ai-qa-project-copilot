from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Risk, RiskDecision


class RiskDecisionError(ValueError):
    pass


class RiskDecisionNotFoundError(LookupError):
    pass


def decision_history(session: Session, risk_id: str) -> list[RiskDecision]:
    return list(
        session.scalars(
            select(RiskDecision)
            .where(RiskDecision.risk_id == risk_id)
            .order_by(RiskDecision.created_at, RiskDecision.id)
        )
    )


def latest_decision(session: Session, risk_id: str) -> RiskDecision | None:
    return session.scalar(
        select(RiskDecision)
        .where(RiskDecision.risk_id == risk_id)
        .order_by(RiskDecision.created_at.desc(), RiskDecision.id.desc())
        .limit(1)
    )


def serialize_decision(decision: RiskDecision) -> dict[str, object]:
    return {
        "id": decision.id,
        "risk_id": decision.risk_id,
        "analysis_id": decision.analysis_id,
        "policy_id": decision.policy_id,
        "status": decision.status,
        "original_recommendation": decision.original_recommendation,
        "modified_recommendation": decision.modified_recommendation,
        "comment": decision.comment,
        "decided_by": decision.decided_by,
        "decided_at": decision.decided_at,
        "created_at": decision.created_at,
        "previous_decision_id": decision.previous_decision_id,
        "external_action_executed": False,
    }


def create_decision(
    session: Session,
    *,
    risk_id: str,
    status: str,
    decided_by: str,
    comment: str | None = None,
    modified_recommendation: str | None = None,
) -> RiskDecision:
    risk = session.get(Risk, risk_id)
    if risk is None or risk.analysis_id is None:
        raise RiskDecisionNotFoundError("risk not found")
    actor = decided_by.strip()
    if not actor:
        raise RiskDecisionError("decided_by is required")
    normalized_comment = comment.strip() if comment else None
    normalized_recommendation = modified_recommendation.strip() if modified_recommendation else None
    if status == "modified" and not normalized_recommendation:
        raise RiskDecisionError("modified_recommendation is required when status is modified")
    if status == "rejected" and not normalized_comment:
        raise RiskDecisionError("comment is required when status is rejected")
    if status not in {"accepted", "modified", "rejected"}:
        raise RiskDecisionError("only accepted, modified or rejected decisions can be recorded")

    previous = latest_decision(session, risk.id)
    now = datetime.now(UTC)
    decision = RiskDecision(
        id=f"RDC-{uuid.uuid4().hex.upper()}",
        risk_id=risk.id,
        analysis_id=risk.analysis_id,
        policy_id=risk.rule_id,
        status=status,
        original_recommendation=risk.recommendation,
        modified_recommendation=normalized_recommendation,
        comment=normalized_comment,
        decided_by=actor,
        decided_at=now,
        created_at=now,
        previous_decision_id=previous.id if previous else None,
    )
    session.add(decision)
    session.commit()
    session.refresh(decision)
    return decision
