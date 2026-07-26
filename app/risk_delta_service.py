from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import RiskAnalysis
from app.risk_repository import analysis_contributions


def _contribution_map(session: Session, analysis: RiskAnalysis) -> dict[str, dict]:
    rows = analysis_contributions(session, analysis.id)
    if rows:
        return {
            row.policy_id: {
                "policy_id": row.policy_id,
                "factor": row.factor,
                "contribution": row.contribution,
                "explanation": row.explanation,
            }
            for row in rows
        }
    return {
        str(item.get("policy_id") or item.get("rule_id")): {
            "policy_id": str(item.get("policy_id") or item.get("rule_id")),
            "factor": item.get("factor") or item.get("rule_id"),
            "contribution": float(item.get("contribution", 0.0)),
            "explanation": item.get("explanation", ""),
        }
        for item in analysis.breakdown
    }


def compare_snapshots(
    session: Session,
    current: RiskAnalysis,
    previous: RiskAnalysis | None = None,
) -> dict[str, object]:
    if previous is None and current.previous_snapshot_id:
        previous = session.get(RiskAnalysis, current.previous_snapshot_id)

    previous_score = previous.score if previous else None
    delta = round(current.score - (previous_score or 0.0), 1) if previous else None
    current_factors = _contribution_map(session, current)
    previous_factors = _contribution_map(session, previous) if previous else {}
    changes = []
    unchanged_count = 0
    for policy_id in sorted(set(current_factors) | set(previous_factors)):
        current_item = current_factors.get(policy_id)
        previous_item = previous_factors.get(policy_id)
        current_value = float(current_item["contribution"]) if current_item else 0.0
        previous_value = float(previous_item["contribution"]) if previous_item else 0.0
        factor_delta = round(current_value - previous_value, 2)
        if factor_delta == 0:
            unchanged_count += 1
            continue
        status = (
            "added"
            if previous_value == 0 and current_value > 0
            else "removed"
            if current_value == 0 and previous_value > 0
            else "increased"
            if factor_delta > 0
            else "decreased"
        )
        selected = current_item or previous_item
        changes.append(
            {
                "policy_id": policy_id,
                "factor": selected["factor"],
                "previous_contribution": previous_value,
                "current_contribution": current_value,
                "delta": factor_delta,
                "change": status,
                "explanation": selected["explanation"],
            }
        )
    changes.sort(key=lambda item: (-abs(float(item["delta"])), str(item["policy_id"])))
    return {
        "current_snapshot_id": current.id,
        "previous_snapshot_id": previous.id if previous else None,
        "current_score": current.score,
        "previous_score": previous_score,
        "delta": delta,
        "direction": (
            "initial"
            if delta is None
            else "increased"
            if delta > 0
            else "decreased"
            if delta < 0
            else "unchanged"
        ),
        "changes": changes,
        "unchanged_factor_count": unchanged_count,
    }
