"""RLS on `alembic_version`.

Revision 0002 switched on row-level security for every app table, but Alembic
creates its own version table outside any revision, so it was left uncovered —
writable through Supabase's auto-generated REST API with the publishable key
(Supabase lint `rls_disabled_in_public`). Same treatment as the app tables:
RLS enabled with no policies; the backend connects as the table owner and is
unaffected, PostgREST is denied outright.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-01
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY")
