"""Saved recipes: a `favorite` flag on meals (imported recipes use status 'saved').

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("meals") as batch:
        batch.add_column(sa.Column("favorite", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("meals") as batch:
        batch.alter_column("favorite", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("meals") as batch:
        batch.drop_column("favorite")
