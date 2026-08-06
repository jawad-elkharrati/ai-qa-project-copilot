from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models import (
    Project,
    Recommendation,
    Risk,
    RiskAnalysis,
    RiskDecision,
)
from app.recommendation_domain import (
    RecommendationEffort,
    RecommendationImpact,
    RecommendationPriority,
    RecommendationStatus,
    RecommendationUrgency,
)
from app.recommendation_service import (
    RecommendationError,
    prioritize_recommendation,
    recommendation_history,
    sync_recommendations_for_snapshot,
    transition_recommendation,
)


def add_project(db_session) -> None:
    db_session.add(
        Project(
            id="PRJ-NS",
            key="NS",
            name="NovaShop",
            description="Demo",
            repository_url=None,
            created_at=datetime(2026, 7, 20, tzinfo=UTC),
        )
    )
    db_session.flush()


def add_snapshot(db_session, day: int, score: float = 40) -> RiskAnalysis:
    observed = datetime(2026, 7, 20, tzinfo=UTC) + timedelta(days=day)
    previous_id = f"QAA-D{day - 1}" if day > 1 else None
    analysis = RiskAnalysis(
        id=f"QAA-D{day}",
        project_id="PRJ-NS",
        sprint_id=None,
        ruleset_version="qa-rules-v1.0",
        reference_date=observed.date(),
        score=score,
        severity="high" if score >= 45 else "medium",
        breakdown=[],
        finding_count=0,
        agent_name="qa-agent-v1",
        analyzed_at=observed,
        policy_hash="policy",
        input_fingerprint=f"input-{day}",
        result_fingerprint=f"result-{day}",
        previous_snapshot_id=previous_id,
        confidence_score=0.9,
        evidence_coverage=0.9,
        missing_information=[],
        stale_information=[],
        confidence_details={"components": {"freshness_coverage": 1.0}},
    )
    db_session.add(analysis)
    db_session.flush()
    return analysis


def add_risk(
    db_session,
    analysis: RiskAnalysis,
    *,
    suffix: str,
    severity: str = "high",
) -> Risk:
    risk = Risk(
        id=f"RSK-{suffix}",
        analysis_id=analysis.id,
        project_id=analysis.project_id,
        sprint_id=None,
        rule_id="QA-PIPELINE-FAILED",
        title="Pipeline en ?chec",
        description=f"?chec observ? dans {suffix}",
        severity=severity,
        priority=1 if severity == "critical" else 2,
        score=100 if severity == "critical" else 75,
        confidence=0.9,
        source_type="build",
        source_id="PIPELINE-MAIN",
        evidence={"build": suffix},
        recommendation="Corriger puis relancer le pipeline.",
        requires_human_validation=True,
        status="open",
        detected_at=analysis.analyzed_at,
    )
    db_session.add(risk)
    db_session.flush()
    analysis.finding_count += 1
    return risk


def test_persistent_risk_reuses_active_recommendation_across_snapshots(db_session):
    add_project(db_session)
    day1 = add_snapshot(db_session, 1)
    first_risk = add_risk(db_session, day1, suffix="D1")
    first = sync_recommendations_for_snapshot(db_session, day1.id)
    recommendation = db_session.get(Recommendation, first.created_ids[0])
    original = dict(recommendation.original_payload)

    day2 = add_snapshot(db_session, 2, score=55)
    second_risk = add_risk(db_session, day2, suffix="D2", severity="critical")
    second = sync_recommendations_for_snapshot(db_session, day2.id)
    db_session.refresh(recommendation)

    assert second.created_ids == ()
    assert second.reused_ids == (recommendation.id,)
    assert recommendation.source_snapshot_id == day1.id
    assert recommendation.source_risk_id == first_risk.id
    assert recommendation.last_seen_snapshot_id == day2.id
    assert recommendation.last_seen_risk_id == second_risk.id
    assert recommendation.observation_count == 2
    assert recommendation.latest_severity == "critical"
    assert recommendation.latest_evidence == [{"build": "D2"}]
    assert recommendation.original_payload == original
    assert len(recommendation_history(db_session, recommendation.id)) == 1


