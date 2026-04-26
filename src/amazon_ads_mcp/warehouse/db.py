"""Database helpers for the warehouse runtime."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Connection, Engine, create_engine

from ..config.settings import Settings


_warehouse_engine: Engine | None = None


def _validate_postgres_url(url: str) -> str:
    normalized = str(url or "").strip()
    if not normalized:
        raise ValueError("WAREHOUSE_DATABASE_DSN is required for the warehouse worker.")
    if not normalized.startswith(("postgresql://", "postgresql+psycopg://")):
        raise ValueError(
            "The warehouse worker only supports Postgres DSNs starting with "
            "postgresql:// or postgresql+psycopg://."
        )
    return normalized


def create_warehouse_engine(url: str | None = None) -> Engine:
    """Create the singleton warehouse engine."""
    resolved_url = _validate_postgres_url(url or Settings().warehouse_database_dsn or "")
    return create_engine(
        resolved_url,
        future=True,
        pool_pre_ping=True,
    )


def get_warehouse_engine() -> Engine:
    """Return a cached Postgres engine for warehouse operations."""
    global _warehouse_engine
    if _warehouse_engine is None:
        _warehouse_engine = create_warehouse_engine()
    return _warehouse_engine


def dispose_warehouse_engine() -> None:
    """Dispose the cached warehouse engine."""
    global _warehouse_engine
    if _warehouse_engine is not None:
        _warehouse_engine.dispose()
        _warehouse_engine = None


@contextmanager
def warehouse_connection(engine: Engine | None = None) -> Iterator[Connection]:
    """Open a transactional warehouse connection."""
    resolved_engine = engine or get_warehouse_engine()
    with resolved_engine.begin() as connection:
        yield connection
