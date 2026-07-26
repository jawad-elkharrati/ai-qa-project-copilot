from __future__ import annotations

from datetime import UTC, datetime

from app.qa_domain import Fact, RuleContext
from app.time_utils import require_utc_datetime


def _sprint_index(context: RuleContext):
    return {sprint.id: sprint for sprint in context.sprints}


def _ticket_facts(context: RuleContext) -> list[Fact]:
    facts: list[Fact] = []
    sprint_by_id = _sprint_index(context)
    reference = datetime.combine(context.reference_date, datetime.min.time(), tzinfo=UTC)
    for ticket in context.tickets:
        if require_utc_datetime(ticket.created_at).date() > context.reference_date:
            continue
        sprint = sprint_by_id.get(ticket.sprint_id or "")
        active_high_priority = bool(
            sprint is not None
            and sprint.status == "active"
            and ticket.priority in {"high", "critical"}
        )
        attributes: dict[str, bool | float | str] = {
            "active_high_priority": active_high_priority,
        }
        if ticket.status == "blocked" and ticket.blocked_since is not None:
            blocked_since = require_utc_datetime(ticket.blocked_since)
            hours = (reference - blocked_since).total_seconds() / 3600
            facts.append(
                Fact(
                    metric="blocked_hours",
                    raw_value=round(hours, 6),
                    source_type="ticket",
                    source_id=ticket.id,
                    sprint_id=ticket.sprint_id,
                    observed_at=blocked_since,
                    evidence={
                        "status": ticket.status,
                        "priority": ticket.priority,
                        "blocked_since": blocked_since.isoformat(),
                        "reference_date": context.reference_date.isoformat(),
                        "blocked_hours": round(hours, 1),
                    },
                    attributes=attributes,
                )
            )
        if ticket.status != "done" and ticket.due_date is not None:
            days = (context.reference_date - ticket.due_date).days
            facts.append(
                Fact(
                    metric="overdue_days",
                    raw_value=float(days),
                    source_type="ticket",
                    source_id=ticket.id,
                    sprint_id=ticket.sprint_id,
                    observed_at=require_utc_datetime(ticket.updated_at),
                    evidence={
                        "status": ticket.status,
                        "priority": ticket.priority,
                        "due_date": ticket.due_date.isoformat(),
                        "reference_date": context.reference_date.isoformat(),
                        "overdue_days": days,
                    },
                    attributes=attributes,
                )
            )
        if ticket.type == "bug" and ticket.priority == "critical" and ticket.status != "done":
            facts.append(
                Fact(
                    metric="open_critical_bug",
                    raw_value=True,
                    source_type="ticket",
                    source_id=ticket.id,
                    sprint_id=ticket.sprint_id,
                    observed_at=require_utc_datetime(ticket.updated_at),
                    evidence={
                        "type": ticket.type,
                        "priority": ticket.priority,
                        "status": ticket.status,
                        "title": ticket.title,
                    },
                    attributes=attributes,
                )
            )
    return facts


def _build_facts(context: RuleContext) -> list[Fact]:
    grouped: dict[str | None, list] = {}
    for build in context.builds:
        if require_utc_datetime(build.started_at).date() <= context.reference_date:
            grouped.setdefault(build.sprint_id, []).append(build)

    facts: list[Fact] = []
    for sprint_id, builds in grouped.items():
        ordered = sorted(builds, key=lambda build: require_utc_datetime(build.started_at))
        latest = ordered[-1]
        streak = 0
        for build in reversed(ordered):
            if build.status != "failed":
                break
            streak += 1
        facts.append(
            Fact(
                metric="consecutive_failed_builds",
                raw_value=float(streak),
                source_type="build",
                source_id=latest.id,
                sprint_id=sprint_id,
                observed_at=require_utc_datetime(latest.started_at),
                evidence={
                    "pipeline_name": latest.pipeline_name,
                    "branch": latest.branch,
                    "latest_status": latest.status,
                    "consecutive_failures": streak,
                    "recent_builds": [
                        {
                            "id": build.id,
                            "status": build.status,
                            "started_at": require_utc_datetime(build.started_at).isoformat(),
                        }
                        for build in ordered[-3:]
                    ],
                },
            )
        )
    return facts


def _metric_facts(context: RuleContext) -> list[Fact]:
    latest_by_sprint = {}
    for metric in context.metrics:
        if (
            metric.name != "test_coverage"
            or require_utc_datetime(metric.measured_at).date() > context.reference_date
        ):
            continue
        current = latest_by_sprint.get(metric.sprint_id)
        if current is None or require_utc_datetime(metric.measured_at) > require_utc_datetime(
            current.measured_at
        ):
            latest_by_sprint[metric.sprint_id] = metric

    return [
        Fact(
            metric="coverage_percent",
            raw_value=float(metric.value),
            source_type="metric",
            source_id=metric.id,
            sprint_id=sprint_id,
            observed_at=require_utc_datetime(metric.measured_at),
            evidence={
                "metric_name": metric.name,
                "value": metric.value,
                "unit": metric.unit,
                "source": metric.source,
                "measured_at": require_utc_datetime(metric.measured_at).isoformat(),
            },
        )
        for sprint_id, metric in latest_by_sprint.items()
    ]


def collect_facts(context: RuleContext) -> list[Fact]:
    """Build deterministic, dated facts before applying configurable policies."""

    return _ticket_facts(context) + _build_facts(context) + _metric_facts(context)
