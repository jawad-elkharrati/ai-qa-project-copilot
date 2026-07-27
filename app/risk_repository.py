from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Risk, RiskAnalysis, RiskContribution


def scope_query(project_id: str, sprint_id: str | None):
    query = select(RiskAnalysis).where(RiskAnalysis.project_id == project_id)
    return (
        query.where(RiskAnalysis.sprint_id == sprint_id)
        if sprint_id is not None
        else query.where(RiskAnalysis.sprint_id.is_(None))
    )


def latest_analysis(
    session: Session, project_id: str, sprint_id: str | None
) -> RiskAnalysis | None:
    return session.scalar(
        scope_query(project_id, sprint_id)
        .order_by(RiskAnalysis.analyzed_at.desc(), RiskAnalysis.id.desc())
        .limit(1)
    )


def analysis_history(
    session: Session,
    project_id: str,
    sprint_id: str | None,
    limit: int = 100,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[RiskAnalysis]:
    query = scope_query(project_id, sprint_id)
    if from_date is not None:
        query = query.where(RiskAnalysis.reference_date >= from_date)
    if to_date is not None:
        query = query.where(RiskAnalysis.reference_date <= to_date)
    return list(
        session.scalars(
            query.order_by(RiskAnalysis.analyzed_at.desc(), RiskAnalysis.id.desc()).limit(limit)
        )
    )


def analysis_risks(session: Session, analysis_id: str) -> list[Risk]:
    return list(
        session.scalars(
            select(Risk)
            .where(Risk.analysis_id == analysis_id)
            .order_by(Risk.priority, Risk.rule_id, Risk.source_id)
        )
    )


def analysis_contributions(session: Session, analysis_id: str) -> list[RiskContribution]:
    return list(
        session.scalars(
            select(RiskContribution)
            .where(RiskContribution.analysis_id == analysis_id)
            .order_by(RiskContribution.policy_id)
        )
    )


def get_risk(session: Session, risk_id: str) -> Risk | None:
    return session.get(Risk, risk_id)


def get_policy_contribution(
    session: Session, analysis_id: str, policy_id: str
) -> RiskContribution | None:
    return session.scalar(
        select(RiskContribution).where(
            RiskContribution.analysis_id == analysis_id,
            RiskContribution.policy_id == policy_id,
        )
    )
