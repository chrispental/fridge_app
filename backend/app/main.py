"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .config import settings
from .database import Base, SessionLocal, engine
from .routers import health, inventory, meals, preferences

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables and ensure the singleton preferences row exists.
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.get(models.Preferences, 1) is None:
            db.add(models.Preferences(id=1))
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
