from sqlalchemy import func, select

from app.dataset import load_dataset
from app.models import Recommendation, RecommendationTransition, Risk, RiskAnalysis
from app.novashop_history import HISTORY_END, HISTORY_START
from app.seed import seed_dataset


def _history(db_session) -> list[RiskAnalysis]:
    return list(
        db_session.scalars(
            select(RiskAnalysis)
            .where(
                RiskAnalysis.project_id == "PRJ-COPILOTE",
                RiskAnalysis.sprint_id.is_(None),
                RiskAnalysis.reference_date.between(HISTORY_START, HISTORY_END),
            )
            .order_by(RiskAnalysis.reference_date)
        )
    )


def _risk_policies(db_session, snapshot_id: str) -> set[str]:
    return set(
        db_session.scalars(
            select(Risk.rule_id).where(
                Risk.analysis_id == snapshot_id,
                Risk.status == "open",
            )
        )
    )


def test_novashop_seed_creates_a_deterministic_seven_day_history(db_session) -> None:
    result = seed_dataset(db_session, load_dataset("data/demo_dataset_v0.1.json"))
    snapshots = _history(db_session)

    assert result["history_snapshot_count"] == 7
    assert [snapshot.reference_date for snapshot in snapshots] == [
        HISTORY_START,
        HISTORY_START.replace(day=15),
        HISTORY_START.replace(day=16),
        HISTORY_START.replace(day=17),
        HISTORY_START.replace(day=18),
        HISTORY_START.replace(day=19),
        HISTORY_END,
    ]
    assert [snapshot.score for snapshot in snapshots] == [18, 36, 61, 82, 57, 32, 12]
    assert snapshots[0].previous_snapshot_id is None
    assert [snapshot.previous_snapshot_id for snapshot in snapshots[1:]] == [
        snapshot.id for snapshot in snapshots[:-1]
    ]


def test_history_demonstrates_new_resolved_and_aggravated_risks(db_session) -> None:
    seed_dataset(db_session, load_dataset("data/demo_dataset_v0.1.json"))
    snapshots = _history(db_session)
    policies = [_risk_policies(db_session, snapshot.id) for snapshot in snapshots]

    assert "QA-BLOCKED-LONG" in policies[1] - policies[0]
    assert "QA-CRITICAL-BUG-OPEN" in policies[3] - policies[2]
    assert "QA-COVERAGE-LOW" in policies[2] - policies[3]
    assert "QA-BLOCKED-LONG" in policies[3] - policies[4]
    assert snapshots[3].score > snapshots[2].score


def test_persistent_risks_reuse_one_active_recommendation_episode(db_session) -> None:
    seed_dataset(db_session, load_dataset("data/demo_dataset_v0.1.json"))
    recommendations = list(
        db_session.scalars(
            select(Recommendation)
            .where(Recommendation.project_id == "PRJ-COPILOTE")
            .order_by(Recommendation.policy_id)
        )
    )
    by_policy = {recommendation.policy_id: recommendation for recommendation in recommendations}

    assert len(recommendations) == 5
    assert by_policy["QA-TICKET-OVERDUE"].observation_count == 7
    assert by_policy["QA-TICKET-OVERDUE"].resolved_snapshot_id is None
    assert by_policy["QA-PIPELINE-FAILED"].observation_count == 4
    assert by_policy["QA-PIPELINE-FAILED"].source_risk_id != (
        by_policy["QA-PIPELINE-FAILED"].last_seen_risk_id
    )
    assert by_policy["QA-PIPELINE-FAILED"].resolved_snapshot_id == "QAH-NS-20260720"
    assert db_session.scalar(select(func.count()).select_from(RecommendationTransition)) == 5


def test_novashop_history_backfill_is_idempotent(db_session) -> None:
    dataset = load_dataset("data/demo_dataset_v0.1.json")
    first = seed_dataset(db_session, dataset)
    second = seed_dataset(db_session, dataset)

    assert first["status"] == "seeded"
    assert second["status"] == "already_seeded"
    assert second["history_snapshot_count"] == 7
    assert len(_history(db_session)) == 7
    assert db_session.scalar(select(func.count()).select_from(Recommendation)) == 5
