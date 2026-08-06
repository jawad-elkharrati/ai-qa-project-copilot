"""Add the minimal P1-A operational recommendation state.

Revision ID: 20260801_0009
Revises: 20260730_0008
Create Date: 2026-08-01 01:20:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260801_0009"
down_revision: str | None = "20260730_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RECOMMENDATION_STATUSES = (
    "status IN ('PROPOSED', 'ACCEPTED', 'MODIFIED', 'REJECTED', 'IN_PROGRESS', 'COMPLETED')"
)
TRANSITION_STATUSES = (
    "to_status IN ('PROPOSED', 'ACCEPTED', 'MODIFIED', 'REJECTED', 'IN_PROGRESS', 'COMPLETED')"
)
P0_RECOMMENDATION_STATUSES = (
    "status IN ('PROPOSED', 'ACCEPTED', 'MODIFIED', 'REJECTED', 'COMPLETED')"
)
P0_TRANSITION_STATUSES = (
    "to_status IN ('PROPOSED', 'ACCEPTED', 'MODIFIED', 'REJECTED', 'COMPLETED')"
)


def upgrade() -> None:
    with op.batch_alter_table("recommendations") as batch_op:
        batch_op.drop_constraint("ck_recommendations_status", type_="check")
        batch_op.create_check_constraint("ck_recommendations_status", RECOMMENDATION_STATUSES)
    with op.batch_alter_table("recommendation_transitions") as batch_op:
        batch_op.drop_constraint("ck_recommendation_transitions_to_status", type_="check")
        batch_op.create_check_constraint(
            "ck_recommendation_transitions_to_status", TRANSITION_STATUSES
        )


def downgrade() -> None:
    with op.batch_alter_table("recommendation_transitions") as batch_op:
        batch_op.drop_constraint("ck_recommendation_transitions_to_status", type_="check")
        batch_op.create_check_constraint(
            "ck_recommendation_transitions_to_status", P0_TRANSITION_STATUSES
        )
    with op.batch_alter_table("recommendations") as batch_op:
        batch_op.drop_constraint("ck_recommendations_status", type_="check")
        batch_op.create_check_constraint("ck_recommendations_status", P0_RECOMMENDATION_STATUSES)
