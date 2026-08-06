from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def str_pk() -> Mapped[str]:
    return mapped_column(String(64), primary_key=True)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = str_pk()
    key: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    repository_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Sprint(Base):
    __tablename__ = "sprints"
    __table_args__ = (Index("ix_sprints_project_dates", "project_id", "start_date", "end_date"),)

    id: Mapped[str] = str_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    goal: Mapped[str] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), index=True)
    capacity_points: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_project_status", "project_id", "status"),
        Index("ix_tickets_sprint_priority", "sprint_id", "priority"),
    )

    id: Mapped[str] = str_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    sprint_id: Mapped[str | None] = mapped_column(
        ForeignKey("sprints.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    priority: Mapped[str] = mapped_column(String(30), index=True)
    assignee: Mapped[str | None] = mapped_column(String(120), nullable=True)
    story_points: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    blocked_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    labels: Mapped[list[str]] = mapped_column(JSON, default=list)


class Commit(Base):
    __tablename__ = "commits"

    id: Mapped[str] = str_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    ticket_id: Mapped[str | None] = mapped_column(
        ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True
    )
    sha: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    author: Mapped[str] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(String(500))
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    additions: Mapped[int] = mapped_column(Integer)
    deletions: Mapped[int] = mapped_column(Integer)


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[str] = str_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    ticket_id: Mapped[str | None] = mapped_column(
        ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True
    )
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(250))
    author: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), index=True)
    source_branch: Mapped[str] = mapped_column(String(200))
    target_branch: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_count: Mapped[int] = mapped_column(Integer)
    changed_files: Mapped[int] = mapped_column(Integer)


