import json

import httpx
import pytest

from amazon_ads_mcp.tools.sd.report_helper import SDReportError, create_sd_report


class FakeResponse:
    def __init__(self, *, status_code=200, json_data=None, content=b""):
        self.status_code = status_code
        self._json_data = json_data
        self.content = content
        self.request = httpx.Request("POST", "https://example.com/reporting/reports")

    def raise_for_status(self):
        if self.status_code >= 400:
            response = httpx.Response(
                self.status_code,
                request=self.request,
                json=self._json_data,
                content=None if self._json_data is not None else self.content,
            )
            raise httpx.HTTPStatusError(
                "request failed", request=self.request, response=response
            )

    def json(self):
        return self._json_data

    @property
    def text(self):
        if self._json_data is not None:
            return json.dumps(self._json_data)
        return self.content.decode("utf-8", "replace")


class FakeReportClient:
    def __init__(self, post_responses):
        self.post_responses = list(post_responses)
        self.calls = []

    async def post(self, path, json=None, headers=None):
        self.calls.append((path, json, headers))
        return self.post_responses.pop(0)


@pytest.mark.asyncio
async def test_create_sd_report_uses_documented_reporting_contract():
    client = FakeReportClient([FakeResponse(json_data={"reportId": "sd-rpt-1"})])

    result = await create_sd_report(
        report_type_id="sdAdGroup",
        start_date="2026-01-01",
        end_date="2026-01-31",
        group_by=["adGroup"],
        columns=["impressions", "clicks", "cost", "campaignId", "adGroupId"],
        filters=[{"field": "campaignObjective", "values": ["REACH"]}],
        client=client,
    )

    assert result == "sd-rpt-1"
    assert client.calls[0][0] == "/reporting/reports"
    assert client.calls[0][1] == {
        "name": client.calls[0][1]["name"],
        "startDate": "2026-01-01",
        "endDate": "2026-01-31",
        "configuration": {
            "adProduct": "SPONSORED_DISPLAY",
            "reportTypeId": "sdAdGroup",
            "groupBy": ["adGroup"],
            "columns": ["impressions", "clicks", "cost", "campaignId", "adGroupId"],
            "format": "GZIP_JSON",
            "timeUnit": "SUMMARY",
            "filters": [{"field": "campaignObjective", "values": ["REACH"]}],
        },
    }
    assert client.calls[0][2] == {
        "Content-Type": "application/vnd.createasyncreportrequest.v3+json",
        "Accept": "application/json",
    }


@pytest.mark.asyncio
async def test_create_sd_report_surfaces_status_and_detail_on_failure():
    client = FakeReportClient(
        [
            FakeResponse(
                status_code=400,
                json_data={
                    "code": "BAD_REQUEST",
                    "message": "reportTypeId is invalid for ad product",
                },
            )
        ]
    )

    with pytest.raises(
        SDReportError,
        match=r"Sponsored Display report creation failed\. \(status 400\): reportTypeId is invalid for ad product",
    ):
        await create_sd_report(
            report_type_id="sdTargeting",
            start_date="2026-01-01",
            end_date="2026-01-31",
            group_by=["targetingGroup"],
            columns=["targetingGroupId"],
            client=client,
        )
