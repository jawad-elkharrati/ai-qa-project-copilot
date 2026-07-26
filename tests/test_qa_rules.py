from datetime import UTC, datetime

from app.dataset import load_dataset
from app.qa_rules import (
    RuleContext,
    detect_failed_pipeline,
    detect_long_blocked,
    detect_low_coverage,
    detect_open_critical_bugs,
    detect_overdue_tickets,
    evaluate_rules,
)
from app.qa_scoring import calculate_risk_score


def context_for(sprint_id: str) -> RuleContext:
    dataset = load_dataset("data/demo_dataset_v0.1.json")
    return RuleContext(
        project_id=dataset.project.id,
        reference_date=dataset.reference_date,
        analyzed_at=datetime(2026, 7, 13, 12, tzinfo=UTC),
        tickets=[ticket for ticket in dataset.tickets if ticket.sprint_id == sprint_id],
        builds=[build for build in dataset.builds if build.sprint_id == sprint_id],
        metrics=[metric for metric in dataset.metrics if metric.sprint_id == sprint_id],
        sprints=dataset.sprints,
    )


def test_blocked_long_rule_explains_duration_and_severity() -> None:
    risk_finding = detect_long_blocked(context_for("SPR-002"))[0]
    critical_finding = detect_long_blocked(context_for("SPR-003"))[0]

    assert (risk_finding.source_id, risk_finding.severity) == ("TKT-024", "high")
    assert risk_finding.evidence["blocked_hours"] > 72
    assert (critical_finding.source_id, critical_finding.severity) == ("TKT-039", "critical")


def test_overdue_rule_matches_the_known_ticket_oracle() -> None:
    risk_findings = detect_overdue_tickets(context_for("SPR-002"))
    critical_findings = detect_overdue_tickets(context_for("SPR-003"))

    assert {(item.source_id, item.severity) for item in risk_findings} == {
        ("TKT-027", "medium"),
        ("TKT-029", "medium"),
    }
    assert {(item.source_id, item.severity) for item in critical_findings} == {
        ("TKT-042", "high"),
        ("TKT-045", "high"),
    }


def test_critical_bug_rule_ignores_non_critical_and_closed_tickets() -> None:
    findings = detect_open_critical_bugs(context_for("SPR-003"))
    assert [(item.source_id, item.severity) for item in findings] == [("TKT-038", "critical")]
    assert detect_open_critical_bugs(context_for("SPR-001")) == []


def test_pipeline_rule_only_flags_an_unrecovered_latest_failure() -> None:
    assert detect_failed_pipeline(context_for("SPR-002")) == []
    finding = detect_failed_pipeline(context_for("SPR-003"))[0]
    assert (finding.source_id, finding.severity) == ("BLD-012", "critical")
    assert finding.evidence["consecutive_failures"] == 2


def test_low_coverage_rule_uses_the_latest_metric_and_threshold() -> None:
    assert detect_low_coverage(context_for("SPR-002")) == []
    finding = detect_low_coverage(context_for("SPR-003"))[0]
    assert (finding.source_id, finding.severity) == ("MET-007", "high")
    assert finding.evidence["value"] == 54.0
    assert finding.evidence["threshold"] == 70.0


def test_three_scenarios_have_ordered_explainable_scores() -> None:
    healthy = calculate_risk_score(evaluate_rules(context_for("SPR-001")))
    at_risk = calculate_risk_score(evaluate_rules(context_for("SPR-002")))
    critical = calculate_risk_score(evaluate_rules(context_for("SPR-003")))

    assert healthy[0:2] == (0.0, "low")
    assert at_risk[1] == "medium"
    assert critical[1] == "critical"
    assert healthy[0] < at_risk[0] < critical[0]
    assert round(sum(item["contribution"] for item in critical[2]), 1) == critical[0]
