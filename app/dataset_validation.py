from __future__ import annotations

from datetime import date

from app.time_utils import reference_day_end, require_utc_datetime


class DatasetConsistencyError(ValueError):
    pass


def _fail(message: str) -> None:
    raise DatasetConsistencyError(message)


def _inside_sprint(moment, sprint, label: str) -> None:
    observed = require_utc_datetime(moment).date()
    if not sprint.start_date <= observed <= sprint.end_date:
        _fail(
            f"{label} occurs on {observed}, outside sprint {sprint.id} "
            f"[{sprint.start_date}, {sprint.end_date}]"
        )


def validate_dataset_consistency(dataset) -> None:
    """Validate cross-entity business and temporal invariants."""

    reference_limit = reference_day_end(dataset.reference_date)
    sprints = {item.id: item for item in dataset.sprints}
    tickets = {item.id: item for item in dataset.tickets}
    commits_by_sha = {item.sha: item for item in dataset.commits}
    pull_requests = {item.id: item for item in dataset.pull_requests}
    builds = {item.id: item for item in dataset.builds}

    for sprint in dataset.sprints:
        if sprint.start_date > sprint.end_date:
            _fail(f"sprint {sprint.id} starts after it ends")

    for ticket in dataset.tickets:
        created = require_utc_datetime(ticket.created_at)
        updated = require_utc_datetime(ticket.updated_at)
        if created > updated:
            _fail(f"ticket {ticket.id} is updated before it is created")
        if (
            ticket.blocked_since is not None
            and require_utc_datetime(ticket.blocked_since) < created
        ):
            _fail(f"ticket {ticket.id} is blocked before it is created")
        if ticket.closed_at is not None:
            closed = require_utc_datetime(ticket.closed_at)
            if closed < created:
                _fail(f"ticket {ticket.id} is closed before it is created")

    for pull_request in dataset.pull_requests:
        created = require_utc_datetime(pull_request.created_at)
        if (
            pull_request.merged_at is not None
            and require_utc_datetime(pull_request.merged_at) < created
        ):
            _fail(f"pull request {pull_request.id} is merged before it is created")

    for build in dataset.builds:
        if build.pull_request_id is None:
            _fail(f"build {build.id} has no pull request")
        pull_request = pull_requests.get(build.pull_request_id)
        if pull_request is None:
            _fail(f"build {build.id} references unknown pull request {build.pull_request_id}")
        commit = commits_by_sha.get(build.commit_sha)
        if commit is None:
            _fail(f"build {build.id} references unknown commit SHA {build.commit_sha}")
        if pull_request.ticket_id is None or commit.ticket_id is None:
            _fail(f"build {build.id} chain has no ticket")
        if pull_request.ticket_id != commit.ticket_id:
            _fail(
                f"build {build.id} links pull request {pull_request.id} to "
                f"{pull_request.ticket_id}, but commit {commit.id} to {commit.ticket_id}"
            )
        ticket = tickets[pull_request.ticket_id]
        if build.sprint_id != ticket.sprint_id:
            _fail(
                f"build {build.id} sprint {build.sprint_id} differs from "
                f"ticket {ticket.id} sprint {ticket.sprint_id}"
            )
        sprint = sprints[build.sprint_id]
        commit_at = require_utc_datetime(commit.committed_at)
        pull_request_at = require_utc_datetime(pull_request.created_at)
        build_at = require_utc_datetime(build.started_at)
        if not commit_at <= pull_request_at <= build_at:
            _fail(
                f"invalid chain dates for {build.id}: commit {commit.id}={commit_at.isoformat()}, "
                f"pull request {pull_request.id}={pull_request_at.isoformat()}, "
                f"build={build_at.isoformat()}"
            )
        if build.finished_at is not None:
            finished = require_utc_datetime(build.finished_at)
            if finished < build_at:
                _fail(f"build {build.id} finishes before it starts")
            if finished > reference_limit:
                _fail(f"build {build.id} finishes after dataset reference date")
        _inside_sprint(commit_at, sprint, f"commit {commit.id}")
        _inside_sprint(pull_request_at, sprint, f"pull request {pull_request.id}")
        _inside_sprint(build_at, sprint, f"build {build.id}")
        if build_at > reference_limit:
            _fail(f"build {build.id} occurs after dataset reference date")

    for result in dataset.test_results:
        build = builds[result.build_id]
        executed = require_utc_datetime(result.executed_at)
        build_start = require_utc_datetime(build.started_at)
        build_finish = (
            require_utc_datetime(build.finished_at)
            if build.finished_at is not None
            else build_start
        )
        if executed < build_finish:
            _fail(f"test result {result.id} executes before build {build.id} finishes")
        if executed > reference_limit:
            _fail(f"test result {result.id} occurs after dataset reference date")
        _inside_sprint(executed, sprints[build.sprint_id], f"test result {result.id}")

    for metric in dataset.metrics:
        measured = require_utc_datetime(metric.measured_at)
        if measured > reference_limit:
            _fail(f"metric {metric.id} occurs after dataset reference date")
        if metric.sprint_id is not None:
            _inside_sprint(measured, sprints[metric.sprint_id], f"metric {metric.id}")


def validate_snapshot_evidence(
    *,
    analysis_id: str,
    reference_date: date,
    evidence_rows: list,
) -> None:
    boundary = reference_day_end(reference_date)
    for evidence in evidence_rows:
        if evidence.analysis_id != analysis_id:
            _fail(
                f"evidence {evidence.id} belongs to {evidence.analysis_id}, "
                f"not snapshot {analysis_id}"
            )
        observed = require_utc_datetime(evidence.observed_at) if evidence.observed_at else None
        if observed is not None and observed > boundary:
            _fail(
                f"evidence {evidence.id} observed at {observed.isoformat()} "
                f"after snapshot reference date {reference_date}"
            )
