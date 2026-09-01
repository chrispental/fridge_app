"""Alembic migrations: head must match the models, re-running must be a no-op, and a
pre-Alembic SQLite file of any vintage must upgrade in place.

Set TEST_DATABASE_URL (e.g. postgresql+psycopg://...) to run the dialect-neutral
tests against a real Postgres; the legacy-SQLite test always uses SQLite.
"""
import os

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.migrations import run_migrations
from app.services.staples import DEFAULT_STAPLES

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")


def _engine(tmp_path):
    """A fresh, empty database: a temp SQLite file by default, or TEST_DATABASE_URL
    (wiped first) when set."""
    if TEST_DATABASE_URL:
        eng = create_engine(TEST_DATABASE_URL)
        with eng.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(text(f'DROP TABLE IF EXISTS "{table.name}" CASCADE'))
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        return eng
    return create_engine(f"sqlite:///{tmp_path / 'migrate.db'}")


def _sqlite_engine(tmp_path):
    return create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")


def _schema_diff(engine) -> list:
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        return compare_metadata(ctx, Base.metadata)


def test_head_matches_models(tmp_path):
    """The load-bearing test: editing models.py without a revision fails here."""
    eng = _engine(tmp_path)
    run_migrations(eng)
    assert _schema_diff(eng) == []


def test_migrations_are_idempotent(tmp_path):
    eng = _engine(tmp_path)
    run_migrations(eng)
    run_migrations(eng)
    assert _schema_diff(eng) == []
    with eng.connect() as conn:
        (version,) = conn.execute(text("SELECT version_num FROM alembic_version")).one()
    assert version


def test_create_all_matches_head(tmp_path):
    """Unit tests use `create_all` on in-memory SQLite for speed; make sure that
    shortcut and the migrations describe the same schema."""
    eng = _sqlite_engine(tmp_path)
    Base.metadata.create_all(eng)
    assert _schema_diff(eng) == []


def test_legacy_sqlite_upgrades_in_place(tmp_path):
    """A `data/fridge.db` created before storage/image_url/expires_at/pantry_staples/name
    existed (and before Alembic) upgrades with data intact and backfilled."""
    eng = _sqlite_engine(tmp_path)
    with eng.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE extraction_batches ("
                "id INTEGER NOT NULL, image_path VARCHAR NOT NULL, raw_ai_response JSON, "
                "status VARCHAR NOT NULL, created_at DATETIME NOT NULL, PRIMARY KEY (id))"
            )
        )
        conn.execute(
            text(
                # Exactly what `create_all` emitted at that vintage.
                "CREATE TABLE inventory_items ("
                "id INTEGER NOT NULL, name VARCHAR NOT NULL, quantity FLOAT, "
                "unit VARCHAR NOT NULL, category VARCHAR, source VARCHAR NOT NULL, "
                "extraction_batch_id INTEGER, added_at DATETIME NOT NULL, updated_at DATETIME, "
                "PRIMARY KEY (id), FOREIGN KEY(extraction_batch_id) REFERENCES extraction_batches (id))"
            )
        )
        conn.execute(
            text(
                "INSERT INTO inventory_items (name, category, unit, source, added_at) VALUES "
                "('milk','dairy','unknown','manual','2026-01-01 00:00:00'), "
                "('peas','frozen','unknown','manual','2026-01-01 00:00:00'), "
                "('mystery', NULL,'unknown','manual','2026-01-01 00:00:00')"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE preferences ("
                "id INTEGER NOT NULL, household_size INTEGER NOT NULL, allergies JSON NOT NULL, "
                "dietary_restrictions JSON NOT NULL, equipment JSON NOT NULL, "
                "max_complexity INTEGER NOT NULL, disliked_ingredients JSON NOT NULL, "
                "disliked_cuisines JSON NOT NULL, no_repeat_days INTEGER NOT NULL, "
                "location VARCHAR NOT NULL, onboarded BOOLEAN NOT NULL, updated_at DATETIME, "
                "PRIMARY KEY (id))"
            )
        )
        conn.execute(
            text(
                "INSERT INTO preferences (id, household_size, allergies, dietary_restrictions, "
                "equipment, max_complexity, disliked_ingredients, disliked_cuisines, "
                "no_repeat_days, location, onboarded) VALUES "
                "(1, 2, '[]', '[]', '[]', 3, '[]', '[]', 14, '', 0)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE meals ("
                "id INTEGER NOT NULL, title VARCHAR NOT NULL, title_normalized VARCHAR NOT NULL, "
                "cuisine VARCHAR, recipe_json JSON NOT NULL, status VARCHAR NOT NULL, "
                "suggested_at DATETIME NOT NULL, cooked_at DATETIME, delivery_ordered_at DATETIME, "
                "PRIMARY KEY (id))"
            )
        )
        conn.execute(text("CREATE INDEX ix_meals_title_normalized ON meals (title_normalized)"))
        conn.execute(
            text(
                "INSERT INTO meals (title, title_normalized, recipe_json, status, suggested_at) "
                "VALUES ('Old Chili', 'old chili', '{}', 'cooked', '2026-01-01 00:00:00')"
            )
        )

    run_migrations(eng)

    assert _schema_diff(eng) == []
    db = sessionmaker(bind=eng)()
    try:
        rows = {r.name: r.storage for r in db.query(models.InventoryItem).all()}
        assert rows == {"milk": "fridge", "peas": "freezer", "mystery": "unsorted"}
        assert db.query(models.InventoryItem).filter_by(name="milk").one().expires_at is None

        prefs = db.get(models.Preferences, 1)
        assert prefs.household_size == 2
        assert prefs.name == ""
        assert prefs.pantry_staples == list(DEFAULT_STAPLES)

        meal = db.query(models.Meal).one()
        assert meal.title == "Old Chili" and meal.rating is None
        meal.rating = 1
        db.commit()
    finally:
        db.close()

    # Re-running against the upgraded file is a no-op.
    run_migrations(eng)
    assert _schema_diff(eng) == []


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="Postgres-only check")
def test_every_public_table_has_rls(tmp_path):
    """On Postgres every table in `public` — alembic_version included — must have RLS
    enabled, or it is writable through Supabase's auto-generated REST API with the
    publishable key. A new table failing here needs `ENABLE ROW LEVEL SECURITY` in
    its migration (see revisions 0002 and 0004)."""
    eng = _engine(tmp_path)
    run_migrations(eng)
    with eng.connect() as conn:
        unprotected = conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND NOT rowsecurity"
            )
        ).scalars().all()
    assert unprotected == []


@pytest.mark.skipif(bool(TEST_DATABASE_URL), reason="SQLite-only check")
def test_fresh_sqlite_has_version_table(tmp_path):
    eng = _sqlite_engine(tmp_path)
    run_migrations(eng)
    assert inspect(eng).has_table("alembic_version")
