"""Add the week-three QA analysis and explainable risk fields.

Revision ID: 20260718_0003
Revises: 20260714_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260718_0003"
down_revision: str | None = "20260714_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "risk_analyses",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("sprint_id", sa.String(length=64), nullable=True),
        sa.Column("ruleset_version", sa.String(length=50), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("breakdown", sa.JSON(), nullable=False),
        sa.Column("finding_count", sa.Integer(), nullable=False),
        sa.Column("agent_name", sa.String(length=80), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sprint_id"], ["sprints.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risk_analyses_analyzed_at", "risk_analyses", ["analyzed_at"])
    op.create_index("ix_risk_analyses_severity", "risk_analyses", ["severity"])

    with op.batch_alter_table("risks") as batch:
        batch.add_column(sa.Column("analysis_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("priority", sa.Integer(), server_default="4", nullable=False))
        batch.add_column(sa.Column("evidence", sa.JSON(), server_default="{}", nullable=False))
        batch.add_column(sa.Column("recommendation", sa.Text(), server_default="", nullable=False))
        batch.add_column(
            sa.Column(
                "requires_human_validation",
                sa.Boolean(),
                server_default=sa.true(),
                nullable=False,
            )
        )
        batch.create_foreign_key(
            "fk_risks_analysis_id",
            "risk_analyses",
            ["analysis_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_index("ix_risks_analysis_id", ["analysis_id"])


def downgrade() -> None:
    with op.batch_alter_table("risks") as batch:
        batch.drop_index("ix_risks_analysis_id")
        batch.drop_constraint("fk_risks_analysis_id", type_="foreignkey")
        batch.drop_column("requires_human_validation")
        batch.drop_column("recommendation")
        batch.drop_column("evidence")
        batch.drop_column("priority")
        batch.drop_column("analysis_id")
    op.drop_index("ix_risk_analyses_severity", table_name="risk_analyses")
    op.drop_index("ix_risk_analyses_analyzed_at", table_name="risk_analyses")
    op.drop_table("risk_analyses")
