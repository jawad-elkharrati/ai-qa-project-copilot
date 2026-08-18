import pytest

from app.decision_domain import (
    DecisionResult,
    DecisionSignals,
    DecisionThresholds,
    HumanValidationStatus,
    QADecision,
)
from app.recommendation_domain import (
    RecommendationIdentity,
    RecommendationOutcomeStatus,
    RecommendationStatus,
    recommendation_key,
    risk_identity_key,
)


def test_week4_decision_values_and_human_governance_are_explicit():
    assert {decision.value for decision in QADecision} == {
        "GO",
        "GO_WITH_CONDITIONS",
        "NO_GO",
        "INSUFFICIENT_INFORMATION",
    }
    result = DecisionResult(
        suggested_decision=QADecision.GO,
        justification="Le risque est faible et les preuves sont suffisantes.",
        triggered_rules=("GO_LOW_CONTROLLED_RISK",),
    )

    assert result.human_validation_status is HumanValidationStatus.PENDING
    assert result.external_action_executed is False


def test_decision_thresholds_reject_overlapping_risk_bands():
    with pytest.raises(ValueError, match="risk thresholds"):
        DecisionThresholds(go_max_risk_score=70, conditional_max_risk_score=60)


def test_decision_signals_validate_normalized_inputs():
    with pytest.raises(ValueError, match="confidence_score"):
        DecisionSignals(
            project_id="project-novashop",
            snapshot_id="QAA-1",
            risk_score=20,
            confidence_score=1.1,
            evidence_coverage=0.9,
            data_freshness=0.9,
            active_risk_count=1,
        )


def test_recommendation_key_is_stable_across_snapshots_but_scope_is_not():
    risk_key = risk_identity_key(
        project_id="project-novashop",
        policy_id="QA-CRITICAL-BUG-OPEN",
        source_type="ticket",
        source_id="NS-42",
    )
    stable_key = recommendation_key(risk_key=risk_key)
    first = RecommendationIdentity(
        project_id="project-novashop",
        source_snapshot_id="QAA-DAY-1",
        source_risk_id="RSK-DAY-1",
        risk_key=risk_key,
        recommendation_key=stable_key,
    )
    second = RecommendationIdentity(
        project_id="project-novashop",
        source_snapshot_id="QAA-DAY-2",
        source_risk_id="RSK-DAY-2",
        risk_key=risk_key,
        recommendation_key=stable_key,
    )

    assert first.risk_key == second.risk_key
    assert first.recommendation_key == second.recommendation_key
    assert first.idempotency_scope != second.idempotency_scope


def test_recommendation_p1_lifecycle_adds_only_minimal_operational_state():
    assert {status.value for status in RecommendationStatus} == {
        "PROPOSED",
        "ACCEPTED",
        "MODIFIED",
        "REJECTED",
        "IN_PROGRESS",
        "COMPLETED",
    }
    assert "EXPIRED" not in RecommendationStatus.__members__
    assert RecommendationOutcomeStatus.NOT_YET_MEASURABLE.value == "NOT_YET_MEASURABLE"
