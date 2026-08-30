"""Run Alembic migrations programmatically.

The app upgrades to head on startup (see `lifespan` in `app/main.py`) so every entry
point — `docker compose up`, bare `uvicorn --reload`, and the tests — migrates the same
way. The Alembic CLI (`cd backend && alembic upgrade head`) shares `alembic/env.py`.
"""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine

BACKEND_DIR = Path(__file__).resolve().parent.parent


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def run_migrations(engine: Engine | None = None) -> None:
    """Upgrade `engine` (default: the app engine) to the latest revision.

    The connection is handed to `alembic/env.py` via `config.attributes`, so the
    migration runs inside one transaction on the caller's engine — which is what lets
    tests migrate an in-memory SQLite database.
    """
    if engine is None:
        from .database import engine as app_engine

        engine = app_engine

    cfg = alembic_config()
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")
