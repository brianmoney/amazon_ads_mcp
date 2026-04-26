"""Alembic environment for the warehouse schema."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from amazon_ads_mcp.config.settings import Settings
from amazon_ads_mcp.warehouse.schema import metadata


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def _database_url() -> str:
    settings = Settings()
    if not settings.warehouse_database_dsn:
        raise RuntimeError("WAREHOUSE_DATABASE_DSN is required for Alembic migrations.")
    return settings.warehouse_database_dsn


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
