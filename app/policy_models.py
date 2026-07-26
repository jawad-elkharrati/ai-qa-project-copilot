from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Severity = Literal["low", "medium", "high", "critical"]
EntityType = Literal["ticket", "build", "metric"]
MetricName = Literal[
    "blocked_hours",
    "overdue_days",
    "open_critical_bug",
    "consecutive_failed_builds",
    "coverage_percent",
    "active_high_priority",
]
Operator = Literal[
    "equal",
    "not_equal",
    "greater_than",
    "greater_or_equal",
    "less_than",
    "less_or_equal",
    "in",
    "not_in",
]


class PolicyCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: MetricName
    operator: Operator
    value: bool | float | str | list[bool | float | str]

    @model_validator(mode="after")
    def validate_operator_value(self):
        expects_collection = self.operator in {"in", "not_in"}
        if expects_collection and not isinstance(self.value, list):
            raise ValueError(f"{self.operator} operator requires a list value")
        if not expects_collection and isinstance(self.value, list):
            raise ValueError(f"{self.operator} operator requires a scalar value")
        return self


class NormalizationDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["ratio", "boolean", "distance_below"]
    divisor: float = Field(gt=0)
    baseline: float | None = None

    @model_validator(mode="after")
    def validate_baseline(self):
        if self.strategy == "distance_below" and self.baseline is None:
            raise ValueError("distance_below normalization requires a baseline")
        return self


class AggregationDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["max_with_count_bonus"] = "max_with_count_bonus"
    count_bonus: float = Field(default=0.0, ge=0, le=1)


class SeverityOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition: PolicyCondition
    severity: Severity


class PolicyDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^QA-[A-Z0-9-]+$")
    version: int = Field(ge=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    entity_type: EntityType
    severity: Severity
    weight: float = Field(ge=0, le=100)
    condition: PolicyCondition
    normalization: NormalizationDefinition
    aggregation: AggregationDefinition
    severity_overrides: list[SeverityOverride] = Field(default_factory=list)
    recommendation: str = Field(min_length=1)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_entity_metric(self):
        entity_by_metric = {
            "blocked_hours": "ticket",
            "overdue_days": "ticket",
            "open_critical_bug": "ticket",
            "consecutive_failed_builds": "build",
            "coverage_percent": "metric",
        }
        expected_entity = entity_by_metric.get(self.condition.metric)
        if expected_entity is None:
            raise ValueError("policy condition must use an observable primary metric")
        if self.entity_type != expected_entity:
            raise ValueError(f"{self.condition.metric} requires entity_type={expected_entity}")
        return self

    @property
    def semantic_fingerprint(self) -> str:
        """Identify detection logic independently from editorial metadata."""

        payload = {
            "entity_type": self.entity_type,
            "condition": self.condition.model_dump(mode="json"),
            "normalization": self.normalization.model_dump(mode="json"),
            "aggregation": self.aggregation.model_dump(mode="json"),
            "severity_overrides": [
                override.model_dump(mode="json") for override in self.severity_overrides
            ],
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PolicySet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    version: str = Field(pattern=r"^\d+\.\d+(?:\.\d+)?$")
    description: str = Field(min_length=1)
    policies: list[PolicyDefinition] = Field(min_length=1)
    content_hash: str = ""

    @model_validator(mode="after")
    def validate_policies(self):
        identifiers = [policy.id for policy in self.policies]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("policy identifiers must be unique")
        enabled_weight = sum(policy.weight for policy in self.policies if policy.enabled)
        if enabled_weight > 100:
            raise ValueError("enabled policy weights must not exceed 100")
        semantic_owners: dict[str, str] = {}
        for policy in self.policies:
            if not policy.enabled:
                continue
            previous_id = semantic_owners.get(policy.semantic_fingerprint)
            if previous_id is not None:
                raise ValueError(
                    "Duplicate semantic policy detected: "
                    f"{previous_id} and {policy.id} evaluate the same condition"
                )
            semantic_owners[policy.semantic_fingerprint] = policy.id
        return self

    @property
    def ruleset_version(self) -> str:
        return f"{self.id}-v{self.version}"

    def by_id(self, policy_id: str) -> PolicyDefinition:
        for policy in self.policies:
            if policy.id == policy_id:
                return policy
        raise KeyError(policy_id)
