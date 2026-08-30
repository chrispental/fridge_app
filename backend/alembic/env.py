"""Alembic environment.

Two entry points share this file:

* The CLI (`alembic upgrade head`, `alembic revision --autogenerate`) — builds an engine
  from `settings.database_url`.
* The app / tests — `app.migrations.run_migrations()` hands us an already-open
  connection via `config.attributes["connection"]` so migrations run inside the
  caller's transaction and against the caller's engine (in-memory SQLite in tests).

SQLite can't ALTER most things in place, so `render_as_batch` is enabled for it: Alembic
rewrites ALTERs as create-copy-drop. On Postgres batch mode is a passthrough.
"""
from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.database import Base
import app.models  # noqa: F401  — populate Base.metadata for autogenerate

config = context.config
target_metadata = Base.metadata


def _configure_and_run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: emit SQL without a DB connection."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=settings.database_url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _configure_and_run(connection)
        return

    config.set_main_option("sqlalchemy.url", settings.database_url)
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as conn:
        _configure_and_run(conn)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