class Build(Base):
    __tablename__ = "builds"
    __table_args__ = (Index("ix_builds_project_status", "project_id", "status"),)

    id: Mapped[str] = str_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    sprint_id: Mapped[str | None] = mapped_column(
        ForeignKey("sprints.id", ondelete="SET NULL"), nullable=True
    )
    pull_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True
    )
    pipeline_name: Mapped[str] = mapped_column(String(150))
    branch: Mapped[str] = mapped_column(String(200))
    commit_sha: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[str] = str_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    build_id: Mapped[str] = mapped_column(ForeignKey("builds.id", ondelete="CASCADE"))
    suite_name: Mapped[str] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(30), index=True)
    total: Mapped[int] = mapped_column(Integer)
    passed: Mapped[int] = mapped_column(Integer)
    failed: Mapped[int] = mapped_column(Integer)
    skipped: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[float] = mapped_column(Float)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = (Index("ix_metrics_project_name_date", "project_id", "name", "measured_at"),)

    id: Mapped[str] = str_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    sprint_id: Mapped[str | None] = mapped_column(
        ForeignKey("sprints.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(100))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RiskAnalysis(Base):
    __tablename__ = "risk_analyses"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_risk_analyses_score_range"),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_risk_analyses_confidence_range",
        ),
        CheckConstraint(
            "evidence_coverage >= 0 AND evidence_coverage <= 1",
            name="ck_risk_analyses_evidence_coverage_range",
        ),
        Index(
            "ix_risk_analyses_scope_date",
            "project_id",
            "sprint_id",
            "analyzed_at",
        ),
    )

    id: Mapped[str] = str_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    sprint_id: Mapped[str | None] = mapped_column(
        ForeignKey("sprints.id", ondelete="SET NULL"), nullable=True
    )
    ruleset_version: Mapped[str] = mapped_column(String(50))
    reference_date: Mapped[date] = mapped_column(Date)
    score: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(30), index=True)
    breakdown: Mapped[list[dict]] = mapped_column(JSON, default=list)
    finding_count: Mapped[int] = mapped_column(Integer)
    agent_name: Mapped[str] = mapped_column(String(80))
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    policy_hash: Mapped[str] = mapped_column(String(64), default="legacy")
    input_fingerprint: Mapped[str] = mapped_column(String(64), default="legacy")
    result_fingerprint: Mapped[str] = mapped_column(String(64), default="legacy")
    previous_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("risk_analyses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_coverage: Mapped[float] = mapped_column(Float, default=1.0)
    missing_information: Mapped[list] = mapped_column(JSON, default=list)
    stale_information: Mapped[list] = mapped_column(JSON, default=list)
    confidence_details: Mapped[dict] = mapped_column(JSON, default=dict)


class RiskContribution(Base):
    __tablename__ = "risk_contributions"
    __table_args__ = (
        UniqueConstraint(
            "analysis_id",
            "policy_id",
            name="uq_risk_contributions_analysis_policy",
        ),
        CheckConstraint(
            "normalized_value >= 0 AND normalized_value <= 1",
            name="ck_risk_contributions_normalized_range",
        ),
        CheckConstraint(
            "weight >= 0 AND weight <= 100",
            name="ck_risk_contributions_weight_range",
        ),
        CheckConstraint(
            "contribution >= 0 AND contribution <= weight",
            name="ck_risk_contributions_value_range",
        ),
    )

    id: Mapped[str] = str_pk()
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("risk_analyses.id", ondelete="CASCADE"), index=True
    )
    policy_id: Mapped[str] = mapped_column(String(100), index=True)
    policy_version: Mapped[int] = mapped_column(Integer)
    factor: Mapped[str] = mapped_column(String(100))
    raw_value: Mapped[object | None] = mapped_column(JSON, nullable=True)
    normalized_value: Mapped[float] = mapped_column(Float)
    weight: Mapped[float] = mapped_column(Float)
    contribution: Mapped[float] = mapped_column(Float)
    finding_count: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Risk(Base):
    __tablename__ = "risks"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_risks_score_range"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_risks_confidence_range",
        ),
        CheckConstraint("priority >= 1 AND priority <= 4", name="ck_risks_priority_range"),
    )

    id: Mapped[str] = str_pk()
    analysis_id: Mapped[str | None] = mapped_column(
        ForeignKey("risk_analyses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    sprint_id: Mapped[str | None] = mapped_column(
        ForeignKey("sprints.id", ondelete="SET NULL"), nullable=True
    )
    rule_id: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(30), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=4)
    score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    source_type: Mapped[str] = mapped_column(String(50))
    source_id: Mapped[str] = mapped_column(String(64))
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    recommendation: Mapped[str] = mapped_column(Text, default="")
    requires_human_validation: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(30))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RiskEvidence(Base):
    __tablename__ = "risk_evidence"
    __table_args__ = (
        UniqueConstraint(
            "risk_id",
            "source_type",
            "source_id",
            "relation",
            name="uq_risk_evidence_source_relation",
        ),
        CheckConstraint(
            "evidence_order >= 0",
            name="ck_risk_evidence_order_non_negative",
        ),
    )

    id: Mapped[str] = str_pk()
    risk_id: Mapped[str] = mapped_column(ForeignKey("risks.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("risk_analyses.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(50))
    source_id: Mapped[str] = mapped_column(String(64))
    relation: Mapped[str] = mapped_column(String(100))
    evidence_order: Mapped[int] = mapped_column(Integer)
    contribution: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RiskDecision(Base):
    __tablename__ = "risk_decisions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'modified', 'rejected')",
            name="ck_risk_decisions_status",
        ),
        CheckConstraint(
            "status = 'pending' OR "
            "(decided_by IS NOT NULL AND length(trim(decided_by)) > 0 "
            "AND decided_at IS NOT NULL)",
            name="ck_risk_decisions_actor_for_final_status",
        ),
        CheckConstraint(
            "status != 'modified' OR "
            "(modified_recommendation IS NOT NULL "
            "AND length(trim(modified_recommendation)) > 0)",
            name="ck_risk_decisions_modified_text",
        ),
        CheckConstraint(
            "status != 'rejected' OR (comment IS NOT NULL AND length(trim(comment)) > 0)",
            name="ck_risk_decisions_rejection_comment",
        ),
        Index("ix_risk_decisions_risk_created", "risk_id", "created_at"),
    )

    id: Mapped[str] = str_pk()
    risk_id: Mapped[str] = mapped_column(ForeignKey("risks.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("risk_analyses.id", ondelete="CASCADE"), index=True
    )
    policy_id: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(30))
    original_recommendation: Mapped[str] = mapped_column(Text)
    modified_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    previous_decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("risk_decisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint(
            "source_snapshot_id", "recommendation_key", name="uq_recommendations_snapshot_key"
        ),
        CheckConstraint(
            "priority_score >= 0 AND priority_score <= 100",
            name="ck_recommendations_priority_score_range",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_recommendations_confidence_range"
        ),
        CheckConstraint(
            "status IN ('PROPOSED', 'ACCEPTED', 'MODIFIED', 'REJECTED', "
            "'IN_PROGRESS', 'COMPLETED')",
            name="ck_recommendations_status",
        ),
        CheckConstraint(
            "observation_count >= 1",
            name="ck_recommendations_observation_count_positive",
        ),
        Index(
            "ix_recommendations_project_status_priority", "project_id", "status", "priority_score"
        ),
        Index("ix_recommendations_risk_key_status", "risk_key", "status"),
        Index("ix_recommendations_scope_active", "project_id", "sprint_id", "resolved_snapshot_id"),
    )

    id: Mapped[str] = str_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    source_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("risk_analyses.id", ondelete="CASCADE"), index=True
    )
    sprint_id: Mapped[str | None] = mapped_column(
        ForeignKey("sprints.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_risk_id: Mapped[str] = mapped_column(
        ForeignKey("risks.id", ondelete="CASCADE"), index=True
    )
    last_seen_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("risk_analyses.id", ondelete="CASCADE"), index=True
    )
    last_seen_risk_id: Mapped[str] = mapped_column(
        ForeignKey("risks.id", ondelete="CASCADE"), index=True
    )
    resolved_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("risk_analyses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observation_count: Mapped[int] = mapped_column(Integer, default=1)
    policy_id: Mapped[str] = mapped_column(String(100), index=True)
    risk_key: Mapped[str] = mapped_column(String(64))
    recommendation_key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text)
    justification: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    priority: Mapped[str] = mapped_column(String(30), index=True)
    priority_score: Mapped[int] = mapped_column(Integer)
    priority_factors: Mapped[dict] = mapped_column(JSON, default=dict)
    priority_justification: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(30))
    impact: Mapped[str] = mapped_column(String(30))
    effort: Mapped[str] = mapped_column(String(30))
    urgency: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Float)
    latest_evidence: Mapped[list] = mapped_column(JSON, default=list)
    latest_severity: Mapped[str] = mapped_column(String(30))
    latest_score: Mapped[float] = mapped_column(Float)
    latest_confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30))
    original_payload: Mapped[dict] = mapped_column(JSON)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RecommendationTransition(Base):
    __tablename__ = "recommendation_transitions"
    __table_args__ = (
        UniqueConstraint(
            "recommendation_id", "sequence", name="uq_recommendation_transitions_sequence"
        ),
        CheckConstraint("sequence >= 1", name="ck_recommendation_transitions_sequence_positive"),
        CheckConstraint(
            "to_status IN ('PROPOSED', 'ACCEPTED', 'MODIFIED', 'REJECTED', "
            "'IN_PROGRESS', 'COMPLETED')",
            name="ck_recommendation_transitions_to_status",
        ),
        CheckConstraint(
            "external_action_executed = false",
            name="ck_recommendation_transitions_no_external_action",
        ),
        Index(
            "ix_recommendation_transitions_recommendation_created",
            "recommendation_id",
            "created_at",
        ),
    )

    id: Mapped[str] = str_pk()
    recommendation_id: Mapped[str] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), index=True
    )
    source_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("risk_analyses.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30))
    actor: Mapped[str] = mapped_column(String(120))
    actor_role: Mapped[str] = mapped_column(String(120))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    justification: Mapped[str] = mapped_column(Text)
    previous_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resulting_payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    external_action_executed: Mapped[bool] = mapped_column(Boolean, default=False)


class RecommendationOutcome(Base):
    __tablename__ = "recommendation_outcomes"
    __table_args__ = (
        UniqueConstraint(
            "recommendation_id",
            "observed_snapshot_id",
            name="uq_recommendation_outcomes_observation",
        ),
        CheckConstraint(
            "status IN ('NOT_YET_MEASURABLE', 'IMPROVEMENT_OBSERVED', "
            "'NO_IMPROVEMENT_OBSERVED', 'INSUFFICIENT_DATA')",
            name="ck_recommendation_outcomes_status",
        ),
    )

    id: Mapped[str] = str_pk()
    recommendation_id: Mapped[str] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), index=True
    )
    baseline_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("risk_analyses.id", ondelete="CASCADE"), index=True
    )
    observed_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("risk_analyses.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(40))
    score_before: Mapped[float] = mapped_column(Float)
    score_after: Mapped[float] = mapped_column(Float)
    score_delta: Mapped[float] = mapped_column(Float)
    contributions_before: Mapped[dict] = mapped_column(JSON, default=dict)
    contributions_after: Mapped[dict] = mapped_column(JSON, default=dict)
    policies_before: Mapped[list] = mapped_column(JSON, default=list)
    policies_after: Mapped[list] = mapped_column(JSON, default=list)
    observation: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QADecisionReview(Base):
    __tablename__ = "qa_decision_reviews"
    __table_args__ = (
        CheckConstraint(
            "suggested_decision IN "
            "('GO', 'GO_WITH_CONDITIONS', 'NO_GO', 'INSUFFICIENT_INFORMATION')",
            name="ck_qa_decision_reviews_suggested_decision",
        ),
        CheckConstraint(
            "final_decision IS NULL OR final_decision IN "
            "('GO', 'GO_WITH_CONDITIONS', 'NO_GO', 'INSUFFICIENT_INFORMATION')",
            name="ck_qa_decision_reviews_final_decision",
        ),
        CheckConstraint(
            "status IN ('CONFIRMED', 'OVERRIDDEN', 'REJECTED')",
            name="ck_qa_decision_reviews_status",
        ),
        CheckConstraint(
            "external_action_executed = false", name="ck_qa_decision_reviews_no_external_action"
        ),
        Index(
            "ix_qa_decision_reviews_project_snapshot_created",
            "project_id",
            "snapshot_id",
            "created_at",
        ),
    )

    id: Mapped[str] = str_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("risk_analyses.id", ondelete="CASCADE"), index=True
    )
    suggested_decision: Mapped[str] = mapped_column(String(40))
    final_decision: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    actor: Mapped[str] = mapped_column(String(120))
    actor_role: Mapped[str] = mapped_column(String(120))
    justification: Mapped[str] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    previous_review_id: Mapped[str | None] = mapped_column(
        ForeignKey("qa_decision_reviews.id", ondelete="SET NULL"), nullable=True, index=True
    )
    external_action_executed: Mapped[bool] = mapped_column(Boolean, default=False)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = str_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    sprint_id: Mapped[str | None] = mapped_column(
        ForeignKey("sprints.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(30))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    content_markdown: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    validated_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IngestionLog(Base):
    __tablename__ = "ingestion_logs"

    id: Mapped[str] = str_pk()
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_type: Mapped[str] = mapped_column(String(20))
    source_name: Mapped[str] = mapped_column(String(500))
    dataset_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reference_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    record_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
