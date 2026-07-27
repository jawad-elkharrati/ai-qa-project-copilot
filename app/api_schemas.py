from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["low", "medium", "high", "critical"]
DecisionStatus = Literal["pending", "accepted", "modified", "rejected"]


class RiskFindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    rule_id: str
    title: str
    description: str
    severity: Severity
    priority: int = Field(ge=1, le=4)
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    source_type: str
    source_id: str
    sprint_id: str | None
    evidence: dict[str, object]
    recommendation: str
    requires_human_validation: bool
    status: str
    detected_at: datetime


class RiskContributionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    policy_id: str
    policy_version: int | None = None
    factor: str
    raw_value: bool | float | str | None = None
    normalized_value: float = Field(ge=0, le=1)
    weight: float = Field(ge=0, le=100)
    contribution: float = Field(ge=0, le=100)
    finding_count: int = Field(ge=0)
    explanation: str
    source_type: str | None = None
    source_id: str | None = None
    observed_at: datetime | None = None


class RiskSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: str
    snapshot_id: str
    snapshot_created: bool
    previous_snapshot_id: str | None
    agent: str
    ruleset_version: str
    policy_hash: str
    input_fingerprint: str
    project_id: str
    sprint_id: str | None
    reference_date: date
    score: float = Field(ge=0, le=100)
    severity: Severity
    score_breakdown: list[dict[str, object]]
    contributions: list[RiskContributionResponse]
    finding_count: int = Field(ge=0)
    returned_findings: int = Field(ge=0)
    analyzed_at: datetime
    confidence_score: float = Field(ge=0, le=1)
    evidence_coverage: float = Field(ge=0, le=1)
    confidence_details: dict[str, object]
    missing_information: list
    stale_information: list
    human_validation_required: bool
    findings: list[RiskFindingResponse]


class RiskDeltaFactorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str
    factor: str
    previous_contribution: float
    current_contribution: float
    delta: float
    change: Literal["added", "removed", "increased", "decreased"]
    explanation: str


class RiskDeltaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_snapshot_id: str
    previous_snapshot_id: str | None
    current_score: float = Field(ge=0, le=100)
    previous_score: float | None = Field(default=None, ge=0, le=100)
    delta: float | None
    direction: Literal["initial", "increased", "decreased", "unchanged"]
    changes: list[RiskDeltaFactorResponse]
    unchanged_factor_count: int = Field(ge=0)


class RiskHistoryItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    previous_snapshot_id: str | None
    reference_date: date
    calculated_at: datetime
    score: float = Field(ge=0, le=100)
    severity: Severity
    confidence_score: float = Field(ge=0, le=1)
    finding_count: int = Field(ge=0)
    policy_version: str


class RiskHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    sprint_id: str | None
    items: list[RiskHistoryItemResponse]


class RiskSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    sprint_id: str | None
    snapshot_id: str
    score: float = Field(ge=0, le=100)
    severity: Severity
    confidence_score: float = Field(ge=0, le=1)
    evidence_coverage: float = Field(ge=0, le=1)
    confidence_details: dict[str, object]
    missing_information: list
    stale_information: list
    delta: RiskDeltaResponse
    top_contributions: list[RiskContributionResponse]
    human_validation_required: bool
    pending_recommendation_count: int = Field(ge=0)
    decision_summary: dict[str, object]


class RiskDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk: RiskFindingResponse
    snapshot_id: str
    contribution: RiskContributionResponse | None
    human_validation_required: bool


class EvidenceNodeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    source_id: str
    label: str
    observed_at: datetime | None
    metadata: dict[str, object]


class EvidenceEdgeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    relation: str
    label: str


class EvidenceMissingLinkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation: str
    source_id: str
    target_id: str


class EvidenceChainResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[EvidenceNodeResponse]
    edges: list[EvidenceEdgeResponse]
    missing_links: list[EvidenceMissingLinkResponse]


class RiskExplanationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_id: str
    snapshot_id: str
    policy_id: str
    summary: str
    severity: Severity
    score_contribution: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=1)
    evidence_coverage: float = Field(ge=0, le=1)
    confidence_details: dict[str, object]
    missing_information: list
    stale_information: list
    evidence_chain: EvidenceChainResponse
    recommendation: str
    human_validation_required: bool


class RiskDecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["accepted", "modified", "rejected"]
    decided_by: str = Field(min_length=1, max_length=120)
    comment: str | None = Field(default=None, max_length=2000)
    modified_recommendation: str | None = Field(default=None, max_length=5000)


class RiskDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    risk_id: str
    analysis_id: str
    policy_id: str
    status: DecisionStatus
    original_recommendation: str
    modified_recommendation: str | None
    comment: str | None
    decided_by: str | None
    decided_at: datetime | None
    created_at: datetime
    previous_decision_id: str | None
    external_action_executed: Literal[False]


class RiskDecisionHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_id: str
    current_status: DecisionStatus
    current_decision: RiskDecisionResponse | None
    items: list[RiskDecisionResponse]
