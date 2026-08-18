from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum


class RecommendationStatus(StrEnum):
    """Governed lifecycle with the minimal P1-A operational state."""

    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    MODIFIED = "MODIFIED"
    REJECTED = "REJECTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class RecommendationPriority(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RecommendationImpact(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RecommendationEffort(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RecommendationUrgency(StrEnum):
    IMMEDIATE = "IMMEDIATE"
    THIS_WEEK = "THIS_WEEK"
    PLANNED = "PLANNED"


class RecommendationOutcomeStatus(StrEnum):
    NOT_YET_MEASURABLE = "NOT_YET_MEASURABLE"
    IMPROVEMENT_OBSERVED = "IMPROVEMENT_OBSERVED"
    NO_IMPROVEMENT_OBSERVED = "NO_IMPROVEMENT_OBSERVED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


def _stable_digest(*parts: str) -> str:
    canonical = "|".join(part.strip() for part in parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper()


def risk_identity_key(
    *,
    project_id: str,
    policy_id: str,
    source_type: str,
    source_id: str,
) -> str:
    """Identify the same semantic risk independently from a snapshot-specific risk id."""

    values = (project_id, policy_id, source_type, source_id)
    if any(not value.strip() for value in values):
        raise ValueError("risk identity parts must be non-empty")
    return f"RID-{_stable_digest(*values)[:24]}"


def recommendation_key(
    *,
    risk_key: str,
    recommendation_type: str = "QA_REMEDIATION",
) -> str:
    """Stable key combined with source_snapshot_id by the database uniqueness rule."""

    if not risk_key.strip() or not recommendation_type.strip():
        raise ValueError("recommendation key parts must be non-empty")
    return f"RKEY-{_stable_digest(risk_key, recommendation_type)[:24]}"


@dataclass(frozen=True)
class RecommendationIdentity:
    project_id: str
    source_snapshot_id: str
    source_risk_id: str
    risk_key: str
    recommendation_key: str

    @property
    def idempotency_scope(self) -> tuple[str, str]:
        return self.source_snapshot_id, self.recommendation_key


@dataclass(frozen=True)
class RecommendationPriorityResult:
    priority: RecommendationPriority
    score: int
    justification: str
    factors: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 100:
            raise ValueError("priority score must be between 0 and 100")
        if not self.justification.strip():
            raise ValueError("priority justification is required")
