from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class QADecision(StrEnum):
    """A deterministic suggestion; the final decision always remains human."""

    GO = "GO"
    GO_WITH_CONDITIONS = "GO_WITH_CONDITIONS"
    NO_GO = "NO_GO"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class HumanValidationStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    OVERRIDDEN = "OVERRIDDEN"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class DecisionThresholds:
    """Configurable P0 thresholds used by the deterministic decision engine."""

    go_max_risk_score: float = 25.0
    conditional_max_risk_score: float = 60.0
    minimum_confidence: float = 0.60
    minimum_evidence_coverage: float = 0.70
    minimum_data_freshness: float = 0.60
    minimum_test_coverage: float = 70.0

    def __post_init__(self) -> None:
        bounded_ratios = {
            "minimum_confidence": self.minimum_confidence,
            "minimum_evidence_coverage": self.minimum_evidence_coverage,
            "minimum_data_freshness": self.minimum_data_freshness,
        }
        if not 0 <= self.go_max_risk_score < self.conditional_max_risk_score <= 100:
            raise ValueError("risk thresholds must satisfy 0 <= go < conditional <= 100")
        for name, value in bounded_ratios.items():
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if not 0 <= self.minimum_test_coverage <= 100:
            raise ValueError("minimum_test_coverage must be between 0 and 100")


@dataclass(frozen=True)
class DecisionSignals:
    """Normalized facts consumed by the decision engine, independent from API and UI."""

    project_id: str
    snapshot_id: str
    risk_score: float
    confidence_score: float
    evidence_coverage: float
    data_freshness: float
    active_risk_count: int
    critical_risk_count: int = 0
    blocking_risk_ids: tuple[str, ...] = ()
    violated_policy_ids: tuple[str, ...] = ()
    blocking_policy_ids: tuple[str, ...] = ()
    critical_ci_failure: bool = False
    open_critical_bug_count: int = 0
    test_coverage_percent: float | None = None
    blocked_ticket_count: int = 0
    overdue_ticket_count: int = 0
    missing_information: tuple[str, ...] = ()
    stale_information: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.project_id.strip():
            raise ValueError("project_id is required")
        if not self.snapshot_id.strip():
            raise ValueError("snapshot_id is required")
        bounded_scores = {
            "risk_score": (self.risk_score, 100),
            "confidence_score": (self.confidence_score, 1),
            "evidence_coverage": (self.evidence_coverage, 1),
            "data_freshness": (self.data_freshness, 1),
        }
        for name, (value, maximum) in bounded_scores.items():
            if not 0 <= value <= maximum:
                raise ValueError(f"{name} must be between 0 and {maximum}")
        non_negative_counts = {
            "active_risk_count": self.active_risk_count,
            "critical_risk_count": self.critical_risk_count,
            "open_critical_bug_count": self.open_critical_bug_count,
            "blocked_ticket_count": self.blocked_ticket_count,
            "overdue_ticket_count": self.overdue_ticket_count,
        }
        for name, value in non_negative_counts.items():
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.test_coverage_percent is not None and not (0 <= self.test_coverage_percent <= 100):
            raise ValueError("test_coverage_percent must be between 0 and 100")


@dataclass(frozen=True)
class DecisionResult:
    suggested_decision: QADecision
    justification: str
    triggered_rules: tuple[str, ...]
    blockers: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    human_validation_status: HumanValidationStatus = HumanValidationStatus.PENDING
    external_action_executed: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not self.justification.strip():
            raise ValueError("decision justification is required")
        if not self.triggered_rules:
            raise ValueError("at least one triggered decision rule is required")
