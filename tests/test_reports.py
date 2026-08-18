from datetime import date

import pytest

from app.dataset import load_dataset
from app.report_service import (
    ReportNotFoundError,
    ReportPeriodError,
    daily_report,
    weekly_report,
)
from app.seed import seed_dataset


def _seed(db_session) -> None:
    seed_dataset(db_session, load_dataset("data/demo_dataset_v0.1.json"))


def test_daily_report_compares_adjacent_snapshots_without_inventing_content(db_session) -> None:
    _seed(db_session)
    report = daily_report(db_session, "PRJ-COPILOTE", date(2026, 7, 15))

    assert report["report_type"] == "DAILY"
    assert report["snapshot_id"] == "QAH-NS-20260715"
    assert report["score"] == 36
    assert report["risk_delta"]["delta"] == 18
    assert {item["policy_id"] for item in report["new_risks"]} == {"QA-BLOCKED-LONG"}
    assert {item["policy_id"] for item in report["aggravated_risks"]} == {"QA-TICKET-OVERDUE"}
    assert report["resolved_risks"] == []
    assert report["suggested_decision"] == "GO_WITH_CONDITIONS"
    assert report["human_validation_required"] is True
    assert report["external_action_executed"] is False


def test_daily_report_detects_resolved_risks_and_is_deterministic(db_session) -> None:
    _seed(db_session)
    first = daily_report(db_session, "PRJ-COPILOTE", date(2026, 7, 18))
    second = daily_report(db_session, "PRJ-COPILOTE", date(2026, 7, 18))

    assert first == second
    assert {item["policy_id"] for item in first["resolved_risks"]} == {"QA-BLOCKED-LONG"}
    assert first["risk_delta"]["direction"] == "decreased"
    assert first["recommendations"]
    assert all(item["priority_justification"] for item in first["recommendations"])


def test_weekly_report_aggregates_multiple_snapshots_and_real_transitions(db_session) -> None:
    _seed(db_session)
    report = weekly_report(
        db_session,
        "PRJ-COPILOTE",
        date(2026, 7, 14),
        date(2026, 7, 20),
    )

    assert report["report_type"] == "WEEKLY"
    assert len(report["snapshot_ids"]) == 7
    assert report["best_score"] == 12
    assert report["worst_score"] == 82
    assert report["score_change"] == -6
    assert report["trend"] == "IMPROVING"
    assert {item["policy_id"] for item in report["persistent_risks"]} == {"QA-TICKET-OVERDUE"}
    assert {item["policy_id"] for item in report["new_risks"]} == {
        "QA-BLOCKED-LONG",
        "QA-PIPELINE-FAILED",
        "QA-CRITICAL-BUG-OPEN",
    }
    assert report["policy_violation_frequency"]["QA-TICKET-OVERDUE"] == 7
    assert len(report["contribution_evolution"]["QA-PIPELINE-FAILED"]) == 7
    assert report["recommendations_emitted"] == 5
    assert report["human_decisions"] == {}
    assert "aucune causalité" in report["observed_impact"]
    assert report["external_action_executed"] is False


def test_reports_fail_explicitly_for_missing_or_invalid_periods(db_session) -> None:
    _seed(db_session)

    with pytest.raises(ReportNotFoundError, match="no risk snapshot"):
        daily_report(db_session, "PRJ-COPILOTE", date(2026, 7, 1))
    with pytest.raises(ReportPeriodError, match="period_start"):
        weekly_report(
            db_session,
            "PRJ-COPILOTE",
            date(2026, 7, 20),
            date(2026, 7, 14),
        )
    with pytest.raises(ReportNotFoundError, match="at least two"):
        weekly_report(
            db_session,
            "PRJ-COPILOTE",
            date(2026, 7, 20),
            date(2026, 7, 20),
        )
