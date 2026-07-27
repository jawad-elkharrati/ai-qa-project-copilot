from datetime import UTC, datetime

import pytest

from app.qa_domain import Finding
from app.qa_scoring import calculate_risk_score


def finding(
    rule_id: str,
    signal: float,
    source_id: str = "SRC-001",
) -> Finding:
    return Finding(
        rule_id=rule_id,
        policy_version=1,
        factor="test_factor",
        title="Test",
        description="Test",
        severity="high",
        source_type="ticket",
        source_id=source_id,
        sprint_id="SPR-001",
        evidence={"value": signal},
        recommendation="Valider humainement.",
        confidence=1.0,
        raw_value=signal,
        observed_at=datetime(2026, 7, 13, tzinfo=UTC),
        signal_strength=signal,
    )


def test_score_is_strictly_bounded_for_invalid_negative_signal() -> None:
    score, severity, breakdown = calculate_risk_score([finding("QA-BLOCKED-LONG", -10)])

    assert (score, severity) == (0.0, "low")
    assert breakdown[0]["normalized_value"] == 0.0
    assert breakdown[0]["contribution"] == 0.0


def test_policy_contribution_is_capped_and_explained() -> None:
    findings = [finding("QA-TICKET-OVERDUE", 0.9, f"TKT-{index:03d}") for index in range(10)]

    score, _, breakdown = calculate_risk_score(findings)
    overdue = next(item for item in breakdown if item["policy_id"] == "QA-TICKET-OVERDUE")

    assert score == 15.0
    assert overdue["normalized_value"] == 1.0
    assert overdue["contribution"] == overdue["weight"] == 15.0
    assert overdue["source_ids"] == sorted(overdue["source_ids"])
    assert "10 constat(s)" in overdue["explanation"]


def test_unknown_policy_finding_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown policies"):
        calculate_risk_score([finding("QA-UNKNOWN", 1.0)])


def test_finding_order_does_not_change_the_score_or_breakdown() -> None:
    findings = [
        finding("QA-BLOCKED-LONG", 0.7, "TKT-002"),
        finding("QA-BLOCKED-LONG", 0.8, "TKT-001"),
        finding("QA-COVERAGE-LOW", 0.5, "MET-001"),
    ]

    forward = calculate_risk_score(findings)
    backward = calculate_risk_score(list(reversed(findings)))

    assert forward == backward
    assert round(sum(item["contribution"] for item in forward[2]), 1) == forward[0]