def test_same_snapshot_sync_is_idempotent(db_session):
    add_project(db_session)
    snapshot = add_snapshot(db_session, 1)
    add_risk(db_session, snapshot, suffix="D1")

    first = sync_recommendations_for_snapshot(db_session, snapshot.id)
    second = sync_recommendations_for_snapshot(db_session, snapshot.id)
    recommendation = db_session.get(Recommendation, first.created_ids[0])

    assert second.created_ids == ()
    assert second.reused_ids == (recommendation.id,)
    assert recommendation.observation_count == 1
    assert db_session.scalar(select(func.count()).select_from(Recommendation)) == 1


def test_resolved_risk_reappearance_creates_new_episode(db_session):
    add_project(db_session)
    day1 = add_snapshot(db_session, 1)
    add_risk(db_session, day1, suffix="D1")
    first = sync_recommendations_for_snapshot(db_session, day1.id)

    day2 = add_snapshot(db_session, 2, score=5)
    resolved = sync_recommendations_for_snapshot(db_session, day2.id)
    old = db_session.get(Recommendation, first.created_ids[0])

    day3 = add_snapshot(db_session, 3)
    add_risk(db_session, day3, suffix="D3")
    recurrence = sync_recommendations_for_snapshot(db_session, day3.id)
    new = db_session.get(Recommendation, recurrence.created_ids[0])

    assert resolved.resolved_ids == (old.id,)
    assert old.resolved_snapshot_id == day2.id
    assert new.id != old.id
    assert new.risk_key == old.risk_key
    assert new.source_snapshot_id == day3.id
    assert new.observation_count == 1


def test_human_transition_is_append_only_and_preserves_s3_decision(db_session):
    add_project(db_session)
    snapshot = add_snapshot(db_session, 1)
    risk = add_risk(db_session, snapshot, suffix="D1")
    sync = sync_recommendations_for_snapshot(db_session, snapshot.id)
    legacy = RiskDecision(
        id="RDC-S3",
        risk_id=risk.id,
        analysis_id=snapshot.id,
        policy_id=risk.rule_id,
        status="accepted",
        original_recommendation="D?cision S3",
        modified_recommendation=None,
        comment="Historique S3",
        decided_by="legacy-manager",
        decided_at=snapshot.analyzed_at,
        created_at=snapshot.analyzed_at,
        previous_decision_id=None,
    )
    db_session.add(legacy)
    db_session.commit()

    transition = transition_recommendation(
        db_session,
        recommendation_id=sync.created_ids[0],
        to_status=RecommendationStatus.ACCEPTED,
        actor="qa-manager",
        actor_role="QA_MANAGER",
        justification="Le plan r?duit le risque identifi?.",
        comment="Accept? pour traitement manuel.",
    )

    history = recommendation_history(db_session, sync.created_ids[0])
    assert [item.to_status for item in history] == ["PROPOSED", "ACCEPTED"]
    assert transition.actor == "qa-manager"
    assert transition.actor_role == "QA_MANAGER"
    assert transition.external_action_executed is False
    assert db_session.get(RiskDecision, "RDC-S3").original_recommendation == "D?cision S3"


def test_modification_keeps_original_payload_and_records_before_after(db_session):
    add_project(db_session)
    snapshot = add_snapshot(db_session, 1)
    add_risk(db_session, snapshot, suffix="D1")
    sync = sync_recommendations_for_snapshot(db_session, snapshot.id)
    recommendation = db_session.get(Recommendation, sync.created_ids[0])
    original = dict(recommendation.original_payload)

    transition = transition_recommendation(
        db_session,
        recommendation_id=recommendation.id,
        to_status=RecommendationStatus.MODIFIED,
        actor="project-lead",
        actor_role="PROJECT_MANAGER",
        justification="Adaptation au calendrier de release.",
        changes={
            "description": "Corriger le pipeline et ajouter un test cibl?.",
            "due_date": "2026-07-25",
        },
    )

    assert recommendation.original_payload == original
    assert transition.previous_payload["description"] == "Corriger puis relancer le pipeline."
    assert transition.resulting_payload["description"] == (
        "Corriger le pipeline et ajouter un test cibl?."
    )
    assert transition.resulting_payload["due_date"] == "2026-07-25"


