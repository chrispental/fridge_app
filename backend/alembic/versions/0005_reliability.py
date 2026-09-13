"""Durable plan progress and per-user action receipts."""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("meal_plans") as batch:
        batch.add_column(sa.Column("status", sa.String(), nullable=False, server_default="ready"))
        batch.add_column(sa.Column("requested_count", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("error", sa.String(), nullable=True))
    with op.batch_alter_table("meal_plans") as batch:
        batch.alter_column("status", server_default=None)
    op.create_index("uq_meal_plan_active_user", "meal_plans", ["user_id"], unique=True,
                    sqlite_where=sa.text("status IN ('queued', 'generating')"),
                    postgresql_where=sa.text("status IN ('queued', 'generating')"))
    op.create_table(
        "action_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", name="fk_action_receipt_user"), nullable=False),
        sa.Column("action_key", sa.String(200), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "action_key", name="uq_action_receipt_user_key"),
    )
    op.create_index("ix_action_receipts_user_id", "action_receipts", ["user_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE action_receipts ENABLE ROW LEVEL SECURITY')


def downgrade():
    op.drop_table("action_receipts")
    op.drop_index("uq_meal_plan_active_user", table_name="meal_plans")
    with op.batch_alter_table("meal_plans") as batch:
        batch.drop_column("error")
        batch.drop_column("requested_count")
        batch.drop_column("status")
