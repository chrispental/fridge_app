"""Persist owner- and OAuth-client-bound human shopping approvals."""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mcp_shopping_approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", name="fk_mcp_approval_user"), nullable=False),
        sa.Column("client_id", sa.String(255), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("shopping_digest", sa.String(64), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_mcp_shopping_approvals_user_id", "mcp_shopping_approvals", ["user_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE mcp_shopping_approvals ENABLE ROW LEVEL SECURITY")


def downgrade():
    op.drop_table("mcp_shopping_approvals")
