from __future__ import annotations

from app.policy_loader import get_policy_set
from app.policy_models import PolicySet
from app.qa_domain import Finding

RULE_WEIGHTS = {policy.id: policy.weight for policy in get_policy_set().policies if policy.enabled}
SEVERITY_SCORES = {"low": 25.0, "medium": 50.0, "high": 75.0, "critical": 100.0}
SEVERITY_PRIORITY = {"critical": 1, "high": 2, "medium": 3, "low": 4}


def calculate_risk_score(
    findings: list[Finding], policy_set: PolicySet | None = None
) -> tuple[float, str, list[dict[str, object]]]:
    """Combine validated policy signals into a transparent, bounded score."""

    selected = policy_set or get_policy_set()
    known_ids = {policy.id for policy in selected.policies}
    unknown_ids = sorted({finding.rule_id for finding in findings} - known_ids)
    if unknown_ids:
        raise ValueError(f"findings reference unknown policies: {unknown_ids}")

    breakdown: list[dict[str, object]] = []
    total = 0.0
    for policy in selected.policies:
        if not policy.enabled:
            continue
        matching = [finding for finding in findings if finding.rule_id == policy.id]
        primary = max(matching, key=lambda finding: finding.signal_strength, default=None)
        signal = min(max(float(primary.signal_strength), 0.0), 1.0) if primary is not None else 0.0
        if len(matching) > 1:
            signal = min(
                signal + policy.aggregation.count_bonus * (len(matching) - 1),
                1.0,
            )
        contribution = round(policy.weight * signal, 2)
        total += contribution
        explanation = (
            f"{policy.name}: signal {signal:.3f} × poids {policy.weight:.1f} "
            f"= {contribution:.2f}; {len(matching)} constat(s)."
        )
        breakdown.append(
            {
                "policy_id": policy.id,
                "rule_id": policy.id,
                "policy_version": policy.version,
                "factor": policy.condition.metric,
                "raw_value": primary.raw_value if primary else None,
                "weight": policy.weight,
                "normalized_value": round(signal, 3),
                "normalized_signal": round(signal, 3),
                "contribution": contribution,
                "finding_count": len(matching),
                "explanation": explanation,
                "source_type": primary.source_type if primary else None,
                "source_id": primary.source_id if primary else None,
                "source_ids": sorted(finding.source_id for finding in matching),
                "observed_at": (
                    primary.observed_at.isoformat()
                    if primary is not None and primary.observed_at is not None
                    else None
                ),
            }
        )
    score = round(max(0.0, min(total, 100.0)), 1)
    severity = (
        "critical" if score >= 70 else "high" if score >= 45 else "medium" if score >= 20 else "low"
    )
    return score, severity, breakdown


def finding_score(finding: Finding) -> float:
    return SEVERITY_SCORES[finding.severity]


def finding_priority(finding: Finding) -> int:
    return SEVERITY_PRIORITY[finding.severity]
