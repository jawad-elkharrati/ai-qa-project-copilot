from __future__ import annotations

from collections import Counter
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.decision_engine import evaluate_decision
from app.decision_signal_service import signals_from_snapshot
from app.models import (
    Recommendation,
    RecommendationTransition,
    Risk,
    RiskAnalysis,
    RiskContribution,
)
from app.recommendation_service import stable_risk_key
from app.risk_delta_service import compare_snapshots


class ReportNotFoundError(LookupError):
    pass


class ReportPeriodError(ValueError):
    pass


def _scope_query(project_id: str, sprint_id: str | None):
    query = select(RiskAnalysis).where(RiskAnalysis.project_id == project_id)
    return (
        query.where(RiskAnalysis.sprint_id == sprint_id)
        if sprint_id is not None
        else query.where(RiskAnalysis.sprint_id.is_(None))
    )


def _snapshots(
    session: Session,
    project_id: str,
    sprint_id: str | None,
    start: date,
    end: date,
) -> list[RiskAnalysis]:
    query = _scope_query(project_id, sprint_id).where(
        RiskAnalysis.reference_date >= start,
        RiskAnalysis.reference_date <= end,
    )
    return list(
        session.scalars(query.order_by(RiskAnalysis.reference_date, RiskAnalysis.analyzed_at))
    )


def _risks(session: Session, snapshot_id: str) -> list[Risk]:
    return list(
        session.scalars(
            select(Risk)
            .where(Risk.analysis_id == snapshot_id, Risk.status == "open")
            .order_by(Risk.priority, Risk.rule_id, Risk.source_id)
        )
    )


def _contributions(session: Session, snapshot_id: str) -> list[RiskContribution]:
    return list(
        session.scalars(
            select(RiskContribution)
            .where(RiskContribution.analysis_id == snapshot_id)
            .order_by(RiskContribution.contribution.desc(), RiskContribution.policy_id)
        )
    )


def _risk_map(risks: list[Risk]) -> dict[str, Risk]:
    return {stable_risk_key(risk): risk for risk in risks}


def _risk_item(risk: Risk) -> dict[str, object]:
    return {
        "risk_id": risk.id,
        "risk_key": stable_risk_key(risk),
        "policy_id": risk.rule_id,
        "title": risk.title,
        "severity": risk.severity,
        "score": risk.score,
        "confidence": risk.confidence,
        "source_type": risk.source_type,
        "source_id": risk.source_id,
        "evidence": risk.evidence,
    }


def _information(items: list) -> list[str]:
    values: list[str] = []
    for item in items:
        if isinstance(item, dict):
            value = item.get("code") or item.get("label") or item.get("detail")
        else:
            value = item
        if value:
            values.append(str(value))
    return sorted(set(values))


def _recommendations(
    session: Session, project_id: str, sprint_id: str | None, end: date
) -> list[Recommendation]:
    query = select(Recommendation).where(Recommendation.project_id == project_id)
    query = (
        query.where(Recommendation.sprint_id == sprint_id)
        if sprint_id is not None
        else query.where(Recommendation.sprint_id.is_(None))
    )
    rows = list(session.scalars(query.order_by(Recommendation.priority_score.desc())))
    return [item for item in rows if item.created_at.date() <= end]


def _recommendation_item(item: Recommendation) -> dict[str, object]:
    return {
        "id": item.id,
        "policy_id": item.policy_id,
        "title": item.title,
        "priority": item.priority,
        "priority_score": item.priority_score,
        "priority_justification": item.priority_justification,
        "status": item.status,
        "observation_count": item.observation_count,
        "resolved_snapshot_id": item.resolved_snapshot_id,
    }


def daily_report(
    session: Session,
    project_id: str,
    report_date: date,
    sprint_id: str | None = None,
) -> dict[str, object]:
    candidates = _snapshots(session, project_id, sprint_id, report_date, report_date)
    if not candidates:
        raise ReportNotFoundError("no risk snapshot for the requested date and scope")
    current = candidates[-1]
    earlier = list(
        session.scalars(
            _scope_query(project_id, sprint_id)
            .where(RiskAnalysis.reference_date < report_date)
            .order_by(RiskAnalysis.reference_date.desc(), RiskAnalysis.analyzed_at.desc())
            .limit(1)
        )
    )
    previous = earlier[0] if earlier else None
    current_risks = _risks(session, current.id)
    previous_risks = _risks(session, previous.id) if previous else []
    current_map = _risk_map(current_risks)
    previous_map = _risk_map(previous_risks)
    delta = compare_snapshots(session, current, previous)
    increased_policies = {
        item["policy_id"] for item in delta["changes"] if item["change"] == "increased"
    }
    aggravated = [
        risk
        for key, risk in current_map.items()
        if key in previous_map
        and (
            risk.rule_id in increased_policies
            or risk.priority < previous_map[key].priority
            or risk.score > previous_map[key].score
        )
    ]
    decision = evaluate_decision(signals_from_snapshot(session, current.id))
    recommendations = _recommendations(session, project_id, sprint_id, report_date)
    transitions = (
        list(
            session.scalars(
                select(RecommendationTransition).where(
                    RecommendationTransition.recommendation_id.in_(
                        [item.id for item in recommendations]
                    )
                )
            )
        )
        if recommendations
        else []
    )
    human_status = Counter(
        transition.to_status for transition in transitions if transition.actor_role != "SYSTEM"
    )
    contributions = _contributions(session, current.id)
    return {
        "report_type": "DAILY",
        "project_id": project_id,
        "sprint_id": sprint_id,
        "report_date": report_date,
        "period_start": report_date,
        "period_end": report_date,
        "snapshot_id": current.id,
        "score": current.score,
        "risk_level": current.severity,
        "risk_delta": delta,
        "new_risks": [
            _risk_item(current_map[key]) for key in sorted(current_map.keys() - previous_map.keys())
        ],
        "resolved_risks": [
            _risk_item(previous_map[key])
            for key in sorted(previous_map.keys() - current_map.keys())
        ],
        "aggravated_risks": [_risk_item(risk) for risk in aggravated],
        "violated_policies": sorted({risk.rule_id for risk in current_risks}),
        "top_contributions": [
            {
                "policy_id": item.policy_id,
                "contribution": item.contribution,
                "weight": item.weight,
                "explanation": item.explanation,
            }
            for item in contributions
            if item.contribution > 0
        ],
        "available_evidence": [risk.evidence for risk in current_risks if risk.evidence],
        "missing_evidence": _information(current.missing_information),
        "stale_information": _information(current.stale_information),
        "confidence_score": current.confidence_score,
        "evidence_coverage": current.evidence_coverage,
        "recommendations": [_recommendation_item(item) for item in recommendations],
        "suggested_decision": decision.suggested_decision.value,
        "decision_justification": decision.justification,
        "decision_blockers": list(decision.blockers),
        "decision_conditions": list(decision.conditions),
        "human_decision_statuses": dict(sorted(human_status.items())),
        "human_validation_required": True,
        "external_action_executed": False,
    }


