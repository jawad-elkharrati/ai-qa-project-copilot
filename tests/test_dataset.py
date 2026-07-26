import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.dataset import dataset_summary, load_dataset
from app.schemas import DemoDataset

DATASET_PATH = Path("data/demo_dataset_v0.1.json")


def test_dataset_has_week_one_expected_volume() -> None:
    dataset = load_dataset(DATASET_PATH)
    assert dataset_summary(dataset) == {
        "version": "0.1",
        "projects": 1,
        "sprints": 3,
        "tickets": 50,
        "commits": 30,
        "pull_requests": 12,
        "builds": 12,
        "test_results": 12,
        "metrics": 9,
        "risks": 0,
        "reports": 0,
        "expected_anomalies": 9,
    }
    distribution = [
        sum(ticket.sprint_id == sprint.id for ticket in dataset.tickets)
        for sprint in dataset.sprints
    ]
    assert distribution == [16, 17, 17]


def test_expected_anomaly_oracle_matches_injected_facts() -> None:
    dataset = load_dataset(DATASET_PATH)
    reference = datetime.combine(dataset.reference_date, datetime.min.time(), tzinfo=UTC)

    long_blocked = {
        ticket.id
        for ticket in dataset.tickets
        if ticket.blocked_since is not None
        and (reference - ticket.blocked_since).total_seconds() / 3600 > 72
    }
    overdue = {
        ticket.id
        for ticket in dataset.tickets
        if ticket.due_date is not None
        and ticket.due_date < dataset.reference_date
        and ticket.status != "done"
    }
    critical_bugs = {
        ticket.id
        for ticket in dataset.tickets
        if ticket.type == "bug" and ticket.priority == "critical" and ticket.status != "done"
    }
    low_coverage = {
        metric.id
        for metric in dataset.metrics
        if metric.name == "test_coverage" and metric.value < 70
    }
    oracle = {(item.rule_id, item.source_id) for item in dataset.expected_anomalies}

    assert long_blocked == {"TKT-024", "TKT-039"}
    assert overdue == {"TKT-027", "TKT-029", "TKT-042", "TKT-045"}
    assert critical_bugs == {"TKT-038"}
    assert low_coverage == {"MET-007"}
    assert {("QA-BLOCKED-LONG", item) for item in long_blocked} <= oracle
    assert {("QA-TICKET-OVERDUE", item) for item in overdue} <= oracle
    assert {("QA-CRITICAL-BUG-OPEN", item) for item in critical_bugs} <= oracle
    assert {("QA-COVERAGE-LOW", item) for item in low_coverage} <= oracle
    assert ("QA-PIPELINE-FAILED", "BLD-012") in oracle


def test_latest_critical_sprint_builds_fail_consecutively() -> None:
    dataset = load_dataset(DATASET_PATH)
    builds = sorted(
        (build for build in dataset.builds if build.sprint_id == "SPR-003"),
        key=lambda build: build.started_at,
    )
    assert [build.status for build in builds[-2:]] == ["failed", "failed"]


def test_all_test_result_counts_are_consistent() -> None:
    dataset = load_dataset(DATASET_PATH)
    for result in dataset.test_results:
        assert result.passed + result.failed + result.skipped == result.total


def test_all_ticket_pr_commit_build_test_chains_are_consistent() -> None:
    dataset = load_dataset(DATASET_PATH)
    tickets = {item.id: item for item in dataset.tickets}
    pull_requests = {item.id: item for item in dataset.pull_requests}
    commits = {item.sha: item for item in dataset.commits}
    results_by_build = {item.build_id: item for item in dataset.test_results}

    for build in dataset.builds:
        pull_request = pull_requests[build.pull_request_id]
        commit = commits[build.commit_sha]
        ticket = tickets[pull_request.ticket_id]
        result = results_by_build[build.id]
        assert commit.ticket_id == pull_request.ticket_id == ticket.id
        assert build.sprint_id == ticket.sprint_id
        assert commit.committed_at <= pull_request.created_at <= build.started_at
        assert build.finished_at <= result.executed_at
        assert result.executed_at.date() <= dataset.reference_date


def test_bl012_chain_has_functional_ticket_and_chronology() -> None:
    dataset = load_dataset(DATASET_PATH)
    build = next(item for item in dataset.builds if item.id == "BLD-012")
    pull_request = next(item for item in dataset.pull_requests if item.id == build.pull_request_id)
    commit = next(item for item in dataset.commits if item.sha == build.commit_sha)

    assert pull_request.ticket_id == "TKT-047"
    assert commit.ticket_id == "TKT-047"
    assert "TKT-047" in pull_request.title
    assert "TKT-047" in commit.message
    assert commit.committed_at <= pull_request.created_at <= build.started_at


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda payload: payload["builds"][0].update({"started_at": "2026-06-08T09:00:00Z"}),
            "invalid chain dates",
        ),
        (
            lambda payload: payload["commits"][1].update({"ticket_id": "TKT-001"}),
            "links pull request",
        ),
        (
            lambda payload: payload["test_results"][0].update(
                {"executed_at": "2026-06-08T09:00:00Z"}
            ),
            "executes before build",
        ),
    ],
)
def test_temporally_or_functionally_invalid_dataset_is_rejected(mutation, expected: str) -> None:
    payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    mutation(payload)
    with pytest.raises(ValidationError, match=expected):
        DemoDataset.model_validate(payload)
