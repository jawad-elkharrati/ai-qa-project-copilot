from __future__ import annotations

from app.policy_models import PolicyCondition, PolicyDefinition
from app.qa_domain import Fact, Finding

SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _matches(actual, condition: PolicyCondition) -> bool:
    if actual is None:
        return False
    expected = condition.value
    operator = condition.operator
    if operator == "equal":
        return actual == expected
    if operator == "not_equal":
        return actual != expected
    if operator == "greater_than":
        return actual > expected
    if operator == "greater_or_equal":
        return actual >= expected
    if operator == "less_than":
        return actual < expected
    if operator == "less_or_equal":
        return actual <= expected
    if operator == "in":
        return actual in expected
    if operator == "not_in":
        return actual not in expected
    raise ValueError(f"unsupported policy operator: {operator}")


def _normalize(policy: PolicyDefinition, raw_value) -> float:
    definition = policy.normalization
    if definition.strategy == "boolean":
        value = 1.0 if raw_value is True else 0.0
    elif definition.strategy == "ratio":
        value = float(raw_value) / definition.divisor
    elif definition.strategy == "distance_below":
        value = (float(definition.baseline) - float(raw_value)) / definition.divisor
    else:  # pragma: no cover - protected by Pydantic's Literal
        raise ValueError(f"unsupported normalization strategy: {definition.strategy}")
    return min(max(value, 0.0), 1.0)


def _severity(policy: PolicyDefinition, fact: Fact) -> str:
    severity = policy.severity
    for override in policy.severity_overrides:
        if (
            _matches(fact.value_for(override.condition.metric), override.condition)
            and SEVERITY_RANK[override.severity] > SEVERITY_RANK[severity]
        ):
            severity = override.severity
    return severity


def _description(policy: PolicyDefinition, fact: Fact) -> str:
    value = fact.raw_value
    threshold = policy.condition.value
    if policy.id == "QA-BLOCKED-LONG":
        return (
            f"{fact.source_id} est bloqué depuis {float(value):.0f} h, au-delà du seuil "
            f"de {float(threshold):.0f} h."
        )
    if policy.id == "QA-TICKET-OVERDUE":
        due_date = fact.evidence["due_date"]
        return (
            f"{fact.source_id} est ouvert {int(float(value))} jour(s) après son échéance "
            f"du {due_date}."
        )
    if policy.id == "QA-CRITICAL-BUG-OPEN":
        return f"{fact.source_id} est un bug critique au statut {fact.evidence['status']}."
    if policy.id == "QA-PIPELINE-FAILED":
        return (
            f"Le dernier pipeline {fact.source_id} a échoué; la série atteint "
            f"{int(float(value))} échec(s) consécutif(s)."
        )
    if policy.id == "QA-COVERAGE-LOW":
        return (
            f"La couverture mesurée par {fact.source_id} est de {float(value):.1f} %, "
            f"sous le seuil de {float(threshold):.1f} %."
        )
    return (
        f"{policy.name}: {fact.source_type} {fact.source_id} viole "
        f"{policy.condition.metric} {policy.condition.operator} {threshold}."
    )


def evaluate_policy(policy: PolicyDefinition, facts: list[Fact]) -> list[Finding]:
    if not policy.enabled:
        return []
    findings = []
    for fact in facts:
        if fact.metric != policy.condition.metric:
            continue
        if not _matches(fact.raw_value, policy.condition):
            continue
        evidence = {
            **fact.evidence,
            "policy_id": policy.id,
            "policy_version": policy.version,
            "observed_value": fact.raw_value,
            "operator": policy.condition.operator,
            "threshold": policy.condition.value,
        }
        if policy.condition.metric == "blocked_hours":
            evidence["threshold_hours"] = policy.condition.value
        findings.append(
            Finding(
                rule_id=policy.id,
                policy_version=policy.version,
                factor=policy.condition.metric,
                title=policy.name,
                description=_description(policy, fact),
                severity=_severity(policy, fact),
                source_type=fact.source_type,
                source_id=fact.source_id,
                sprint_id=fact.sprint_id,
                evidence=evidence,
                recommendation=policy.recommendation,
                confidence=1.0,
                raw_value=fact.raw_value,
                observed_at=fact.observed_at,
                signal_strength=_normalize(policy, fact.raw_value),
            )
        )
    return findings
