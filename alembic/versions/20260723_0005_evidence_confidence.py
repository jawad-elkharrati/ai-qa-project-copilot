"""Add persisted evidence chains and confidence details.

Revision ID: 20260723_0005
Revises: 20260723_0004
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260723_0005"
down_revision: str | None = "20260723_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("risk_analyses") as batch:
        batch.add_column(
            sa.Column("confidence_details", sa.JSON(), server_default="{}", nullable=False)
        )

    op.create_table(
        "risk_evidence",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("risk_id", sa.String(length=64), nullable=False),
        sa.Column("analysis_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("relation", sa.String(length=100), nullable=False),
        sa.Column("evidence_order", sa.Integer(), nullable=False),
        sa.Column("contribution", sa.Float(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "evidence_order >= 0",
            name="ck_risk_evidence_order_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["risk_analyses.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["risk_id"], ["risks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "risk_id",
            "source_type",
            "source_id",
            "relation",
            name="uq_risk_evidence_source_relation",
        ),
    )
    op.create_index("ix_risk_evidence_analysis_id", "risk_evidence", ["analysis_id"])
    op.create_index("ix_risk_evidence_risk_id", "risk_evidence", ["risk_id"])


def downgrade() -> None:
    op.drop_index("ix_risk_evidence_risk_id", table_name="risk_evidence")
    op.drop_index("ix_risk_evidence_analysis_id", table_name="risk_evidence")
    op.drop_table("risk_evidence")
    with op.batch_alter_table("risk_analyses") as batch:
        batch.drop_column("confidence_details")
