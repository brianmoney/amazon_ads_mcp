"""Warehouse worker orchestration and APScheduler wiring."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..config.settings import Settings
from .context import ensure_worker_region, warehouse_profile_context
from .db import warehouse_connection
from .durability import DurableReportCoordinator, WarehouseJobCoordinator
from .loaders import (
    load_ads_profiles,
    load_budget_history,
    load_campaigns_and_ad_groups,
    load_impression_share,
    load_keyword_performance,
    load_keywords,
    load_placement_report,
    load_portfolio_usage_snapshot,
    load_portfolios,
    load_search_terms,
)
from .repository import advance_watermark
from .types import JobScope, ReportRequest
from .utils import default_worker_id, report_window, utcnow
from .validation import (
    validate_budget_history,
    validate_impression_share,
    validate_keyword_performance,
    validate_placement_report,
    validate_portfolio_usage,
    validate_portfolios,
    validate_search_terms,
)
from .live_views import fetch_live_portfolios, fetch_live_profiles
from .live_views import (
    create_live_report,
    download_live_report_rows,
    lookup_live_report_status,
    poll_live_report,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduledSurface:
    """Surface metadata used to register worker schedules."""

    surface_name: str
    job_type: str
    schedule_minutes: int


REPORT_SURFACES = {
    "get_keyword_performance": {
        "report_type_id": "spTargeting",
        "group_by": ["targeting"],
        "columns": [
            "campaignId",
            "campaignName",
            "adGroupId",
            "adGroupName",
            "keywordId",
            "keyword",
            "matchType",
            "impressions",
            "clicks",
            "cost",
            "sales14d",
            "purchases14d",
        ],
        "filters": [{"field": "keywordType", "values": ["BROAD", "PHRASE", "EXACT"]}],
        "time_unit": "SUMMARY",
    },
    "get_search_term_report": {
        "report_type_id": "spSearchTerm",
        "group_by": ["searchTerm"],
        "columns": [
            "campaignId",
            "campaignName",
            "adGroupId",
            "adGroupName",
            "searchTerm",
            "keywordId",
            "keyword",
            "matchType",
            "impressions",
            "clicks",
            "cost",
            "sales14d",
            "purchases14d",
        ],
        "filters": [],
        "time_unit": "SUMMARY",
    },
    "get_campaign_budget_history": {
        "report_type_id": "budgetUsage",
        "group_by": ["campaign"],
        "columns": ["campaignId", "campaignName", "date", "cost", "dailyBudget", "hoursRan"],
        "filters": [],
        "time_unit": "DAILY",
    },
    "get_placement_report": {
        "report_type_id": "spCampaigns",
        "group_by": ["campaign", "campaignPlacement"],
        "columns": [
            "campaignId",
            "campaignName",
            "placementClassification",
            "impressions",
            "clicks",
            "cost",
            "sales14d",
            "purchases14d",
        ],
        "filters": [],
        "time_unit": "SUMMARY",
    },
    "get_impression_share_report": {
        "report_type_id": "spCampaigns",
        "group_by": ["campaign"],
        "columns": ["campaignId", "campaignName", "topOfSearchImpressionShare"],
        "filters": [],
        "time_unit": "SUMMARY",
    },
}


class WarehouseWorker:
    """Run scheduled ingestion cycles for the phase 1 warehouse surfaces."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.worker_id = default_worker_id(self.settings)
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    def _scheduled_surfaces(self) -> list[ScheduledSurface]:
        """Return the phase 1 worker schedules defined by the OpenSpec change."""
        return [
            ScheduledSurface("dimension_cycle", "dimension", self.settings.warehouse_dimension_refresh_minutes),
            ScheduledSurface("report_cycle", "report", self.settings.warehouse_report_refresh_minutes),
            ScheduledSurface(
                "portfolio_usage_cycle",
                "snapshot",
                self.settings.warehouse_portfolio_usage_refresh_minutes,
            ),
            ScheduledSurface(
                "validation_cycle",
                "validation",
                self.settings.warehouse_validation_refresh_minutes,
            ),
        ]

    def configure_schedule(self) -> None:
        """Wire APScheduler intervals for the documented phase 1 surfaces."""
        for surface in self._scheduled_surfaces():
            self.scheduler.add_job(
                self.run_cycle,
                "interval",
                minutes=max(surface.schedule_minutes, 1),
                id=surface.surface_name,
                replace_existing=True,
                kwargs={"cycle_name": surface.surface_name},
            )

    async def _run_with_heartbeat(
        self,
        job_coordinator,
        ingestion_job_id: str,
        operation,
    ):
        """Keep heartbeats fresh while a claimed job is executing."""
        interval_seconds = max(self.settings.warehouse_heartbeat_seconds, 1)
        stop_event = asyncio.Event()

        async def heartbeat_loop() -> None:
            while True:
                try:
                    await asyncio.wait_for(
                        stop_event.wait(), timeout=interval_seconds
                    )
                    return
                except asyncio.TimeoutError:
                    job_coordinator.heartbeat(ingestion_job_id)

        heartbeat_task = asyncio.create_task(heartbeat_loop())
        job_coordinator.heartbeat(ingestion_job_id)
        try:
            return await operation
        finally:
            stop_event.set()
            await heartbeat_task

    async def start(self) -> None:
        """Start the worker and scheduler, then keep the process alive."""
        if not self.settings.warehouse_worker_enabled:
            raise RuntimeError("Warehouse worker is disabled. Set WAREHOUSE_WORKER_ENABLED=true.")
        if self.settings.warehouse_scheduler_enabled:
            self.configure_schedule()
            self.scheduler.start()
            logger.info("Warehouse scheduler started for worker %s", self.worker_id)
        else:
            await self.run_cycle(cycle_name="manual")
            return
        while True:
            await asyncio.sleep(3600)

    async def run_cycle(self, *, cycle_name: str) -> None:
        """Run one ordered ingestion cycle across configured profiles and regions."""
        logger.info("Starting warehouse cycle %s", cycle_name)
        regions = self.settings.effective_warehouse_regions
        for region in regions:
            profiles = await self._resolve_profiles_for_region(region)
            if not profiles:
                logger.info(
                    "Warehouse cycle %s found no profiles for region %s; skipping.",
                    cycle_name,
                    region,
                )
                continue
            for profile_id in profiles:
                await self._run_profile_cycle(profile_id=profile_id, region=region)

    async def _resolve_profiles_for_region(self, region: str) -> list[str]:
        """Return configured profile ids or discover visible profiles for a region."""
        if self.settings.warehouse_profile_ids:
            return self.settings.warehouse_profile_ids
        await ensure_worker_region(region)
        return [
            str(profile.get("profileId", "")).strip()
            for profile in await fetch_live_profiles()
            if str(profile.get("profileId", "")).strip()
        ]

    async def _run_profile_cycle(self, *, profile_id: str, region: str) -> None:
        """Run the documented loader order for one profile and region."""
        await ensure_worker_region(region)
        with warehouse_profile_context(profile_id=profile_id, region=region):
            with warehouse_connection() as connection:
                job_coordinator = WarehouseJobCoordinator(
                    connection,
                    claim_timeout_seconds=self.settings.warehouse_claim_timeout_seconds,
                )
                await self._run_dimension_loads(connection, job_coordinator, profile_id, region)
                await self._run_report_loads(connection, job_coordinator, profile_id, region)
                await self._run_portfolio_usage_load(connection, job_coordinator, profile_id, region)
                if self.settings.warehouse_validation_enabled:
                    await self._run_validation(connection, job_coordinator, profile_id, region)

    async def _run_dimension_loads(self, connection, job_coordinator, profile_id: str, region: str) -> None:
        """Run the dimension portion of the documented loader order."""
        ads_scope = JobScope(profile_id=profile_id, region=region, surface_name="ads_profile", job_type="dimension")
        ads_job = job_coordinator.claim(ads_scope, worker_id=self.worker_id)
        if ads_job:
            try:
                await self._run_with_heartbeat(
                    job_coordinator,
                    ads_job.ingestion_job_id,
                    load_ads_profiles(
                        connection,
                        profile_id=profile_id,
                        region=region,
                    ),
                )
                job_coordinator.complete(ads_job.ingestion_job_id)
            except Exception as exc:
                job_coordinator.fail(ads_job.ingestion_job_id, error_text=str(exc))
                raise

        portfolio_scope = JobScope(profile_id=profile_id, region=region, surface_name="list_portfolios", job_type="dimension")
        portfolio_job = job_coordinator.claim(portfolio_scope, worker_id=self.worker_id)
        if portfolio_job:
            try:
                await self._run_with_heartbeat(
                    job_coordinator,
                    portfolio_job.ingestion_job_id,
                    load_portfolios(
                        connection,
                        profile_id=profile_id,
                        region=region,
                    ),
                )
                job_coordinator.complete(portfolio_job.ingestion_job_id)
            except Exception as exc:
                job_coordinator.fail(portfolio_job.ingestion_job_id, error_text=str(exc))
                raise

        campaign_scope = JobScope(profile_id=profile_id, region=region, surface_name="list_campaigns", job_type="dimension")
        campaign_job = job_coordinator.claim(campaign_scope, worker_id=self.worker_id)
        campaign_ids: list[str] = []
        if campaign_job:
            try:
                _, _, campaign_ids, _ = await self._run_with_heartbeat(
                    job_coordinator,
                    campaign_job.ingestion_job_id,
                    load_campaigns_and_ad_groups(
                        connection,
                        profile_id=profile_id,
                        region=region,
                    ),
                )
                job_coordinator.complete(campaign_job.ingestion_job_id)
            except Exception as exc:
                job_coordinator.fail(campaign_job.ingestion_job_id, error_text=str(exc))
                raise

        keyword_scope = JobScope(profile_id=profile_id, region=region, surface_name="sp_keyword", job_type="dimension")
        keyword_job = job_coordinator.claim(keyword_scope, worker_id=self.worker_id)
        if keyword_job:
            try:
                await self._run_with_heartbeat(
                    job_coordinator,
                    keyword_job.ingestion_job_id,
                    load_keywords(
                        connection,
                        profile_id=profile_id,
                        region=region,
                        campaign_ids=campaign_ids,
                    ),
                )
                job_coordinator.complete(keyword_job.ingestion_job_id)
            except Exception as exc:
                job_coordinator.fail(keyword_job.ingestion_job_id, error_text=str(exc))
                raise

    async def _execute_report_surface(
        self,
        connection,
        job_coordinator,
        *,
        profile_id: str,
        region: str,
        surface_name: str,
    ) -> None:
        """Create or resume a report-run and then persist the resulting facts."""
        window_start, window_end = report_window(self.settings)
        scope = JobScope(
            profile_id=profile_id,
            region=region,
            surface_name=surface_name,
            job_type="report",
            window_start=window_start,
            window_end=window_end,
        )
        job = job_coordinator.claim(scope, worker_id=self.worker_id)
        if job is None:
            return
        request_spec = REPORT_SURFACES[surface_name]
        request = ReportRequest(
            surface_name=surface_name,
            report_type_id=request_spec["report_type_id"],
            start_date=window_start.isoformat(),
            end_date=window_end.isoformat(),
            group_by=request_spec["group_by"],
            columns=request_spec["columns"],
            filters=request_spec["filters"],
            time_unit=request_spec["time_unit"],
        )
        durable_reports = DurableReportCoordinator(connection)
        try:
            from ..tools.sp.common import get_sp_client, require_sp_context

            auth_manager, _, _ = require_sp_context()
            client = await get_sp_client(auth_manager)

            async def run_report_load() -> None:
                report_run = durable_reports.create_or_resume(
                    ingestion_job_id=job.ingestion_job_id,
                    profile_id=profile_id,
                    region=region,
                    request=request,
                )
                report_id = report_run.amazon_report_id
                if not report_id:
                    report_id = await create_live_report(request, client=client)
                    report_run = durable_reports.store_amazon_report_id(
                        report_run.report_run_id,
                        report_id,
                    )
                status = await lookup_live_report_status(report_id, client=client)
                durable_reports.mark_polled(
                    report_run.report_run_id,
                    status=status["status"],
                    raw_status=status.get("raw_status"),
                    status_details=status.get("status_details"),
                    diagnostic=status,
                )

                if status["status"] != "COMPLETED":
                    status = await poll_live_report(
                        report_id,
                        client=client,
                        timeout_seconds=self.settings.warehouse_report_poll_timeout_seconds,
                    )
                    durable_reports.mark_polled(
                        report_run.report_run_id,
                        status=status["status"],
                        raw_status=status.get("raw_status"),
                        status_details=status.get("status_details"),
                        diagnostic=status,
                    )

                rows = await download_live_report_rows(
                    report_id,
                    client=client,
                    status=status,
                )
                durable_reports.mark_downloaded(
                    report_run.report_run_id,
                    row_count=len(rows),
                    diagnostic=status,
                )
                if surface_name == "get_keyword_performance":
                    await load_keyword_performance(
                        connection,
                        profile_id=profile_id,
                        region=region,
                        start_date=request.start_date,
                        end_date=request.end_date,
                        report_run_id=report_run.report_run_id,
                        amazon_report_id=report_id,
                    )
                elif surface_name == "get_search_term_report":
                    await load_search_terms(
                        connection,
                        profile_id=profile_id,
                        region=region,
                        start_date=request.start_date,
                        end_date=request.end_date,
                        report_run_id=report_run.report_run_id,
                        amazon_report_id=report_id,
                    )
                elif surface_name == "get_campaign_budget_history":
                    await load_budget_history(
                        connection,
                        profile_id=profile_id,
                        region=region,
                        start_date=request.start_date,
                        end_date=request.end_date,
                        report_run_id=report_run.report_run_id,
                        amazon_report_id=report_id,
                    )
                elif surface_name == "get_placement_report":
                    await load_placement_report(
                        connection,
                        profile_id=profile_id,
                        region=region,
                        start_date=request.start_date,
                        end_date=request.end_date,
                        report_run_id=report_run.report_run_id,
                        amazon_report_id=report_id,
                    )
                elif surface_name == "get_impression_share_report":
                    await load_impression_share(
                        connection,
                        profile_id=profile_id,
                        region=region,
                        start_date=request.start_date,
                        end_date=request.end_date,
                        report_run_id=report_run.report_run_id,
                        amazon_report_id=report_id,
                    )

            await self._run_with_heartbeat(
                job_coordinator,
                job.ingestion_job_id,
                run_report_load(),
            )
            job_coordinator.complete(job.ingestion_job_id)
        except Exception as exc:
            job_coordinator.fail(job.ingestion_job_id, error_text=str(exc))
            raise

    async def _run_report_loads(self, connection, job_coordinator, profile_id: str, region: str) -> None:
        """Run all report-based fact loads in the documented order."""
        for surface_name in [
            "get_keyword_performance",
            "get_search_term_report",
            "get_campaign_budget_history",
            "get_placement_report",
            "get_impression_share_report",
        ]:
            await self._execute_report_surface(
                connection,
                job_coordinator,
                profile_id=profile_id,
                region=region,
                surface_name=surface_name,
            )

    async def _run_portfolio_usage_load(self, connection, job_coordinator, profile_id: str, region: str) -> None:
        """Run portfolio usage snapshots after portfolio settings sync."""
        portfolios = await fetch_live_portfolios(limit=100)
        portfolio_ids = [row["portfolio_id"] for row in portfolios if row.get("portfolio_id")]
        scope = JobScope(
            profile_id=profile_id,
            region=region,
            surface_name="get_portfolio_budget_usage",
            job_type="snapshot",
            scope={"portfolio_ids": portfolio_ids},
        )
        job = job_coordinator.claim(scope, worker_id=self.worker_id)
        if job is None:
            return
        try:
            await self._run_with_heartbeat(
                job_coordinator,
                job.ingestion_job_id,
                load_portfolio_usage_snapshot(
                    connection,
                    profile_id=profile_id,
                    region=region,
                    portfolio_ids=portfolio_ids,
                ),
            )
            job_coordinator.complete(job.ingestion_job_id)
        except Exception as exc:
            job_coordinator.fail(job.ingestion_job_id, error_text=str(exc))
            raise

    async def _run_validation(self, connection, job_coordinator, profile_id: str, region: str) -> None:
        """Run focused warehouse-versus-live validation checks."""
        window_start, window_end = report_window(self.settings)
        scope = JobScope(
            profile_id=profile_id,
            region=region,
            surface_name="warehouse_validation",
            job_type="validation",
            window_start=window_start,
            window_end=window_end,
        )
        job = job_coordinator.claim(scope, worker_id=self.worker_id)
        if job is None:
            return
        try:
            async def run_validation() -> dict[str, object]:
                portfolios = await fetch_live_portfolios(limit=25)
                portfolio_ids = [
                    row["portfolio_id"]
                    for row in portfolios[:25]
                    if row.get("portfolio_id")
                ]
                results = [
                    await validate_keyword_performance(
                        connection,
                        profile_id=profile_id,
                        start_date=window_start.isoformat(),
                        end_date=window_end.isoformat(),
                    ),
                    await validate_search_terms(
                        connection,
                        profile_id=profile_id,
                        start_date=window_start.isoformat(),
                        end_date=window_end.isoformat(),
                    ),
                    await validate_budget_history(
                        connection,
                        profile_id=profile_id,
                        start_date=window_start.isoformat(),
                        end_date=window_end.isoformat(),
                    ),
                    await validate_placement_report(
                        connection,
                        profile_id=profile_id,
                        start_date=window_start.isoformat(),
                        end_date=window_end.isoformat(),
                    ),
                    await validate_impression_share(
                        connection,
                        profile_id=profile_id,
                        start_date=window_start.isoformat(),
                        end_date=window_end.isoformat(),
                    ),
                    await validate_portfolios(connection, profile_id=profile_id),
                    await validate_portfolio_usage(
                        connection,
                        profile_id=profile_id,
                        portfolio_ids=portfolio_ids,
                    ),
                ]
                matched = all(result.get("matched") for result in results)
                return {"results": results, "matched": matched}

            diagnostic = await self._run_with_heartbeat(
                job_coordinator,
                job.ingestion_job_id,
                run_validation(),
            )
            matched = bool(diagnostic["matched"])
            advance_watermark(
                connection,
                surface_name="warehouse_validation",
                profile_id=profile_id,
                region=region,
                last_snapshot_at=utcnow(),
                last_status="completed" if matched else "mismatch",
                notes=diagnostic,
            )
            if matched:
                job_coordinator.complete(job.ingestion_job_id, diagnostic=diagnostic)
            else:
                job_coordinator.fail(
                    job.ingestion_job_id,
                    error_text="Warehouse validation mismatches detected.",
                    diagnostic=diagnostic,
                )
        except Exception as exc:
            job_coordinator.fail(job.ingestion_job_id, error_text=str(exc))
            raise
