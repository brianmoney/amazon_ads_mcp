"""Warehouse runtime for Postgres-backed Sponsored Products ingestion."""

from .worker import WarehouseWorker

__all__ = ["WarehouseWorker"]
