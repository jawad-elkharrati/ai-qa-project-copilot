from sqlalchemy import func, select

from app.dataset import load_dataset
from app.models import Recommendation, RecommendationOutcome, RiskAnalysis
from app.recommendation_domain import RecommendationOutcomeStatus, RecommendationStatus
from app.recommendation_outcome_service import (
    RecommendationOutcomeError,
    recommendation_outcome,
)
from app.recommendation_service import transition_recommendation
from app.seed import seed_dataset


def _seed(db_session) -> None:
    seed_dataset(db_session, load_dataset("data/demo_dataset_v0.1.json"))


def _recommendation(db_session, policy_id: str) -> Recommendation:
    return db_session.scalar(select(Recommendation).where(Recommendation.policy_id == policy_id))


def _accept(db_session, recommendation: Recommendation) -> None:
    transition_recommendation(
        db_session,
        recommendation_id=recommendation.id,
        to_status=RecommendationStatus.ACCEPTED,
        actor="qa.lead",
        actor_role="QA_LEAD",
        justification="Traitement manuel approuvé.",
        comment="Mesurer sur un snapshot ultérieur.",
    )


def test_outcome_is_not_measurable_before_human_validation(db_session) -> None:
    _seed(db_session)
    recommendation = _recommendation(db_session, "QA-PIPELINE-FAILED")

    result = recommendation_outcome(db_session, recommendation.id)

    assert result.status == RecommendationOutcomeStatus.NOT_YET_MEASURABLE
    assert result.persisted is False
    assert result.id is None
    assert result.external_action_executed is False
    assert db_session.scalar(select(func.count()).select_from(RecommendationOutcome)) == 0


def test_outcome_persists_observed_improvement_without_claiming_causality(db_session) -> None:
    _seed(db_session)
    recommendation = _recommendation(db_session, "QA-PIPELINE-FAILED")
    _accept(db_session, recommendation)

    first = recommendation_outcome(db_session, recommendation.id)
    second = recommendation_outcome(db_session, recommendation.id)

    assert first == second
    assert first.status == RecommendationOutcomeStatus.IMPROVEMENT_OBSERVED
    assert first.baseline_snapshot_id == "QAH-NS-20260719"
    assert first.observed_snapshot_id == "QAH-NS-20260720"
    assert first.score_before == 32
    assert first.score_after == 12
    assert first.score_delta == -20
    assert "aucune causalité" in first.observation
    assert first.persisted is True
    assert db_session.scalar(select(func.count()).select_from(RecommendationOutcome)) == 1


def test_outcome_reports_insufficient_data_from_snapshot_quality(db_session) -> None:
    _seed(db_session)
    recommendation = _recommendation(db_session, "QA-CRITICAL-BUG-OPEN")
    _accept(db_session, recommendation)
    observed = db_session.get(RiskAnalysis, "QAH-NS-20260720")
    observed.missing_information = [{"code": "coverage_missing"}]
    db_session.commit()

    result = recommendation_outcome(db_session, recommendation.id)

    assert result.status == RecommendationOutcomeStatus.INSUFFICIENT_DATA
    assert "Données insuffisantes" in result.observation


def test_outcome_rejects_snapshot_not_after_baseline(db_session) -> None:
    _seed(db_session)
    recommendation = _recommendation(db_session, "QA-PIPELINE-FAILED")
    _accept(db_session, recommendation)

    try:
        recommendation_outcome(
            db_session,
            recommendation.id,
            observed_snapshot_id="QAH-NS-20260719",
        )
    except RecommendationOutcomeError as exc:
        assert "must be after" in str(exc)
    else:
        raise AssertionError("an invalid observation window must be rejected")
