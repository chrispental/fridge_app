"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from . import models
from .config import settings
from .database import Base, SessionLocal, engine
from .routers import health, inventory, meals, preferences
from .services.storage import storage_from_category

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _migrate_inventory_storage(db, db_engine) -> None:
    """Add the `storage` column to an existing DB and backfill it once.

    There is no Alembic; `create_all` only creates missing tables, never new
    columns. So on a pre-existing `inventory_items` table we add the column via
    ALTER (existing rows get NULL) and then seed each NULL from its `category`.
    New databases already have the column with its default, so this no-ops.
    """
    columns = {c["name"] for c in inspect(db_engine).get_columns("inventory_items")}
    if "storage" not in columns:
        with db_engine.begin() as conn:
            conn.execute(text("ALTER TABLE inventory_items ADD COLUMN storage VARCHAR"))
        logger.info("Added inventory_items.storage column")

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables and ensure the singleton preferences row exists.
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.get(models.Preferences, 1) is None:
            db.add(models.Preferences(id=1))
            db.commit()
        _migrate_inventory_storage(db, engine)
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
