from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select

from amazon_ads_mcp.warehouse.repository import (
    advance_watermark,
    claim_job,
    create_or_refresh_job,
    create_or_resume_report_run,
    update_report_run,
)
from amazon_ads_mcp.warehouse.schema import (
    ads_profile,
    freshness_watermark,
    ingestion_job,
    metadata,
)
from amazon_ads_mcp.warehouse.types import JobScope


@pytest.fixture
def connection():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    metadata.create_all(engine)
    with engine.begin() as conn:
        yield conn


@pytest.mark.unit
def test_claim_job_uses_deterministic_key_and_reclaims_completed_job(connection):
    scope = JobScope(
        profile_id="profile-1",
        region="na",
        surface_name="get_keyword_performance",
        job_type="report",
    )

    first = claim_job(connection, scope, worker_id="worker-a")
    assert first is not None
    assert first.status == "running"

    connection.execute(
        ingestion_job.update()
        .where(ingestion_job.c.ingestion_job_id == first.ingestion_job_id)
        .values(status="completed", completed_at=datetime.now(UTC))
    )

    second = claim_job(connection, scope, worker_id="worker-b")
    assert second is not None
    assert second.ingestion_job_id == first.ingestion_job_id
    assert second.worker_id == "worker-b"
    assert second.attempt_count == 2


@pytest.mark.unit
def test_report_run_resume_returns_existing_active_scope(connection):
    scope = JobScope(
        profile_id="profile-1",
        region="na",
        surface_name="get_keyword_performance",
        job_type="report",
    )
    job = create_or_refresh_job(connection, scope)

    first = create_or_resume_report_run(
        connection,
        ingestion_job_id=job.ingestion_job_id,
        profile_id="profile-1",
        surface_name="get_keyword_performance",
        report_type_id="spTargeting",
        request_scope_hash="scope-hash",
        window_start="2026-04-20",
        window_end="2026-04-20",
    )
    second = create_or_resume_report_run(
        connection,
        ingestion_job_id=job.ingestion_job_id,
        profile_id="profile-1",
        surface_name="get_keyword_performance",
        report_type_id="spTargeting",
        request_scope_hash="scope-hash",
        window_start="2026-04-20",
        window_end="2026-04-20",
    )

    assert second.report_run_id == first.report_run_id


@pytest.mark.unit
def test_report_run_can_create_new_attempt_after_release(connection):
    scope = JobScope(
        profile_id="profile-1",
        region="na",
        surface_name="get_keyword_performance",
        job_type="report",
    )
    job = create_or_refresh_job(connection, scope)

    first = create_or_resume_report_run(
        connection,
        ingestion_job_id=job.ingestion_job_id,
        profile_id="profile-1",
        surface_name="get_keyword_performance",
        report_type_id="spTargeting",
        request_scope_hash="scope-hash",
        window_start="2026-04-20",
        window_end="2026-04-20",
    )
    update_report_run(
        connection,
        first.report_run_id,
        status="completed",
        release_active_scope=True,
        mark_completed=True,
        mark_retrieved=True,
    )

    second = create_or_resume_report_run(
        connection,
        ingestion_job_id=job.ingestion_job_id,
        profile_id="profile-1",
        surface_name="get_keyword_performance",
        report_type_id="spTargeting",
        request_scope_hash="scope-hash",
        window_start="2026-04-20",
        window_end="2026-04-20",
    )

    assert second.report_run_id != first.report_run_id


@pytest.mark.unit
def test_advance_watermark_upserts_latest_status(connection):
    connection.execute(
        ads_profile.insert().values(
            profile_id="profile-1",
            region="na",
            first_seen_at=datetime.now(UTC),
            last_refreshed_at=datetime.now(UTC),
        )
    )

    advance_watermark(
        connection,
        surface_name="get_keyword_performance",
        profile_id="profile-1",
        region="na",
        last_successful_window_end="2026-04-20",
        last_status="completed",
        notes={"rows": 10},
    )
    advance_watermark(
        connection,
        surface_name="get_keyword_performance",
        profile_id="profile-1",
        region="na",
        last_successful_window_end="2026-04-21",
        last_status="mismatch",
        notes={"rows": 11},
    )

    row = connection.execute(select(freshness_watermark)).one()._mapping

    assert row["last_successful_window_end"].isoformat() == "2026-04-21"
    assert row["last_status"] == "mismatch"
    assert row["notes_json"] == {"rows": 11}
