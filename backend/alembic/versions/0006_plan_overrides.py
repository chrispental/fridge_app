"""Per-plan serving count and start date chosen when a plan is created.

Both are nullable: NULL servings means household size, NULL start_date means the
plan shows undated "Day N" slots (every pre-existing plan).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("meal_plans") as batch:
        batch.add_column(sa.Column("servings", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("start_date", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("meal_plans") as batch:
        batch.drop_column("start_date")
        batch.drop_column("servings")
