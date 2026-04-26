"""Alembic helpers for the warehouse schema."""

from __future__ import annotations

from alembic import command
from alembic.config import Config


def alembic_config(config_path: str = "alembic.ini") -> Config:
    """Create an Alembic config object for local command execution."""
    return Config(config_path)


def upgrade_to_head(config_path: str = "alembic.ini") -> None:
    """Apply warehouse migrations to the latest revision."""
    command.upgrade(alembic_config(config_path), "head")
