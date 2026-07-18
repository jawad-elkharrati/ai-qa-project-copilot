from datetime import UTC, datetime
from pathlib import Path

from app.dataset import dataset_summary, load_dataset

DATASET_PATH = Path("data/demo_dataset_v0.1.json")


def test_dataset_has_expected_volume() -> None:
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
