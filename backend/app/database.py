"""SQLAlchemy engine, session factory, and declarative base."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings


def _build_engine():
    url = settings.database_url
    if url.startswith("sqlite"):
        # `check_same_thread` is required for SQLite under FastAPI's threadpool.
        return create_engine(url, connect_args={"check_same_thread": False})
    # Postgres (Supabase). `pool_pre_ping` recovers connections dropped by the pooler
    # or by a paused free-tier project; the pool is kept small because Supavisor
    # session mode counts every server-side connection against the project limit.
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=1800,
    )


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
