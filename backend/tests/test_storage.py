"""Tests for inventory storage locations, the category backfill, and migration."""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import models
from app.main import _migrate_inventory_columns
from app.services.storage import normalize_storage, storage_from_category
from app.services.vision import parse_items


def _engine():
    return create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )


# --- normalize_storage -------------------------------------------------------
def test_normalize_storage_valid():
    assert normalize_storage("fridge") == "fridge"
    assert normalize_storage("FREEZER") == "freezer"
    assert normalize_storage("  Pantry ") == "pantry"


def test_normalize_storage_invalid_falls_back():
    assert normalize_storage("garage") == "unsorted"
    assert normalize_storage("") == "unsorted"
    assert normalize_storage(None) == "unsorted"


# --- storage_from_category ---------------------------------------------------
def test_storage_from_category_mapping():
    assert storage_from_category("produce") == "fridge"
    assert storage_from_category("dairy") == "fridge"
    assert storage_from_category("frozen") == "freezer"
    assert storage_from_category("pantry") == "pantry"
    assert storage_from_category("bakery") == "counter"


def test_storage_from_category_unknown():
    assert storage_from_category("widgets") == "unsorted"
    assert storage_from_category(None) == "unsorted"


# --- parse_items storage (AI guess, with category fallback) ------------------
def test_parse_items_uses_ai_storage():
    out = parse_items({"items": [{"name": "peas", "category": "produce", "storage": "freezer"}]})
    assert out[0].storage == "freezer"


def test_parse_items_falls_back_to_category():
    # No/invalid storage from the model -> guess from category.
    out = parse_items({"items": [{"name": "milk", "category": "dairy"}]})
    assert out[0].storage == "fridge"
    out = parse_items({"items": [{"name": "x", "category": "frozen", "storage": "nonsense"}]})
    assert out[0].storage == "freezer"


# --- migration: ALTER + one-time backfill ------------------------------------
def test_migration_adds_column_and_backfills():
    eng = _engine()
    # A legacy inventory_items table that predates the storage column.
    with eng.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE inventory_items ("
                "id INTEGER PRIMARY KEY, name VARCHAR, quantity FLOAT, unit VARCHAR, "
                "category VARCHAR, source VARCHAR, extraction_batch_id INTEGER, "
                "added_at DATETIME, updated_at DATETIME)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO inventory_items (name, category) VALUES "
                "('milk','dairy'), ('peas','frozen'), ('mystery', NULL)"
            )
        )

    db = sessionmaker(bind=eng)()
    _migrate_inventory_columns(db, eng)

    rows = {r.name: r.storage for r in db.query(models.InventoryItem).all()}
    assert rows == {"milk": "fridge", "peas": "freezer", "mystery": "unsorted"}
    db.close()


def test_migration_is_idempotent():
    eng = _engine()
    models.Base.metadata.create_all(eng)  # fresh schema already has the column
    db = sessionmaker(bind=eng)()
    db.add(models.InventoryItem(name="bread", category="bakery", storage="counter"))
    db.commit()
    # Running the migration must not disturb an already-set value.
    _migrate_inventory_columns(db, eng)
    item = db.query(models.InventoryItem).filter_by(name="bread").one()
    assert item.storage == "counter"
    db.close()


# --- image backfill ----------------------------------------------------------
def test_backfill_images_only_targets_unfetched(monkeypatch):
    from app.routers import inventory
    from app.services import brave_search

    eng = _engine()
    models.Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()
    db.add(models.InventoryItem(name="milk", storage="fridge"))                       # NULL -> found
    db.add(models.InventoryItem(name="kale", storage="fridge"))                       # NULL -> none
    db.add(models.InventoryItem(name="eggs", storage="fridge", image_url=""))         # already tried
    db.add(models.InventoryItem(name="bread", storage="counter", image_url="http://x"))  # already has
    db.commit()

    results = {"milk": "http://img/milk.jpg", "kale": None}
    seen = []
    monkeypatch.setattr(
        brave_search, "search_image", lambda q: (seen.append(q), results[q])[1]
    )

    inventory.backfill_images(db=db)

    assert sorted(seen) == ["kale", "milk"]  # only the two NULL items were fetched
    by = {i.name: i.image_url for i in db.query(models.InventoryItem).all()}
    assert by["milk"] == "http://img/milk.jpg"
    assert by["kale"] == ""        # miss recorded so it won't refetch
    assert by["eggs"] == ""        # untouched
    assert by["bread"] == "http://x"  # untouched
    db.close()
