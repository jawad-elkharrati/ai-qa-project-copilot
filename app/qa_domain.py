from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from app.models import Build, Metric, Sprint, Ticket


@dataclass(frozen=True)
class RuleContext:
    project_id: str
    reference_date: date
    analyzed_at: datetime
    tickets: list[Ticket]
    builds: list[Build]
    metrics: list[Metric]
    sprints: list[Sprint]
    sprint_id: str | None = None


@dataclass(frozen=True)
class Fact:
    metric: str
    raw_value: bool | float | str
    source_type: str
    source_id: str
    sprint_id: str | None
    observed_at: datetime | None
    evidence: dict[str, object]
    attributes: dict[str, bool | float | str] = field(default_factory=dict)

    def value_for(self, metric: str):
        if metric == self.metric:
            return self.raw_value
        return self.attributes.get(metric)


@dataclass(frozen=True)
class Finding:
    rule_id: str
    policy_version: int
    factor: str
    title: str
    description: str
    severity: str
    source_type: str
    source_id: str
    sprint_id: str | None
    evidence: dict[str, object]
    recommendation: str
    confidence: float
    raw_value: bool | float | str
    observed_at: datetime | None
    signal_strength: float
