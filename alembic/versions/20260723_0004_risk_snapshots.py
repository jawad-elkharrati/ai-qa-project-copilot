"""Add immutable risk snapshot metadata and score contributions.

Revision ID: 20260723_0004
Revises: 20260718_0003
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260723_0004"
down_revision: str | None = "20260718_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("risk_analyses") as batch:
        batch.add_column(
            sa.Column("policy_hash", sa.String(length=64), server_default="legacy", nullable=False)
        )
        batch.add_column(
            sa.Column(
                "input_fingerprint",
                sa.String(length=64),
                server_default="legacy",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "result_fingerprint",
                sa.String(length=64),
                server_default="legacy",
                nullable=False,
            )
        )
        batch.add_column(sa.Column("previous_snapshot_id", sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column("confidence_score", sa.Float(), server_default="1", nullable=False)
        )
        batch.add_column(
            sa.Column("evidence_coverage", sa.Float(), server_default="1", nullable=False)
        )
        batch.add_column(
            sa.Column("missing_information", sa.JSON(), server_default="[]", nullable=False)
        )
        batch.add_column(
            sa.Column("stale_information", sa.JSON(), server_default="[]", nullable=False)
        )
        batch.create_foreign_key(
            "fk_risk_analyses_previous_snapshot_id",
            "risk_analyses",
            ["previous_snapshot_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "ix_risk_analyses_previous_snapshot_id",
            ["previous_snapshot_id"],
        )
        batch.create_index(
            "ix_risk_analyses_scope_date",
            ["project_id", "sprint_id", "analyzed_at"],
        )
        batch.create_check_constraint(
            "ck_risk_analyses_score_range",
            "score >= 0 AND score <= 100",
        )
        batch.create_check_constraint(
            "ck_risk_analyses_confidence_range",
            "confidence_score >= 0 AND confidence_score <= 1",
        )
        batch.create_check_constraint(
            "ck_risk_analyses_evidence_coverage_range",
            "evidence_coverage >= 0 AND evidence_coverage <= 1",
        )

    op.create_table(
        "risk_contributions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("analysis_id", sa.String(length=64), nullable=False),
        sa.Column("policy_id", sa.String(length=100), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("factor", sa.String(length=100), nullable=False),
        sa.Column("raw_value", sa.JSON(), nullable=True),
        sa.Column("normalized_value", sa.Float(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("contribution", sa.Float(), nullable=False),
        sa.Column("finding_count", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "normalized_value >= 0 AND normalized_value <= 1",
            name="ck_risk_contributions_normalized_range",
        ),
        sa.CheckConstraint(
            "weight >= 0 AND weight <= 100",
            name="ck_risk_contributions_weight_range",
        ),
        sa.CheckConstraint(
            "contribution >= 0 AND contribution <= weight",
            name="ck_risk_contributions_value_range",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["risk_analyses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "analysis_id",
            "policy_id",
            name="uq_risk_contributions_analysis_policy",
        ),
    )
    op.create_index(
        "ix_risk_contributions_analysis_id",
        "risk_contributions",
        ["analysis_id"],
    )
    op.create_index(
        "ix_risk_contributions_policy_id",
        "risk_contributions",
        ["policy_id"],
    )

    with op.batch_alter_table("risks") as batch:
        batch.create_check_constraint(
            "ck_risks_score_range",
            "score >= 0 AND score <= 100",
        )
        batch.create_check_constraint(
            "ck_risks_confidence_range",
            "confidence >= 0 AND confidence <= 1",
        )
        batch.create_check_constraint(
            "ck_risks_priority_range",
            "priority >= 1 AND priority <= 4",
        )


def downgrade() -> None:
    with op.batch_alter_table("risks") as batch:
        batch.drop_constraint("ck_risks_priority_range", type_="check")
        batch.drop_constraint("ck_risks_confidence_range", type_="check")
        batch.drop_constraint("ck_risks_score_range", type_="check")

    op.drop_index("ix_risk_contributions_policy_id", table_name="risk_contributions")
    op.drop_index("ix_risk_contributions_analysis_id", table_name="risk_contributions")
    op.drop_table("risk_contributions")

    with op.batch_alter_table("risk_analyses") as batch:
        batch.drop_constraint(
            "ck_risk_analyses_evidence_coverage_range",
            type_="check",
        )
        batch.drop_constraint("ck_risk_analyses_confidence_range", type_="check")
        batch.drop_constraint("ck_risk_analyses_score_range", type_="check")
        batch.drop_index("ix_risk_analyses_scope_date")
        batch.drop_index("ix_risk_analyses_previous_snapshot_id")
        batch.drop_constraint(
            "fk_risk_analyses_previous_snapshot_id",
            type_="foreignkey",
        )
        batch.drop_column("stale_information")
        batch.drop_column("missing_information")
        batch.drop_column("evidence_coverage")
        batch.drop_column("confidence_score")
        batch.drop_column("previous_snapshot_id")
        batch.drop_column("result_fingerprint")
        batch.drop_column("input_fingerprint")
        batch.drop_column("policy_hash")
