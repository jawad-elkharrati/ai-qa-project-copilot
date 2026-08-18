from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Recommendation,
    RecommendationOutcome,
    RecommendationTransition,
    Risk,
    RiskAnalysis,
    RiskContribution,
)
from app.recommendation_domain import RecommendationOutcomeStatus


class RecommendationOutcomeError(ValueError):
    pass


class RecommendationOutcomeNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class OutcomeObservation:
    id: str | None
    recommendation_id: str
    baseline_snapshot_id: str
    observed_snapshot_id: str
    status: str
    score_before: float
    score_after: float
    score_delta: float
    contributions_before: dict[str, float]
    contributions_after: dict[str, float]
    policies_before: list[str]
    policies_after: list[str]
    observation: str
    observed_at: object
    persisted: bool
    external_action_executed: bool = False


def _outcome_id(recommendation_id: str, observed_snapshot_id: str) -> str:
    digest = hashlib.sha256(f"{recommendation_id}|{observed_snapshot_id}".encode()).hexdigest()
    return f"ROU-{digest[:24].upper()}"


def _contributions(session: Session, snapshot_id: str) -> dict[str, float]:
    rows = session.scalars(
        select(RiskContribution).where(RiskContribution.analysis_id == snapshot_id)
    )
    return {row.policy_id: round(row.contribution, 3) for row in rows}


def _policies(session: Session, snapshot_id: str) -> list[str]:
    rows = session.scalars(
        select(Risk.rule_id).where(Risk.analysis_id == snapshot_id, Risk.status == "open")
    )
    return sorted(set(rows))


def _human_baseline_transition(
    session: Session, recommendation_id: str
) -> RecommendationTransition | None:
    return session.scalar(
        select(RecommendationTransition)
        .where(
            RecommendationTransition.recommendation_id == recommendation_id,
            RecommendationTransition.to_status.in_(("ACCEPTED", "MODIFIED")),
            RecommendationTransition.actor_role != "SYSTEM",
        )
        .order_by(RecommendationTransition.sequence)
        .limit(1)
    )


def _observed_snapshot(
    session: Session,
    recommendation: Recommendation,
    baseline: RiskAnalysis,
    observed_snapshot_id: str | None,
) -> RiskAnalysis | None:
    if observed_snapshot_id is not None:
        observed = session.get(RiskAnalysis, observed_snapshot_id)
        if observed is None:
            raise RecommendationOutcomeNotFoundError("observed snapshot not found")
        if (
            observed.project_id != recommendation.project_id
            or observed.sprint_id != recommendation.sprint_id
        ):
            raise RecommendationOutcomeError("observed snapshot is outside recommendation scope")
        if observed.reference_date <= baseline.reference_date:
            raise RecommendationOutcomeError(
                "observed snapshot must be after the baseline snapshot"
            )
        return observed
    return session.scalar(
        select(RiskAnalysis)
        .where(
            RiskAnalysis.project_id == recommendation.project_id,
            RiskAnalysis.sprint_id == recommendation.sprint_id,
            RiskAnalysis.reference_date > baseline.reference_date,
        )
        .order_by(RiskAnalysis.reference_date.desc(), RiskAnalysis.analyzed_at.desc())
        .limit(1)
    )


