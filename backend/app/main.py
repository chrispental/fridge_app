"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from . import models
from .config import settings
from .database import Base, SessionLocal, engine
from .routers import health, inventory, meals, plans, preferences
from .services.staples import DEFAULT_STAPLES
from .services.storage import storage_from_category

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _migrate_inventory_columns(db, db_engine) -> None:
    """Add columns missing from a pre-existing inventory_items table (no Alembic).

    `create_all` only creates missing tables, never new columns. So on an existing
    table we ALTER in the new columns. `storage` is then backfilled once from each
    item's category; `image_url` is left NULL (filled on demand via the backfill
    endpoint). New databases already have the columns, so this no-ops.
    """
    columns = {c["name"] for c in inspect(db_engine).get_columns("inventory_items")}
    with db_engine.begin() as conn:
        if "storage" not in columns:
            conn.execute(text("ALTER TABLE inventory_items ADD COLUMN storage VARCHAR"))
            logger.info("Added inventory_items.storage column")
        if "image_url" not in columns:
            conn.execute(text("ALTER TABLE inventory_items ADD COLUMN image_url VARCHAR"))
            logger.info("Added inventory_items.image_url column")

    pending = (
        db.query(models.InventoryItem)
        .filter(models.InventoryItem.storage.is_(None))
        .all()
    )
    for item in pending:
        item.storage = storage_from_category(item.category)
    if pending:
        db.commit()
        logger.info("Backfilled storage for %d existing item(s)", len(pending))


def _migrate_preferences_columns(db, db_engine) -> None:
    """Add the pantry_staples column to a pre-existing preferences table (no Alembic).

    `create_all` never adds columns to an existing table, so we ALTER it in and seed
    the singleton row with the default staples. New databases already have the column
    (and the row is seeded at creation), so this no-ops.
    """
    columns = {c["name"] for c in inspect(db_engine).get_columns("preferences")}
    if "pantry_staples" not in columns:
        with db_engine.begin() as conn:
            conn.execute(text("ALTER TABLE preferences ADD COLUMN pantry_staples JSON"))
        logger.info("Added preferences.pantry_staples column")

    prefs = db.get(models.Preferences, 1)
    if prefs is not None and not prefs.pantry_staples:
        prefs.pantry_staples = list(DEFAULT_STAPLES)
        db.commit()
        logger.info("Seeded default pantry staples")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables and ensure the singleton preferences row exists.
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Run column migrations BEFORE any ORM query against these tables: the mapped
        # models reference columns that create_all won't add to a pre-existing table,
        # so querying first would fail with "no such column".
        _migrate_inventory_columns(db, engine)
        _migrate_preferences_columns(db, engine)
        if db.get(models.Preferences, 1) is None:
            db.add(models.Preferences(id=1, pantry_staples=list(DEFAULT_STAPLES)))
            db.commit()
    finally:
        db.close()
    yield


app = FastAPI(
    title="Fridge Meal Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(preferences.router)
app.include_router(inventory.router)
app.include_router(meals.router)
app.include_router(plans.router)
