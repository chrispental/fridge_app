"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import engine
from .migrations import run_migrations
from .routers import health, inventory, meals, plans, preferences, shopping
from .services.blob_storage import get_blob_storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bring the schema to the latest Alembic revision (creates it from scratch on a
    # fresh database). Per-user rows are created lazily on first request.
    run_migrations(engine)
    logger.info("Auth mode: %s", "supabase" if settings.auth_enabled else "local (single user)")
    if settings.auth_enabled and settings.database_url.startswith("sqlite"):
        logger.warning(
            "SUPABASE_URL is set but DATABASE_URL is SQLite — multi-user data is being "
            "written to a local file. Point DATABASE_URL at the Supabase Postgres pooler."
        )
    get_blob_storage().check()
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
app.include_router(shopping.router)
