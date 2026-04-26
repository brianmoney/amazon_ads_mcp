"""CLI entrypoint for the warehouse worker."""

from __future__ import annotations

import argparse
import asyncio
import os

from ..utils.security import setup_secure_logging
from .migrations import upgrade_to_head
from .worker import WarehouseWorker


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Amazon Ads warehouse worker")
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run a single cycle without starting APScheduler.",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Skip Alembic upgrade on startup.",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    if not args.skip_migrations:
        upgrade_to_head()
    worker = WarehouseWorker()
    if args.run_once:
        await worker.run_cycle(cycle_name="manual")
        return
    await worker.start()


def main() -> None:
    """Run the warehouse worker process."""
    setup_secure_logging(level=os.environ.get("LOG_LEVEL", "INFO"))
    parser = _build_parser()
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
