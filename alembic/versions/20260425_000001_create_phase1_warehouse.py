"""create phase 1 warehouse schema"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260425_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ads_profile",
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("region", sa.String(length=8), nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("account_type", sa.String(length=64), nullable=True),
        sa.Column("account_name", sa.String(length=255), nullable=True),
        sa.Column("currency_code", sa.String(length=16), nullable=True),
        sa.Column("timezone", sa.String(length=128), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("profile_id", name="pk_ads_profile"),
    )
    op.create_table(
        "portfolio",
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("portfolio_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=64), nullable=True),
        sa.Column("budget_scope", sa.String(length=32), nullable=True),
        sa.Column("daily_budget", sa.Numeric(18, 6), nullable=True),
        sa.Column("monthly_budget", sa.Numeric(18, 6), nullable=True),
        sa.Column("currency_code", sa.String(length=16), nullable=True),
        sa.Column("budget_policy", sa.String(length=64), nullable=True),
        sa.Column("in_budget", sa.Boolean(), nullable=True),
        sa.Column("serving_status", sa.String(length=64), nullable=True),
        sa.Column(
            "campaign_unspent_budget_sharing_state",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "status_reasons_json",
            postgresql.JSON(astext_type=sa.Text()),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column("budget_start_date", sa.Date(), nullable=True),
        sa.Column("budget_end_date", sa.Date(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["ads_profile.profile_id"], name="fk_portfolio_profile_id_ads_profile"),
        sa.PrimaryKeyConstraint("profile_id", "portfolio_id", name="pk_portfolio"),
    )
    op.create_table(
        "sp_campaign",
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("portfolio_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=64), nullable=True),
        sa.Column("serving_status", sa.String(length=64), nullable=True),
        sa.Column("budget", sa.Numeric(18, 6), nullable=True),
        sa.Column("budget_type", sa.String(length=64), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["ads_profile.profile_id"], name="fk_sp_campaign_profile_id_ads_profile"),
        sa.PrimaryKeyConstraint("profile_id", "campaign_id", name="pk_sp_campaign"),
    )
    op.create_index("ix_sp_campaign_profile_portfolio", "sp_campaign", ["profile_id", "portfolio_id"], unique=False)
    op.create_table(
        "sp_ad_group",
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("ad_group_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=64), nullable=True),
        sa.Column("default_bid", sa.Numeric(18, 6), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["ads_profile.profile_id"], name="fk_sp_ad_group_profile_id_ads_profile"),
        sa.PrimaryKeyConstraint("profile_id", "ad_group_id", name="pk_sp_ad_group"),
    )
    op.create_table(
        "sp_keyword",
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("keyword_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("ad_group_id", sa.String(length=64), nullable=False),
        sa.Column("keyword_text", sa.Text(), nullable=True),
        sa.Column("match_type", sa.String(length=32), nullable=True),
        sa.Column("current_bid", sa.Numeric(18, 6), nullable=True),
        sa.Column("bid_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["ads_profile.profile_id"], name="fk_sp_keyword_profile_id_ads_profile"),
        sa.PrimaryKeyConstraint("profile_id", "keyword_id", name="pk_sp_keyword"),
    )
    op.create_table(
        "sp_keyword_performance_fact",
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("keyword_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("ad_group_id", sa.String(length=64), nullable=False),
        sa.Column("keyword_text", sa.Text(), nullable=True),
        sa.Column("match_type", sa.String(length=32), nullable=True),
        sa.Column("current_bid", sa.Numeric(18, 6), nullable=True),
        sa.Column("impressions", sa.Float(), nullable=True),
        sa.Column("clicks", sa.Float(), nullable=True),
        sa.Column("spend", sa.Numeric(18, 6), nullable=True),
        sa.Column("sales_14d", sa.Numeric(18, 6), nullable=True),
        sa.Column("orders_14d", sa.Float(), nullable=True),
        sa.Column("last_report_run_id", sa.String(length=36), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["ads_profile.profile_id"], name="fk_sp_keyword_performance_fact_profile_id_ads_profile"),
        sa.PrimaryKeyConstraint(
            "profile_id",
            "window_start",
            "window_end",
            "keyword_id",
            name="pk_sp_keyword_performance_fact",
        ),
    )
    op.create_table(
        "sp_search_term_fact",
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("ad_group_id", sa.String(length=64), nullable=False),
        sa.Column("normalized_search_term", sa.Text(), nullable=False),
        sa.Column("keyword_id", sa.String(length=64), nullable=True),
        sa.Column("search_term", sa.Text(), nullable=True),
        sa.Column("match_type", sa.String(length=32), nullable=True),
        sa.Column("impressions", sa.Float(), nullable=True),
        sa.Column("clicks", sa.Float(), nullable=True),
        sa.Column("spend", sa.Numeric(18, 6), nullable=True),
        sa.Column("sales_14d", sa.Numeric(18, 6), nullable=True),
        sa.Column("orders_14d", sa.Float(), nullable=True),
        sa.Column("manually_targeted", sa.Boolean(), nullable=True),
        sa.Column("negated", sa.Boolean(), nullable=True),
        sa.Column(
            "targeting_context_json",
            postgresql.JSON(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("last_report_run_id", sa.String(length=36), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["ads_profile.profile_id"], name="fk_sp_search_term_fact_profile_id_ads_profile"),
        sa.PrimaryKeyConstraint(
            "profile_id",
            "window_start",
            "window_end",
            "campaign_id",
            "ad_group_id",
            "normalized_search_term",
            name="pk_sp_search_term_fact",
        ),
    )
    op.create_table(
        "sp_campaign_budget_history_fact",
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("budget_date", sa.Date(), nullable=False),
        sa.Column("campaign_name", sa.String(length=255), nullable=True),
        sa.Column("daily_budget", sa.Numeric(18, 6), nullable=True),
        sa.Column("spend", sa.Numeric(18, 6), nullable=True),
        sa.Column("utilization_pct", sa.Float(), nullable=True),
        sa.Column("hours_ran", sa.Float(), nullable=True),
        sa.Column("last_report_run_id", sa.String(length=36), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["ads_profile.profile_id"], name="fk_sp_campaign_budget_history_fact_profile_id_ads_profile"),
        sa.PrimaryKeyConstraint("profile_id", "campaign_id", "budget_date", name="pk_sp_campaign_budget_history_fact"),
    )
    op.create_table(
        "sp_placement_fact",
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("placement_type", sa.String(length=64), nullable=False),
        sa.Column("campaign_name", sa.String(length=255), nullable=True),
        sa.Column("impressions", sa.Float(), nullable=True),
        sa.Column("clicks", sa.Float(), nullable=True),
        sa.Column("spend", sa.Numeric(18, 6), nullable=True),
        sa.Column("sales_14d", sa.Numeric(18, 6), nullable=True),
        sa.Column("purchases_14d", sa.Float(), nullable=True),
        sa.Column("current_top_of_search_multiplier", sa.Float(), nullable=True),
        sa.Column("current_product_pages_multiplier", sa.Float(), nullable=True),
        sa.Column("context_retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_report_run_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["ads_profile.profile_id"], name="fk_sp_placement_fact_profile_id_ads_profile"),
        sa.PrimaryKeyConstraint(
            "profile_id",
            "window_start",
            "window_end",
            "campaign_id",
            "placement_type",
            name="pk_sp_placement_fact",
        ),
    )
    op.create_table(
        "sp_impression_share_fact",
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_name", sa.String(length=255), nullable=True),
        sa.Column("top_of_search_impression_share", sa.Float(), nullable=True),
        sa.Column("availability_state", sa.String(length=32), nullable=True),
        sa.Column("availability_reason", sa.Text(), nullable=True),
        sa.Column(
            "diagnostic_json",
            postgresql.JSON(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("last_report_run_id", sa.String(length=36), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["ads_profile.profile_id"], name="fk_sp_impression_share_fact_profile_id_ads_profile"),
        sa.PrimaryKeyConstraint(
            "profile_id",
            "window_start",
            "window_end",
            "campaign_id",
            name="pk_sp_impression_share_fact",
        ),
    )
    op.create_table(
        "portfolio_budget_usage_snapshot",
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("portfolio_id", sa.String(length=64), nullable=False),
        sa.Column("snapshot_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cap_amount", sa.Numeric(18, 6), nullable=True),
        sa.Column("current_spend", sa.Numeric(18, 6), nullable=True),
        sa.Column("remaining_budget", sa.Numeric(18, 6), nullable=True),
        sa.Column("utilization_pct", sa.Float(), nullable=True),
        sa.Column("usage_updated_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("availability_state", sa.String(length=32), nullable=True),
        sa.Column("availability_reason", sa.Text(), nullable=True),
        sa.Column(
            "diagnostic_json",
            postgresql.JSON(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["ads_profile.profile_id"], name="fk_portfolio_budget_usage_snapshot_profile_id_ads_profile"),
        sa.PrimaryKeyConstraint(
            "profile_id",
            "portfolio_id",
            "snapshot_timestamp",
            name="pk_portfolio_budget_usage_snapshot",
        ),
    )
    op.create_table(
        "ingestion_job",
        sa.Column("ingestion_job_id", sa.String(length=36), nullable=False),
        sa.Column("job_key", sa.String(length=128), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("surface_name", sa.String(length=128), nullable=False),
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("region", sa.String(length=8), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=True),
        sa.Column("window_end", sa.Date(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column(
            "scope_json",
            postgresql.JSON(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("last_error_text", sa.Text(), nullable=True),
        sa.Column(
            "diagnostic_json",
            postgresql.JSON(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_ingestion_job_attempt_count_non_negative"),
        sa.ForeignKeyConstraint(["profile_id"], ["ads_profile.profile_id"], name="fk_ingestion_job_profile_id_ads_profile"),
        sa.PrimaryKeyConstraint("ingestion_job_id", name="pk_ingestion_job"),
        sa.UniqueConstraint("job_key", name="uq_ingestion_job_job_key"),
    )
    op.create_index(
        "ix_ingestion_job_profile_surface_status",
        "ingestion_job",
        ["profile_id", "surface_name", "status"],
        unique=False,
    )
    op.create_table(
        "report_run",
        sa.Column("report_run_id", sa.String(length=36), nullable=False),
        sa.Column("ingestion_job_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=True),
        sa.Column("window_end", sa.Date(), nullable=True),
        sa.Column("amazon_report_id", sa.String(length=64), nullable=True),
        sa.Column("surface_name", sa.String(length=128), nullable=False),
        sa.Column("report_type_id", sa.String(length=128), nullable=False),
        sa.Column("request_scope_hash", sa.String(length=64), nullable=False),
        sa.Column("active_scope_key", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("raw_status", sa.String(length=64), nullable=True),
        sa.Column("status_details", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column(
            "diagnostic_json",
            postgresql.JSON(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ingestion_job_id"], ["ingestion_job.ingestion_job_id"], name="fk_report_run_ingestion_job_id_ingestion_job"),
        sa.ForeignKeyConstraint(["profile_id"], ["ads_profile.profile_id"], name="fk_report_run_profile_id_ads_profile"),
        sa.PrimaryKeyConstraint("report_run_id", name="pk_report_run"),
        sa.UniqueConstraint("active_scope_key", name="uq_report_run_active_scope_key"),
    )
    op.create_index(
        "ix_report_run_scope_status",
        "report_run",
        ["profile_id", "report_type_id", "request_scope_hash", "status"],
        unique=False,
    )
    op.create_table(
        "freshness_watermark",
        sa.Column("surface_name", sa.String(length=128), nullable=False),
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("region", sa.String(length=8), nullable=False),
        sa.Column("last_successful_window_end", sa.Date(), nullable=True),
        sa.Column("last_snapshot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=32), nullable=True),
        sa.Column(
            "notes_json",
            postgresql.JSON(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["ads_profile.profile_id"], name="fk_freshness_watermark_profile_id_ads_profile"),
        sa.PrimaryKeyConstraint("surface_name", "profile_id", "region", name="pk_freshness_watermark"),
    )


def downgrade() -> None:
    op.drop_table("freshness_watermark")
    op.drop_index("ix_report_run_scope_status", table_name="report_run")
    op.drop_table("report_run")
    op.drop_index("ix_ingestion_job_profile_surface_status", table_name="ingestion_job")
    op.drop_table("ingestion_job")
    op.drop_table("portfolio_budget_usage_snapshot")
    op.drop_table("sp_impression_share_fact")
    op.drop_table("sp_placement_fact")
    op.drop_table("sp_campaign_budget_history_fact")
    op.drop_table("sp_search_term_fact")
    op.drop_table("sp_keyword_performance_fact")
    op.drop_table("sp_keyword")
    op.drop_table("sp_ad_group")
    op.drop_index("ix_sp_campaign_profile_portfolio", table_name="sp_campaign")
    op.drop_table("sp_campaign")
    op.drop_table("portfolio")
    op.drop_table("ads_profile")
