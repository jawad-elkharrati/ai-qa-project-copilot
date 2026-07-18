from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Build, IngestionLog, Metric, Project, Sprint, Ticket


def project_overview(
    session: Session, project_id: str, sprint_id: str | None = None, as_of: date | None = None
) -> dict[str, object] | None:
    project = session.get(Project, project_id)
    if project is None:
        return None

    ticket_query = select(Ticket).where(Ticket.project_id == project_id)
    build_query = select(Build).where(Build.project_id == project_id)
    metric_query = select(Metric).where(Metric.project_id == project_id)
    if sprint_id:
        ticket_query = ticket_query.where(Ticket.sprint_id == sprint_id)
        build_query = build_query.where(Build.sprint_id == sprint_id)
        metric_query = metric_query.where(Metric.sprint_id == sprint_id)

    if as_of is None:
        reference = session.scalar(
            select(IngestionLog.reference_date)
            .where(IngestionLog.project_id == project_id, IngestionLog.reference_date.is_not(None))
            .order_by(IngestionLog.finished_at.desc())
            .limit(1)
        )
        as_of = reference or date.today()

    tickets = list(session.scalars(ticket_query))
    builds = list(session.scalars(build_query))
    metrics = list(session.scalars(metric_query))
    total_points = sum(ticket.story_points for ticket in tickets)
    done_points = sum(ticket.story_points for ticket in tickets if ticket.status == "done")
    coverage_metrics = sorted(
        (metric for metric in metrics if metric.name == "test_coverage"),
        key=lambda metric: metric.measured_at,
        reverse=True,
    )

    return {
        "project_id": project_id,
        "sprint_id": sprint_id,
        "as_of": as_of.isoformat(),
        "total_tickets": len(tickets),
        "done_tickets": sum(ticket.status == "done" for ticket in tickets),
        "progress_percent": round(done_points / total_points * 100, 1) if total_points else 0.0,
        "blocked_tickets": sum(ticket.status == "blocked" for ticket in tickets),
        "overdue_tickets": sum(
            ticket.status != "done" and ticket.due_date is not None and ticket.due_date < as_of
            for ticket in tickets
        ),
        "failed_builds": sum(build.status == "failed" for build in builds),
        "test_coverage": coverage_metrics[0].value if coverage_metrics else None,
    }


def list_sprints(session: Session, project_id: str) -> list[Sprint]:
    return list(
        session.scalars(
            select(Sprint).where(Sprint.project_id == project_id).order_by(Sprint.start_date)
        )
    )
