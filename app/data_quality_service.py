from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PullRequest, TestResult
from app.qa_domain import RuleContext
from app.time_utils import require_utc_datetime

FRESHNESS_DAYS = 14


@dataclass(frozen=True)
class DataQualityAssessment:
    confidence_score: float
    evidence_coverage: float
    missing_information: list[dict[str, object]]
    stale_information: list[dict[str, object]]
    details: dict[str, object]


def _scope_reference_date(context: RuleContext) -> date:
    if context.sprint_id is None:
        return context.reference_date
    sprint = next(
        (item for item in context.sprints if item.id == context.sprint_id),
        None,
    )
    return min(context.reference_date, sprint.end_date) if sprint else context.reference_date


def _missing(code: str, label: str, source_type: str, detail: str) -> dict[str, object]:
    return {
        "code": code,
        "label": label,
        "source_type": source_type,
        "detail": detail,
    }


def assess_data_quality(
    session: Session,
    context: RuleContext,
) -> DataQualityAssessment:
    """Compute a transparent coverage indicator, not an incident probability."""

    missing: list[dict[str, object]] = []
    stale: list[dict[str, object]] = []
    builds = [
        build
        for build in context.builds
        if require_utc_datetime(build.started_at).date() <= context.reference_date
    ]
    coverage_metrics = [
        metric
        for metric in context.metrics
        if metric.name == "test_coverage"
        and require_utc_datetime(metric.measured_at).date() <= context.reference_date
    ]
    build_ids = {build.id for build in builds}
    test_build_ids = (
        set(session.scalars(select(TestResult.build_id).where(TestResult.build_id.in_(build_ids))))
        if build_ids
        else set()
    )
    pr_ids = {build.pull_request_id for build in builds if build.pull_request_id}
    resolved_pr_ids = (
        set(session.scalars(select(PullRequest.id).where(PullRequest.id.in_(pr_ids))))
        if pr_ids
        else set()
    )
    resolved_build_pr_count = sum(1 for build in builds if build.pull_request_id in resolved_pr_ids)

    source_components = {
        "tickets": 1.0 if context.tickets else 0.0,
        "builds": 1.0 if builds else 0.0,
        "test_results": len(test_build_ids) / len(build_ids) if build_ids else 0.0,
        "test_coverage": 1.0 if coverage_metrics else 0.0,
    }
    if not context.tickets:
        missing.append(
            _missing(
                "tickets_missing",
                "Tickets du périmètre",
                "ticket",
                "Aucun ticket n'est disponible pour le périmètre analysé.",
            )
        )
    if not builds:
        missing.append(
            _missing(
                "builds_missing",
                "Historique de builds",
                "build",
                "Aucun build n'est disponible à la date de référence.",
            )
        )
    if build_ids and len(test_build_ids) < len(build_ids):
        missing.append(
            _missing(
                "test_results_incomplete",
                "Résultats de tests",
                "test_result",
                f"{len(build_ids) - len(test_build_ids)} build(s) sans résultat de tests.",
            )
        )
    elif not build_ids:
        missing.append(
            _missing(
                "test_results_missing",
                "Résultats de tests",
                "test_result",
                "Les résultats ne peuvent pas être reliés sans build.",
            )
        )
    if not coverage_metrics:
        missing.append(
            _missing(
                "coverage_metric_missing",
                "Couverture de tests",
                "metric",
                "Aucune métrique de couverture n'est disponible.",
            )
        )

    build_pr_coverage = resolved_build_pr_count / len(builds) if builds else 0.0
    build_test_coverage = len(test_build_ids) / len(builds) if builds else 0.0
    relation_components = {
        "build_to_pull_request": build_pr_coverage,
        "build_to_test_result": build_test_coverage,
    }
    if builds and build_pr_coverage < 1:
        missing.append(
            _missing(
                "build_pr_relations_incomplete",
                "Relations build vers pull request",
                "relation",
                f"{len(builds) - resolved_build_pr_count} relation(s) non résolue(s).",
            )
        )

    scope_reference = _scope_reference_date(context)
    freshness_components = {"builds": 0.0, "test_coverage": 0.0}
    if builds:
        latest_build = max(builds, key=lambda item: require_utc_datetime(item.started_at))
        latest_build_at = require_utc_datetime(latest_build.started_at)
        build_age = max((scope_reference - latest_build_at.date()).days, 0)
        freshness_components["builds"] = 1.0 if build_age <= FRESHNESS_DAYS else 0.0
        if build_age > FRESHNESS_DAYS:
            stale.append(
                {
                    "code": "builds_stale",
                    "source_type": "build",
                    "source_id": latest_build.id,
                    "age_days": build_age,
                    "threshold_days": FRESHNESS_DAYS,
                }
            )
    if coverage_metrics:
        latest_metric = max(
            coverage_metrics,
            key=lambda item: require_utc_datetime(item.measured_at),
        )
        latest_metric_at = require_utc_datetime(latest_metric.measured_at)
        metric_age = max((scope_reference - latest_metric_at.date()).days, 0)
        freshness_components["test_coverage"] = 1.0 if metric_age <= FRESHNESS_DAYS else 0.0
        if metric_age > FRESHNESS_DAYS:
            stale.append(
                {
                    "code": "coverage_metric_stale",
                    "source_type": "metric",
                    "source_id": latest_metric.id,
                    "age_days": metric_age,
                    "threshold_days": FRESHNESS_DAYS,
                }
            )

    source_coverage = sum(source_components.values()) / len(source_components)
    freshness_coverage = sum(freshness_components.values()) / len(freshness_components)
    relation_coverage = sum(relation_components.values()) / len(relation_components)
    confidence = round(
        0.6 * source_coverage + 0.2 * freshness_coverage + 0.2 * relation_coverage,
        2,
    )
    evidence_coverage = round((source_coverage + relation_coverage) / 2, 2)
    return DataQualityAssessment(
        confidence_score=confidence,
        evidence_coverage=evidence_coverage,
        missing_information=missing,
        stale_information=stale,
        details={
            "method": "deterministic-data-coverage-v1",
            "is_probability": False,
            "weights": {
                "source_coverage": 0.6,
                "freshness_coverage": 0.2,
                "relation_coverage": 0.2,
            },
            "components": {
                "source_coverage": round(source_coverage, 3),
                "freshness_coverage": round(freshness_coverage, 3),
                "relation_coverage": round(relation_coverage, 3),
            },
            "source_checks": source_components,
            "freshness_checks": freshness_components,
            "relation_checks": relation_components,
        },
    )
