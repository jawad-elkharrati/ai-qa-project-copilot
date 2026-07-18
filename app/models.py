from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
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


class Risk(Base):
    __tablename__ = "risks"

    id: Mapped[str] = str_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    sprint_id: Mapped[str | None] = mapped_column(
        ForeignKey("sprints.id", ondelete="SET NULL"), nullable=True
    )
    rule_id: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(30), index=True)
    score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    source_type: Mapped[str] = mapped_column(String(50))
    source_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
