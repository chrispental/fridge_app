"""Shopping rows carry a store section (category) so the list can be walked by aisle.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("shopping_list_items") as batch:
        batch.add_column(sa.Column("category", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("shopping_list_items") as batch:
        batch.drop_column("category")
