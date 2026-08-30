"""Photos live behind a storage abstraction: `image_path` becomes `image_key`.

Values are untouched — existing absolute paths keep working with the local-disk
backend, new rows hold relative keys (local) or `<user_id>/<uuid>.jpg` (Supabase).

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("extraction_batches") as batch:
        batch.alter_column(
            "image_path",
            new_column_name="image_key",
            existing_type=sa.String(),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("extraction_batches") as batch:
        batch.alter_column(
            "image_key",
            new_column_name="image_path",
            existing_type=sa.String(),
            existing_nullable=False,
        )