def _observation_from_snapshots(
    session: Session,
    recommendation: Recommendation,
    baseline: RiskAnalysis,
    observed: RiskAnalysis,
) -> tuple[
    RecommendationOutcomeStatus, str, dict[str, float], dict[str, float], list[str], list[str]
]:
    before = _contributions(session, baseline.id)
    after = _contributions(session, observed.id)
    policies_before = _policies(session, baseline.id)
    policies_after = _policies(session, observed.id)
    if baseline.missing_information or observed.missing_information:
        return (
            RecommendationOutcomeStatus.INSUFFICIENT_DATA,
            "Données insuffisantes pour comparer de façon fiable les observations avant et après.",
            before,
            after,
            policies_before,
            policies_after,
        )
    policy_improved = (
        recommendation.policy_id in policies_before
        and recommendation.policy_id not in policies_after
    ) or after.get(recommendation.policy_id, 0.0) < before.get(recommendation.policy_id, 0.0)
    if observed.score < baseline.score or policy_improved:
        return (
            RecommendationOutcomeStatus.IMPROVEMENT_OBSERVED,
            "Amélioration observée après la recommandation; aucune causalité n’est attribuée.",
            before,
            after,
            policies_before,
            policies_after,
        )
    return (
        RecommendationOutcomeStatus.NO_IMPROVEMENT_OBSERVED,
        "Aucune amélioration observée après la recommandation; aucune causalité n’est attribuée.",
        before,
        after,
        policies_before,
        policies_after,
    )


def _serialize(record: RecommendationOutcome) -> OutcomeObservation:
    return OutcomeObservation(
        id=record.id,
        recommendation_id=record.recommendation_id,
        baseline_snapshot_id=record.baseline_snapshot_id,
        observed_snapshot_id=record.observed_snapshot_id,
        status=record.status,
        score_before=record.score_before,
        score_after=record.score_after,
        score_delta=record.score_delta,
        contributions_before=record.contributions_before,
        contributions_after=record.contributions_after,
        policies_before=record.policies_before,
        policies_after=record.policies_after,
        observation=record.observation,
        observed_at=record.observed_at,
        persisted=True,
    )


def recommendation_outcome(
    session: Session,
    recommendation_id: str,
    observed_snapshot_id: str | None = None,
) -> OutcomeObservation:
    recommendation = session.get(Recommendation, recommendation_id)
    if recommendation is None:
        raise RecommendationOutcomeNotFoundError("recommendation not found")
    validation = _human_baseline_transition(session, recommendation_id)
    baseline_id = (
        validation.source_snapshot_id
        if validation is not None
        else recommendation.source_snapshot_id
    )
    baseline = session.get(RiskAnalysis, baseline_id)
    if baseline is None:
        raise RecommendationOutcomeNotFoundError("baseline snapshot not found")
    observed = _observed_snapshot(session, recommendation, baseline, observed_snapshot_id)
    if validation is None or observed is None:
        effective_observed = observed or baseline
        return OutcomeObservation(
            id=None,
            recommendation_id=recommendation.id,
            baseline_snapshot_id=baseline.id,
            observed_snapshot_id=effective_observed.id,
            status=RecommendationOutcomeStatus.NOT_YET_MEASURABLE.value,
            score_before=baseline.score,
            score_after=effective_observed.score,
            score_delta=round(effective_observed.score - baseline.score, 3),
            contributions_before=_contributions(session, baseline.id),
            contributions_after=_contributions(session, effective_observed.id),
            policies_before=_policies(session, baseline.id),
            policies_after=_policies(session, effective_observed.id),
            observation=(
                "Résultat non encore mesurable: validation humaine ou snapshot ultérieur absent."
            ),
            observed_at=effective_observed.analyzed_at,
            persisted=False,
        )
    existing = session.scalar(
        select(RecommendationOutcome).where(
            RecommendationOutcome.recommendation_id == recommendation.id,
            RecommendationOutcome.observed_snapshot_id == observed.id,
        )
    )
    if existing is not None:
        return _serialize(existing)
    status, observation, before, after, policies_before, policies_after = (
        _observation_from_snapshots(session, recommendation, baseline, observed)
    )
    record = RecommendationOutcome(
        id=_outcome_id(recommendation.id, observed.id),
        recommendation_id=recommendation.id,
        baseline_snapshot_id=baseline.id,
        observed_snapshot_id=observed.id,
        status=status.value,
        score_before=baseline.score,
        score_after=observed.score,
        score_delta=round(observed.score - baseline.score, 3),
        contributions_before=before,
        contributions_after=after,
        policies_before=policies_before,
        policies_after=policies_after,
        observation=observation,
        observed_at=observed.analyzed_at,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return _serialize(record)
