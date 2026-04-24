"""Pydantic models for Sponsored Display tools."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SDCampaignListRequest(BaseModel):
    """Normalized request filters for Sponsored Display campaign discovery."""

    campaign_states: list[str] = Field(default_factory=list)
    campaign_ids: list[str] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    limit: int
    offset: int


class SDTargetingGroupContext(BaseModel):
    """Lightweight targeting-group context returned with SD campaigns."""

    targeting_group_id: str | None = None
    targeting_group_name: str | None = None
    state: str | None = None


class SDCampaign(BaseModel):
    """Normalized Sponsored Display campaign record."""

    campaign_id: str
    name: str | None = None
    state: str | None = None
    serving_status: str | None = None
    budget: float | None = None
    budget_type: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    objective: str | None = None
    bidding_model: str | None = None
    targeting_groups: list[SDTargetingGroupContext] = Field(default_factory=list)


class SDCampaignListResponse(BaseModel):
    """Response shape for ``list_sd_campaigns``."""

    profile_id: str
    region: str
    filters: SDCampaignListRequest
    campaigns: list[SDCampaign]
    returned_count: int


class SDPerformanceRequest(BaseModel):
    """Normalized request filters for Sponsored Display performance."""

    start_date: str
    end_date: str
    campaign_ids: list[str] = Field(default_factory=list)
    targeting_group_ids: list[str] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    limit: int
    resume_from_report_id: str | None = None
    timeout_seconds: float


class SDPerformanceRow(BaseModel):
    """Normalized targeting-group row for Sponsored Display reporting."""

    campaign_id: str
    campaign_name: str | None = None
    targeting_group_id: str | None = None
    targeting_group_name: str | None = None
    objective: str | None = None
    bidding_model: str | None = None
    impressions: float | None = None
    viewable_impressions: float | None = None
    clicks: float | None = None
    spend: float | None = None
    sales: float | None = None
    orders: float | None = None
    ctr: float | None = None
    cpc: float | None = None
    vcpm: float | None = None
    acos: float | None = None
    roas: float | None = None


class SDPerformanceResponse(BaseModel):
    """Response shape for ``get_sd_performance``."""

    profile_id: str
    region: str
    start_date: str
    end_date: str
    report_id: str
    filters: SDPerformanceRequest
    rows: list[SDPerformanceRow]
    returned_count: int


class SDReportStatusRequest(BaseModel):
    """Request shape for ``sd_report_status``."""

    report_id: str


class SDReportStatusResponse(BaseModel):
    """Response shape for ``sd_report_status``."""

    profile_id: str
    region: str
    report_id: str
    status: str
    raw_status: str | None = None
    status_details: str | None = None
    generated_at: str | None = None
    updated_at: str | None = None
    url_expires_at: str | None = None
    download_url: str | None = None
    resume_from_report_id: str | None = None