def weekly_report(
    session: Session,
    project_id: str,
    period_start: date,
    period_end: date,
    sprint_id: str | None = None,
) -> dict[str, object]:
    if period_start > period_end:
        raise ReportPeriodError("period_start must be before or equal to period_end")
    snapshots = _snapshots(session, project_id, sprint_id, period_start, period_end)
    if len(snapshots) < 2:
        raise ReportNotFoundError("at least two snapshots are required for a weekly report")
    risk_maps = [_risk_map(_risks(session, snapshot.id)) for snapshot in snapshots]
    first_keys = set(risk_maps[0])
    last_keys = set(risk_maps[-1])
    all_keys = set().union(*(set(items) for items in risk_maps))
    persistent_keys = set.intersection(*(set(items) for items in risk_maps))
    new_keys = all_keys - first_keys
    resolved_keys = all_keys - last_keys
    policy_frequency = Counter(risk.rule_id for items in risk_maps for risk in items.values())
    contribution_evolution: dict[str, list[dict[str, object]]] = {}
    for snapshot in snapshots:
        for item in _contributions(session, snapshot.id):
            contribution_evolution.setdefault(item.policy_id, []).append(
                {"date": snapshot.reference_date, "value": item.contribution}
            )
    recommendations = _recommendations(session, project_id, sprint_id, period_end)
    recommendation_ids = [item.id for item in recommendations]
    transitions = (
        list(
            session.scalars(
                select(RecommendationTransition).where(
                    RecommendationTransition.recommendation_id.in_(recommendation_ids)
                )
            )
        )
        if recommendation_ids
        else []
    )
    human_counts = Counter(
        transition.to_status
        for transition in transitions
        if transition.actor_role != "SYSTEM"
        and period_start <= transition.created_at.date() <= period_end
    )
    last_decision = evaluate_decision(signals_from_snapshot(session, snapshots[-1].id))
    score_change = round(snapshots[-1].score - snapshots[0].score, 1)
    trend = "IMPROVING" if score_change < 0 else "DEGRADING" if score_change > 0 else "STABLE"
    trend_summary = {
        "IMPROVING": "en amélioration",
        "DEGRADING": "en dégradation",
        "STABLE": "stable",
    }[trend]
    latest_by_key = {key: item for items in risk_maps for key, item in items.items()}
    return {
        "report_type": "WEEKLY",
        "project_id": project_id,
        "sprint_id": sprint_id,
        "period_start": period_start,
        "period_end": period_end,
        "snapshot_ids": [snapshot.id for snapshot in snapshots],
        "score_evolution": [
            {"date": snapshot.reference_date, "score": snapshot.score} for snapshot in snapshots
        ],
        "best_score": min(snapshot.score for snapshot in snapshots),
        "worst_score": max(snapshot.score for snapshot in snapshots),
        "score_change": score_change,
        "trend": trend,
        "new_risks": [_risk_item(latest_by_key[key]) for key in sorted(new_keys)],
        "persistent_risks": [_risk_item(latest_by_key[key]) for key in sorted(persistent_keys)],
        "resolved_risks": [_risk_item(latest_by_key[key]) for key in sorted(resolved_keys)],
        "policy_violation_frequency": dict(sorted(policy_frequency.items())),
        "contribution_evolution": dict(sorted(contribution_evolution.items())),
        "average_confidence": round(
            sum(item.confidence_score for item in snapshots) / len(snapshots), 3
        ),
        "average_evidence_coverage": round(
            sum(item.evidence_coverage for item in snapshots) / len(snapshots), 3
        ),
        "recommendations_emitted": len(recommendations),
        "recommendation_statuses": dict(Counter(item.status for item in recommendations)),
        "human_decisions": dict(sorted(human_counts.items())),
        "observed_impact": "Données corrélées dans le temps; aucune causalité attribuée.",
        "summary": (
            f"Le risque évolue de {snapshots[0].score:.1f} à {snapshots[-1].score:.1f}/100 "
            f"sur {len(snapshots)} snapshots; tendance {trend_summary}."
        ),
        "suggested_next_decision": last_decision.suggested_decision.value,
        "decision_justification": last_decision.justification,
        "human_validation_required": True,
        "external_action_executed": False,
    }
