"""Baseline: the pre-Alembic schema, applied idempotently.

Databases created before this revision have no `alembic_version` table and may be of
any vintage (the app used `create_all` plus three hand-rolled `ALTER TABLE ... ADD
COLUMN` migrators). So this revision:

* creates each table only if it is missing,
* otherwise adds any column the old migrators would have added,
* backfills `inventory_items.storage` from category and seeds default pantry staples,
  exactly as the old code did,
* then tightens the NOT NULL constraints the old ALTERs left loose.

Fresh databases (SQLite or Postgres) simply get every table created.

Revision ID: 0001
Revises:
Create Date: 2026-08-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Pure helpers with no DB coupling — safe to import from the app.
from app.services.staples import DEFAULT_STAPLES
from app.services.storage import storage_from_category

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def _columns(table: str) -> dict[str, dict]:
    return {c["name"]: c for c in _inspector().get_columns(table)}


def _ensure_table(table: str, *columns: sa.Column, indexes: list[tuple[str, list[str]]] = ()) -> bool:
    """Create `table` if missing; otherwise add any missing columns. Returns True if
    the table was created fresh (so callers can skip legacy backfills)."""
    if not _inspector().has_table(table):
        op.create_table(table, *columns)
        for name, cols in indexes:
            op.create_index(name, table, cols)
        return True

    existing = _columns(table)
    missing = [c for c in columns if c.name not in existing]
    if missing:
        with op.batch_alter_table(table) as batch:
            for col in missing:
                # Add as nullable first; NOT NULL is applied after the backfill below.
                batch.add_column(sa.Column(col.name, col.type, nullable=True))
    existing_indexes = {ix["name"] for ix in _inspector().get_indexes(table)}
    for name, cols in indexes:
        if name not in existing_indexes:
            op.create_index(name, table, cols)
    return False


def _set_not_null(table: str, column: str, type_: sa.types.TypeEngine) -> None:
    if _columns(table)[column]["nullable"]:
        with op.batch_alter_table(table) as batch:
            batch.alter_column(column, existing_type=type_, nullable=False)


def upgrade() -> None:
    bind = op.get_bind()

    # ---- preferences ----------------------------------------------------------
    fresh = _ensure_table(
        "preferences",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("household_size", sa.Integer, nullable=False),
        sa.Column("allergies", sa.JSON, nullable=False),
        sa.Column("dietary_restrictions", sa.JSON, nullable=False),
        sa.Column("equipment", sa.JSON, nullable=False),
        sa.Column("max_complexity", sa.Integer, nullable=False),
        sa.Column("disliked_ingredients", sa.JSON, nullable=False),
        sa.Column("disliked_cuisines", sa.JSON, nullable=False),
        sa.Column("no_repeat_days", sa.Integer, nullable=False),
        sa.Column("location", sa.String, nullable=False),
        sa.Column("pantry_staples", sa.JSON, nullable=False),
        sa.Column("onboarded", sa.Boolean, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    if not fresh:
        prefs = sa.table(
            "preferences",
            sa.column("id", sa.Integer),
            sa.column("name", sa.String),
            sa.column("pantry_staples", sa.JSON),
        )
        bind.execute(prefs.update().where(prefs.c.name.is_(None)).values(name=""))
        # Seed default staples where the column is NULL or an empty list.
        for row in bind.execute(sa.select(prefs.c.id, prefs.c.pantry_staples)).all():
            if not row.pantry_staples:
                bind.execute(
                    prefs.update()
                    .where(prefs.c.id == row.id)
                    .values(pantry_staples=list(DEFAULT_STAPLES))
                )
        _set_not_null("preferences", "name", sa.String())
        _set_not_null("preferences", "pantry_staples", sa.JSON())

    # ---- extraction_batches ---------------------------------------------------
    _ensure_table(
        "extraction_batches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("image_path", sa.String, nullable=False),
        sa.Column("raw_ai_response", sa.JSON, nullable=True),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    # ---- inventory_items ------------------------------------------------------
    fresh = _ensure_table(
        "inventory_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("quantity", sa.Float, nullable=True),
        sa.Column("unit", sa.String, nullable=False),
        sa.Column("category", sa.String, nullable=True),
        sa.Column("storage", sa.String, nullable=False),
        sa.Column("image_url", sa.String, nullable=True),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("expires_at", sa.Date, nullable=True),
        sa.Column(
            "extraction_batch_id",
            sa.Integer,
            sa.ForeignKey("extraction_batches.id"),
            nullable=True,
        ),
        sa.Column("added_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    if not fresh:
        items = sa.table(
            "inventory_items",
            sa.column("id", sa.Integer),
            sa.column("category", sa.String),
            sa.column("storage", sa.String),
        )
        pending = bind.execute(
            sa.select(items.c.id, items.c.category).where(items.c.storage.is_(None))
        ).all()
        for row in pending:
            bind.execute(
                items.update()
                .where(items.c.id == row.id)
                .values(storage=storage_from_category(row.category))
            )
        _set_not_null("inventory_items", "storage", sa.String())

    # ---- meals ----------------------------------------------------------------
    _ensure_table(
        "meals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("title_normalized", sa.String, nullable=False),
        sa.Column("cuisine", sa.String, nullable=True),
        sa.Column("recipe_json", sa.JSON, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("suggested_at", sa.DateTime, nullable=False),
        sa.Column("cooked_at", sa.DateTime, nullable=True),
        sa.Column("delivery_ordered_at", sa.DateTime, nullable=True),
        sa.Column("rating", sa.Integer, nullable=True),
        sa.Column("feedback_tags", sa.JSON, nullable=True),
        sa.Column("feedback_notes", sa.String, nullable=True),
        sa.Column("feedback_at", sa.DateTime, nullable=True),
        indexes=[("ix_meals_title_normalized", ["title_normalized"])],
    )

    # ---- shopping_list_items --------------------------------------------------
    _ensure_table(
        "shopping_list_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("quantity", sa.Float, nullable=True),
        sa.Column("unit", sa.String, nullable=False),
        sa.Column("checked", sa.Boolean, nullable=False),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("checked_at", sa.DateTime, nullable=True),
    )

    # ---- meal_plans / meal_plan_entries ---------------------------------------
    _ensure_table(
        "meal_plans",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    _ensure_table(
        "meal_plan_entries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("plan_id", sa.Integer, sa.ForeignKey("meal_plans.id"), nullable=False),
        sa.Column("slot_index", sa.Integer, nullable=False),
        sa.Column("meal_id", sa.Integer, sa.ForeignKey("meals.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    # The baseline is the floor; there is nothing older to go back to.
    for table in (
        "meal_plan_entries",
        "meal_plans",
        "shopping_list_items",
        "meals",
        "inventory_items",
        "extraction_batches",
        "preferences",
    ):
        op.drop_table(table)