def test_rejection_requires_comment_and_terminal_transition_is_enforced(db_session):
    add_project(db_session)
    snapshot = add_snapshot(db_session, 1)
    add_risk(db_session, snapshot, suffix="D1")
    sync = sync_recommendations_for_snapshot(db_session, snapshot.id)

    with pytest.raises(RecommendationError, match="comment is required"):
        transition_recommendation(
            db_session,
            recommendation_id=sync.created_ids[0],
            to_status=RecommendationStatus.REJECTED,
            actor="qa-manager",
            actor_role="QA_MANAGER",
            justification="Risque accept? par le m?tier.",
        )

    transition_recommendation(
        db_session,
        recommendation_id=sync.created_ids[0],
        to_status=RecommendationStatus.REJECTED,
        actor="qa-manager",
        actor_role="QA_MANAGER",
        justification="Risque accept? par le m?tier.",
        comment="Le risque est document? et accept?.",
    )
    with pytest.raises(RecommendationError, match="is not allowed"):
        transition_recommendation(
            db_session,
            recommendation_id=sync.created_ids[0],
            to_status=RecommendationStatus.ACCEPTED,
            actor="qa-manager",
            actor_role="QA_MANAGER",
            justification="Changement tardif.",
        )


def test_operational_lifecycle_is_append_only_and_completion_requires_comment(db_session):
    add_project(db_session)
    snapshot = add_snapshot(db_session, 1)
    add_risk(db_session, snapshot, suffix="D1")
    sync = sync_recommendations_for_snapshot(db_session, snapshot.id)
    recommendation_id = sync.created_ids[0]

    transition_recommendation(
        db_session,
        recommendation_id=recommendation_id,
        to_status=RecommendationStatus.ACCEPTED,
        actor="qa-manager",
        actor_role="QA_MANAGER",
        justification="Traitement approuvé.",
    )
    started = transition_recommendation(
        db_session,
        recommendation_id=recommendation_id,
        to_status=RecommendationStatus.IN_PROGRESS,
        actor="qa-engineer",
        actor_role="QA_ENGINEER",
        justification="Traitement démarré.",
        changes={"assigned_to": "qa-engineer", "due_date": "2026-07-28"},
    )
    with pytest.raises(RecommendationError, match="comment is required"):
        transition_recommendation(
            db_session,
            recommendation_id=recommendation_id,
            to_status=RecommendationStatus.COMPLETED,
            actor="qa-engineer",
            actor_role="QA_ENGINEER",
            justification="Traitement terminé.",
        )
    completed = transition_recommendation(
        db_session,
        recommendation_id=recommendation_id,
        to_status=RecommendationStatus.COMPLETED,
        actor="qa-engineer",
        actor_role="QA_ENGINEER",
        justification="Traitement terminé.",
        comment="Correction vérifiée localement; aucune action externe exécutée.",
    )

    recommendation = db_session.get(Recommendation, recommendation_id)
    assert recommendation.assigned_to == "qa-engineer"
    assert recommendation.due_date.isoformat() == "2026-07-28"
    assert started.external_action_executed is False
    assert completed.external_action_executed is False
    assert [item.to_status for item in recommendation_history(db_session, recommendation_id)] == [
        "PROPOSED",
        "ACCEPTED",
        "IN_PROGRESS",
        "COMPLETED",
    ]


def test_priority_formula_is_bounded_and_explained():
    result = prioritize_recommendation(
        severity="critical",
        confidence=1,
        impact=RecommendationImpact.HIGH,
        effort=RecommendationEffort.LOW,
        urgency=RecommendationUrgency.IMMEDIATE,
        blocking=True,
        affected_risk_count=5,
    )

    assert result.score == 100
    assert result.priority is RecommendationPriority.CRITICAL
    assert result.factors == {
        "severity": 30,
        "blocking": 20,
        "impact": 15,
        "urgency": 15,
        "confidence": 10,
        "effort": 5,
        "affected_risks": 5,
    }
    assert "score 100/100" in result.justification
