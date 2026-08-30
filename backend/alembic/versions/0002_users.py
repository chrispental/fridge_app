"""Users + per-user ownership.

Adds the `users` table and a NOT NULL `user_id` to every user-owned table. Existing
rows (from the single-user era) are assigned to the fixed local user so nothing is
orphaned. On Postgres, row-level security is switched on for every table with *no*
policies: the backend connects as the table owner and is unaffected, while Supabase's
auto-generated REST API (reachable with the publishable key that ships in the browser
bundle) is denied outright.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.config import DEFAULT_LOCAL_USER_ID

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OWNED_TABLES = (
    "preferences",
    "extraction_batches",
    "inventory_items",
    "meals",
    "shopping_list_items",
    "meal_plans",
)


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("last_seen_at", sa.DateTime, nullable=True),
    )
    users = sa.table(
        "users",
        sa.column("id", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("last_seen_at", sa.DateTime),
    )
    now = sa.func.now() if bind.dialect.name != "sqlite" else sa.func.current_timestamp()
    bind.execute(users.insert().values(id=DEFAULT_LOCAL_USER_ID, created_at=now, last_seen_at=now))

    for table in OWNED_TABLES:
        # 1) add nullable; 2) claim existing rows for the local user; 3) tighten.
        # Two batch blocks because the UPDATE has to sit between them (SQLite batch
        # mode rebuilds the table on each block).
        with op.batch_alter_table(table) as batch:
            # Named FK: SQLite batch mode can't emit an anonymous constraint.
            batch.add_column(
                sa.Column(
                    "user_id",
                    sa.String(36),
                    sa.ForeignKey("users.id", name=f"fk_{table}_user_id_users"),
                    nullable=True,
                )
            )
        t = sa.table(table, sa.column("user_id", sa.String))
        bind.execute(t.update().where(t.c.user_id.is_(None)).values(user_id=DEFAULT_LOCAL_USER_ID))
        with op.batch_alter_table(table) as batch:
            batch.alter_column("user_id", existing_type=sa.String(36), nullable=False)
        op.create_index(
            f"ix_{table}_user_id", table, ["user_id"], unique=(table == "preferences")
        )

    if bind.dialect.name == "postgresql":
        for table in OWNED_TABLES + ("users", "meal_plan_entries"):
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in OWNED_TABLES + ("users", "meal_plan_entries"):
            op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
    for table in reversed(OWNED_TABLES):
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        with op.batch_alter_table(table) as batch:
            batch.drop_column("user_id")
    op.drop_table("users")
