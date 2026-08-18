from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.decision_domain import DecisionSignals
from app.models import Metric, RiskAnalysis
from app.risk_repository import analysis_risks
from app.time_utils import require_utc_datetime


class DecisionSnapshotNotFoundError(LookupError):
    pass


def _information_codes(items: list) -> tuple[str, ...]:
    values = []
    for item in items:
        if isinstance(item, dict):
            value = item.get("code") or item.get("label") or item.get("detail")
        else:
            value = item
        if value:
            values.append(str(value))
    return tuple(sorted(set(values)))


def _freshness_score(analysis: RiskAnalysis) -> tuple[float, tuple[str, ...]]:
    stale_codes = _information_codes(analysis.stale_information)
    components = analysis.confidence_details.get("components", {})
    value = components.get("freshness_coverage") if isinstance(components, dict) else None
    if isinstance(value, int | float) and 0 <= float(value) <= 1:
        return float(value), stale_codes
    missing = tuple(sorted({*stale_codes, "data_freshness_unknown"}))
    return 0.0, missing


def _test_coverage(session: Session, analysis: RiskAnalysis) -> float | None:
    query = select(Metric).where(
        Metric.project_id == analysis.project_id,
        Metric.name == "test_coverage",
    )
    if analysis.sprint_id is not None:
        query = query.where(Metric.sprint_id == analysis.sprint_id)
    candidates = list(session.scalars(query.order_by(Metric.measured_at.desc(), Metric.id.desc())))
    metric = next(
        (
            item
            for item in candidates
            if require_utc_datetime(item.measured_at).date() <= analysis.reference_date
        ),
        None,
    )
    return float(metric.value) if metric is not None else None


def signals_from_snapshot(session: Session, snapshot_id: str) -> DecisionSignals:
    analysis = session.get(RiskAnalysis, snapshot_id)
    if analysis is None:
        raise DecisionSnapshotNotFoundError("risk snapshot not found")

    risks = [risk for risk in analysis_risks(session, analysis.id) if risk.status == "open"]
    critical_risks = [risk for risk in risks if risk.severity == "critical"]
    violated_policies = tuple(sorted({risk.rule_id for risk in risks}))
    blocking_policies = tuple(sorted({risk.rule_id for risk in critical_risks}))
    freshness, stale_information = _freshness_score(analysis)
    missing_information = _information_codes(analysis.missing_information)
    if "data_freshness_unknown" in stale_information:
        missing_information = tuple(sorted({*missing_information, "data_freshness_unknown"}))

    return DecisionSignals(
        project_id=analysis.project_id,
        snapshot_id=analysis.id,
        risk_score=analysis.score,
        confidence_score=analysis.confidence_score,
        evidence_coverage=analysis.evidence_coverage,
        data_freshness=freshness,
        active_risk_count=len(risks),
        critical_risk_count=len(critical_risks),
        blocking_risk_ids=tuple(sorted(risk.id for risk in critical_risks)),
        violated_policy_ids=violated_policies,
        blocking_policy_ids=blocking_policies,
        critical_ci_failure=any(
            risk.rule_id == "QA-PIPELINE-FAILED" and risk.severity == "critical" for risk in risks
        ),
        open_critical_bug_count=sum(risk.rule_id == "QA-CRITICAL-BUG-OPEN" for risk in risks),
        test_coverage_percent=_test_coverage(session, analysis),
        blocked_ticket_count=sum(risk.rule_id == "QA-BLOCKED-LONG" for risk in risks),
        overdue_ticket_count=sum(risk.rule_id == "QA-TICKET-OVERDUE" for risk in risks),
        missing_information=missing_information,
        stale_information=stale_information,
    )
