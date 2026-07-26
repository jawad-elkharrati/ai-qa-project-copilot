from __future__ import annotations

from typing import Protocol

from app.fact_aggregator import collect_facts
from app.policy_evaluator import evaluate_policy
from app.policy_loader import get_policy_set
from app.policy_models import PolicySet
from app.qa_domain import Finding, RuleContext

RULESET_VERSION = get_policy_set().ruleset_version


class Rule(Protocol):
    rule_id: str

    def __call__(self, context: RuleContext) -> list[Finding]: ...


def _evaluate_one(
    context: RuleContext, policy_id: str, policy_set: PolicySet | None = None
) -> list[Finding]:
    selected = policy_set or get_policy_set()
    return evaluate_policy(selected.by_id(policy_id), collect_facts(context))


def detect_long_blocked(context: RuleContext) -> list[Finding]:
    return _evaluate_one(context, "QA-BLOCKED-LONG")


detect_long_blocked.rule_id = "QA-BLOCKED-LONG"


def detect_overdue_tickets(context: RuleContext) -> list[Finding]:
    return _evaluate_one(context, "QA-TICKET-OVERDUE")


detect_overdue_tickets.rule_id = "QA-TICKET-OVERDUE"


def detect_open_critical_bugs(context: RuleContext) -> list[Finding]:
    return _evaluate_one(context, "QA-CRITICAL-BUG-OPEN")


detect_open_critical_bugs.rule_id = "QA-CRITICAL-BUG-OPEN"


def detect_failed_pipeline(context: RuleContext) -> list[Finding]:
    return _evaluate_one(context, "QA-PIPELINE-FAILED")


detect_failed_pipeline.rule_id = "QA-PIPELINE-FAILED"


def detect_low_coverage(context: RuleContext) -> list[Finding]:
    return _evaluate_one(context, "QA-COVERAGE-LOW")


detect_low_coverage.rule_id = "QA-COVERAGE-LOW"

RULES: tuple[Rule, ...] = (
    detect_long_blocked,
    detect_overdue_tickets,
    detect_open_critical_bugs,
    detect_failed_pipeline,
    detect_low_coverage,
)


def evaluate_rules(context: RuleContext, policy_set: PolicySet | None = None) -> list[Finding]:
    selected = policy_set or get_policy_set()
    facts = collect_facts(context)
    findings = [
        finding for policy in selected.policies for finding in evaluate_policy(policy, facts)
    ]
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(
        findings,
        key=lambda item: (severity_rank[item.severity], item.rule_id, item.source_id),
    )
