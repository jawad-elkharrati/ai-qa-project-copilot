from datetime import UTC, date, datetime

import pytest

from app.decision_domain import DecisionSignals, DecisionThresholds, QADecision
from app.decision_engine import evaluate_decision
from app.decision_signal_service import (
    DecisionSnapshotNotFoundError,
    signals_from_snapshot,
)
from app.models import Metric, Project, Risk, RiskAnalysis


def signals(**overrides) -> DecisionSignals:
    values = {
        "project_id": "PRJ-NS",
        "snapshot_id": "QAA-NS",
        "risk_score": 10.0,
        "confidence_score": 0.9,
        "evidence_coverage": 0.9,
        "data_freshness": 1.0,
        "active_risk_count": 0,
        "test_coverage_percent": 82.0,
    }
    values.update(overrides)
    return DecisionSignals(**values)


def test_go_requires_low_risk_and_sufficient_evidence():
    result = evaluate_decision(signals())

    assert result.suggested_decision is QADecision.GO
    assert result.triggered_rules == ("GO_LOW_CONTROLLED_RISK",)
    assert "10.0/100" in result.justification
    assert result.external_action_executed is False


def test_go_with_conditions_lists_each_controllable_issue():
    result = evaluate_decision(
        signals(
            risk_score=45,
            active_risk_count=2,
            violated_policy_ids=("QA-COVERAGE-LOW", "QA-TICKET-OVERDUE"),
            test_coverage_percent=62,
            overdue_ticket_count=1,
        )
    )

    assert result.suggested_decision is QADecision.GO_WITH_CONDITIONS
    assert result.triggered_rules == (
        "CONDITIONAL_ELEVATED_RISK_SCORE",
        "CONDITIONAL_POLICY_VIOLATIONS",
        "CONDITIONAL_LOW_TEST_COVERAGE",
        "CONDITIONAL_OVERDUE_TICKETS",
    )
    assert any("62.0%" in condition for condition in result.conditions)


def test_no_go_justification_names_critical_observed_blockers():
    result = evaluate_decision(
        signals(
            risk_score=70,
            active_risk_count=2,
            critical_risk_count=2,
            blocking_risk_ids=("RSK-BUG", "RSK-CI"),
            blocking_policy_ids=("QA-CRITICAL-BUG-OPEN", "QA-PIPELINE-FAILED"),
            critical_ci_failure=True,
            open_critical_bug_count=1,
            test_coverage_percent=48,
        )
    )

    assert result.suggested_decision is QADecision.NO_GO
    assert "pipeline CI principal" in result.justification
    assert "1 bug(s) critique(s)" in result.justification
    assert "QA-CRITICAL-BUG-OPEN" in result.justification


def test_known_blocker_takes_precedence_over_low_information_quality():
    result = evaluate_decision(
        signals(
            confidence_score=0.2,
            evidence_coverage=0.2,
            data_freshness=0.0,
            critical_risk_count=1,
            blocking_risk_ids=("RSK-CRITICAL",),
            test_coverage_percent=None,
            missing_information=("builds_missing",),
        )
    )

    assert result.suggested_decision is QADecision.NO_GO
    assert "NO_GO_CRITICAL_RISK" in result.triggered_rules


def test_insufficient_information_explains_each_quality_gate():
    result = evaluate_decision(
        signals(
            confidence_score=0.4,
            evidence_coverage=0.5,
            data_freshness=0.3,
            test_coverage_percent=None,
            missing_information=("coverage_metric_missing",),
        )
    )

    assert result.suggested_decision is QADecision.INSUFFICIENT_INFORMATION
    assert result.triggered_rules == (
        "INSUFFICIENT_LOW_CONFIDENCE",
        "INSUFFICIENT_EVIDENCE_COVERAGE",
        "INSUFFICIENT_DATA_FRESHNESS",
        "INSUFFICIENT_TEST_COVERAGE_MISSING",
        "INSUFFICIENT_MISSING_INFORMATION",
    )
    assert "couverture de tests absente" in result.justification


def test_high_score_is_no_go_after_information_gate_passes():
    result = evaluate_decision(signals(risk_score=61))

    assert result.suggested_decision is QADecision.NO_GO
    assert result.triggered_rules == ("NO_GO_HIGH_RISK_SCORE",)


def test_thresholds_are_configurable_and_evaluation_is_deterministic():
    configured = DecisionThresholds(go_max_risk_score=35, conditional_max_risk_score=75)
    input_signals = signals(risk_score=30)

    assert evaluate_decision(input_signals, configured) == evaluate_decision(
        input_signals, configured
    )
    assert evaluate_decision(input_signals, configured).suggested_decision is QADecision.GO


def test_snapshot_adapter_uses_persisted_quality_and_project_facts(db_session):
    now = datetime(2026, 7, 30, 12, tzinfo=UTC)
    db_session.add(
        Project(
            id="PRJ-NS",
            key="NS",
            name="NovaShop",
            description="Demo",
            repository_url=None,
            created_at=now,
        )
    )
    db_session.flush()
    db_session.add(
        RiskAnalysis(
            id="QAA-NS",
            project_id="PRJ-NS",
            sprint_id=None,
            ruleset_version="qa-rules-v1.0",
            reference_date=date(2026, 7, 30),
            score=80,
            severity="critical",
            breakdown=[],
            finding_count=1,
            agent_name="qa-agent-v1",
            analyzed_at=now,
            policy_hash="policy",
            input_fingerprint="input",
            result_fingerprint="result",
            previous_snapshot_id=None,
            confidence_score=0.9,
            evidence_coverage=0.85,
            missing_information=[],
            stale_information=[],
            confidence_details={"components": {"freshness_coverage": 1.0}},
        )
    )
    db_session.flush()
    db_session.add(
        Risk(
            id="RSK-CI",
            analysis_id="QAA-NS",
            project_id="PRJ-NS",
            sprint_id=None,
            rule_id="QA-PIPELINE-FAILED",
            title="Pipeline critique",
            description="Deux ?checs cons?cutifs",
            severity="critical",
            priority=1,
            score=100,
            confidence=0.9,
            source_type="build",
            source_id="BLD-2",
            evidence={},
            recommendation="Corriger le pipeline.",
            requires_human_validation=True,
            status="open",
            detected_at=now,
        )
    )
    db_session.add(
        Metric(
            id="MET-COV",
            project_id="PRJ-NS",
            sprint_id=None,
            name="test_coverage",
            value=66,
            unit="percent",
            source="novashop",
            measured_at=now,
        )
    )
    db_session.commit()

    result = signals_from_snapshot(db_session, "QAA-NS")

    assert result.critical_ci_failure is True
    assert result.blocking_policy_ids == ("QA-PIPELINE-FAILED",)
    assert result.test_coverage_percent == 66
    assert result.data_freshness == 1.0


def test_snapshot_adapter_fails_cleanly_for_unknown_snapshot(db_session):
    with pytest.raises(DecisionSnapshotNotFoundError, match="snapshot not found"):
        signals_from_snapshot(db_session, "QAA-UNKNOWN")
