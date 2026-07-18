"""Create the foundation schema.

Revision ID: 20260713_0001
Revises:
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("repository_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_key", "projects", ["key"], unique=True)

    op.create_table(
        "sprints",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("capacity_points", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sprints_project_dates", "sprints", ["project_id", "start_date", "end_date"])
    op.create_index("ix_sprints_status", "sprints", ["status"])

    op.create_table(
        "tickets",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("sprint_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.String(length=30), nullable=False),
        sa.Column("assignee", sa.String(length=120), nullable=True),
        sa.Column("story_points", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("blocked_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sprint_id"], ["sprints.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tickets_priority", "tickets", ["priority"])
    op.create_index("ix_tickets_project_status", "tickets", ["project_id", "status"])
    op.create_index("ix_tickets_sprint_priority", "tickets", ["sprint_id", "priority"])
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_type", "tickets", ["type"])

    op.create_table(
        "commits",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("ticket_id", sa.String(length=64), nullable=True),
        sa.Column("sha", sa.String(length=40), nullable=False),
        sa.Column("author", sa.String(length=120), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("additions", sa.Integer(), nullable=False),
        sa.Column("deletions", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_commits_committed_at", "commits", ["committed_at"])
    op.create_index("ix_commits_sha", "commits", ["sha"], unique=True)

    op.create_table(
        "pull_requests",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("ticket_id", sa.String(length=64), nullable=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("author", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("source_branch", sa.String(length=200), nullable=False),
        sa.Column("target_branch", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("changed_files", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pull_requests_status", "pull_requests", ["status"])

    op.create_table(
        "builds",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("sprint_id", sa.String(length=64), nullable=True),
        sa.Column("pull_request_id", sa.String(length=64), nullable=True),
        sa.Column("pipeline_name", sa.String(length=150), nullable=False),
        sa.Column("branch", sa.String(length=200), nullable=False),
        sa.Column("commit_sha", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pull_request_id"], ["pull_requests.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sprint_id"], ["sprints.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_builds_project_status", "builds", ["project_id", "status"])
    op.create_index("ix_builds_status", "builds", ["status"])

    op.create_table(
        "test_results",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("build_id", sa.String(length=64), nullable=False),
        sa.Column("suite_name", sa.String(length=150), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["build_id"], ["builds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_results_status", "test_results", ["status"])

    op.create_table(
        "metrics",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("sprint_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sprint_id"], ["sprints.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_metrics_project_name_date", "metrics", ["project_id", "name", "measured_at"]
    )

    op.create_table(
        "risks",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("sprint_id", sa.String(length=64), nullable=True),
        sa.Column("rule_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sprint_id"], ["sprints.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risks_rule_id", "risks", ["rule_id"])
    op.create_index("ix_risks_severity", "risks", ["severity"])

    op.create_table(
        "reports",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("sprint_id", sa.String(length=64), nullable=True),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_by", sa.String(length=120), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sprint_id"], ["sprints.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reports_type", "reports", ["type"])


def downgrade() -> None:
    for table in (
        "reports",
        "risks",
        "metrics",
        "test_results",
        "builds",
        "pull_requests",
        "commits",
        "tickets",
        "sprints",
        "projects",
    ):
        op.drop_table(table)
