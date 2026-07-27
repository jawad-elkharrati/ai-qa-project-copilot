from datetime import UTC, date, datetime

import pytest

from app.models import Risk, RiskAnalysis
from app.release_readiness_service import release_readiness


def analysis(
    *,
    severity: str = "low",
    confidence: float = 1.0,
    missing: list | None = None,
) -> RiskAnalysis:
    return RiskAnalysis(
        id="QAA-TEST",
        project_id="PRJ-TEST",
        sprint_id="SPR-TEST",
        ruleset_version="qa-rules-v1.0",
        reference_date=date(2026, 7, 13),
        score=0,
        severity=severity,
        breakdown=[],
        finding_count=0,
        agent_name="qa-agent-v1",
        analyzed_at=datetime(2026, 7, 13, tzinfo=UTC),
        policy_hash="hash",
        input_fingerprint="input",
        result_fingerprint="result",
        confidence_score=confidence,
        evidence_coverage=confidence,
        missing_information=missing or [],
        stale_information=[],
        confidence_details={},
    )


def risk(severity: str) -> Risk:
    return Risk(
        id=f"RSK-{severity}",
        analysis_id="QAA-TEST",
        project_id="PRJ-TEST",
        sprint_id="SPR-TEST",
        rule_id="QA-TEST",
        title="Risque de test",
        description="Description",
        severity=severity,
        priority=1 if severity == "critical" else 3,
        score=25,
        confidence=1,
        source_type="ticket",
        source_id="TKT-001",
        evidence={},
        recommendation="Faire valider le correctif.",
        requires_human_validation=True,
        status="open",
        detected_at=datetime(2026, 7, 13, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("snapshot", "risks", "pending", "expected"),
    [
        (analysis(), [], 0, "GO"),
        (analysis(severity="medium"), [risk("medium")], 1, "GO WITH CONDITIONS"),
        (analysis(severity="critical"), [risk("critical")], 1, "NO-GO"),
        (
            analysis(
                confidence=0.5,
                missing=[{"code": "coverage_metric_missing"}],
            ),
            [],
            0,
            "INSUFFICIENT INFORMATION",
        ),
    ],
)
def test_release_readiness_is_deterministic_and_advisory(
    snapshot, risks, pending: int, expected: str
) -> None:
    first = release_readiness(snapshot, risks, pending)
    second = release_readiness(snapshot, risks, pending)

    assert first == second
    assert first["decision"] == expected
    assert first["advisory_only"] is True
    assert first["human_validation_required"] is True
