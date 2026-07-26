"""Add append-only human decisions for risk recommendations.

Revision ID: 20260724_0006
Revises: 20260723_0005
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260724_0006"
down_revision: str | None = "20260723_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "risk_decisions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("risk_id", sa.String(length=64), nullable=False),
        sa.Column("analysis_id", sa.String(length=64), nullable=False),
        sa.Column("policy_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("original_recommendation", sa.Text(), nullable=False),
        sa.Column("modified_recommendation", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(length=120), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_decision_id", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'modified', 'rejected')",
            name="ck_risk_decisions_status",
        ),
        sa.CheckConstraint(
            "status = 'pending' OR "
            "(decided_by IS NOT NULL AND length(trim(decided_by)) > 0 "
            "AND decided_at IS NOT NULL)",
            name="ck_risk_decisions_actor_for_final_status",
        ),
        sa.CheckConstraint(
            "status != 'modified' OR "
            "(modified_recommendation IS NOT NULL "
            "AND length(trim(modified_recommendation)) > 0)",
            name="ck_risk_decisions_modified_text",
        ),
        sa.CheckConstraint(
            "status != 'rejected' OR (comment IS NOT NULL AND length(trim(comment)) > 0)",
            name="ck_risk_decisions_rejection_comment",
        ),
        sa.ForeignKeyConstraint(["analysis_id"], ["risk_analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["risk_id"], ["risks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["previous_decision_id"],
            ["risk_decisions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risk_decisions_analysis_id", "risk_decisions", ["analysis_id"])
    op.create_index("ix_risk_decisions_policy_id", "risk_decisions", ["policy_id"])
    op.create_index(
        "ix_risk_decisions_previous_decision_id",
        "risk_decisions",
        ["previous_decision_id"],
    )
    op.create_index("ix_risk_decisions_risk_id", "risk_decisions", ["risk_id"])
    op.create_index(
        "ix_risk_decisions_risk_created",
        "risk_decisions",
        ["risk_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_risk_decisions_risk_created", table_name="risk_decisions")
    op.drop_index("ix_risk_decisions_risk_id", table_name="risk_decisions")
    op.drop_index("ix_risk_decisions_previous_decision_id", table_name="risk_decisions")
    op.drop_index("ix_risk_decisions_policy_id", table_name="risk_decisions")
    op.drop_index("ix_risk_decisions_analysis_id", table_name="risk_decisions")
    op.drop_table("risk_decisions")
