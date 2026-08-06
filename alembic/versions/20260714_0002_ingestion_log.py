"""Add the week-two ingestion journal.

Revision ID: 20260714_0002
Revises: 20260713_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260714_0002"
down_revision: str | None = "20260713_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_logs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_name", sa.String(length=500), nullable=False),
        sa.Column("dataset_version", sa.String(length=30), nullable=True),
        sa.Column("reference_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("record_counts", sa.JSON(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_logs_project_id", "ingestion_logs", ["project_id"])
    op.create_index("ix_ingestion_logs_status", "ingestion_logs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ingestion_logs_status", table_name="ingestion_logs")
    op.drop_index("ix_ingestion_logs_project_id", table_name="ingestion_logs")
    op.drop_table("ingestion_logs")
