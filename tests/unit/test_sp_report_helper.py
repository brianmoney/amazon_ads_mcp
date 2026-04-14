import gzip
import json

import httpx
import pytest

from amazon_ads_mcp.tools.sp.report_helper import SPReportError, run_sp_report


class FakeResponse:
    def __init__(self, *, status_code=200, json_data=None, content=b""):
        self.status_code = status_code
        self._json_data = json_data
        self.content = content
        self.request = httpx.Request("GET", "https://example.com")

    def raise_for_status(self):
        if self.status_code >= 400:
            response = httpx.Response(self.status_code, request=self.request)
            raise httpx.HTTPStatusError(
                "request failed", request=self.request, response=response
            )

    def json(self):
        return self._json_data


class FakeReportClient:
    def __init__(self, post_responses, get_responses):
        self.post_responses = list(post_responses)
        self.get_responses = list(get_responses)
        self.calls = []

    async def post(self, path, json=None):
        self.calls.append(("POST", path, json))
        return self.post_responses.pop(0)

    async def get(self, path):
        self.calls.append(("GET", path, None))
        return self.get_responses.pop(0)


def _gzip_payload(payload):
    return gzip.compress(json.dumps(payload).encode("utf-8"))


@pytest.mark.asyncio
async def test_run_sp_report_returns_parsed_rows():
    client = FakeReportClient(
        post_responses=[FakeResponse(json_data={"reportId": "rpt-1"})],
        get_responses=[
            FakeResponse(
                json_data={
                    "status": "COMPLETED",
                    "url": "https://download.example/report.gz",
                }
            ),
            FakeResponse(content=_gzip_payload([{"keywordId": 1, "clicks": 2}])),
        ],
    )

    result = await run_sp_report(
        report_type_id="spKeyword",
        start_date="2026-01-01",
        end_date="2026-01-31",
        group_by=["keyword"],
        columns=["keywordId"],
        client=client,
    )

    assert result == {"report_id": "rpt-1", "rows": [{"keywordId": 1, "clicks": 2}]}
    assert client.calls[0][0:2] == ("POST", "/reporting/reports")
    assert client.calls[1][0:2] == ("GET", "/reporting/reports/rpt-1")


@pytest.mark.asyncio
async def test_run_sp_report_times_out_while_polling():
    client = FakeReportClient(
        post_responses=[FakeResponse(json_data={"reportId": "rpt-2"})],
        get_responses=[FakeResponse(json_data={"status": "IN_PROGRESS"})],
    )

    with pytest.raises(SPReportError, match="timed out"):
        await run_sp_report(
            report_type_id="spKeyword",
            start_date="2026-01-01",
            end_date="2026-01-31",
            group_by=["keyword"],
            columns=["keywordId"],
            timeout_seconds=0,
            client=client,
        )


@pytest.mark.asyncio
async def test_run_sp_report_surfaces_download_failure():
    client = FakeReportClient(
        post_responses=[FakeResponse(json_data={"reportId": "rpt-3"})],
        get_responses=[
            FakeResponse(
                json_data={
                    "status": "COMPLETED",
                    "url": "https://download.example/report.gz",
                }
            ),
            FakeResponse(status_code=500),
        ],
    )

    with pytest.raises(SPReportError, match="download failed"):
        await run_sp_report(
            report_type_id="spKeyword",
            start_date="2026-01-01",
            end_date="2026-01-31",
            group_by=["keyword"],
            columns=["keywordId"],
            client=client,
        )


@pytest.mark.asyncio
async def test_run_sp_report_rejects_malformed_payloads():
    client = FakeReportClient(
        post_responses=[FakeResponse(json_data={"reportId": "rpt-4"})],
        get_responses=[
            FakeResponse(
                json_data={
                    "status": "COMPLETED",
                    "url": "https://download.example/report.gz",
                }
            ),
            FakeResponse(content=b"not-a-gzip"),
        ],
    )

    with pytest.raises(SPReportError, match="could not be decompressed"):
        await run_sp_report(
            report_type_id="spKeyword",
            start_date="2026-01-01",
            end_date="2026-01-31",
            group_by=["keyword"],
            columns=["keywordId"],
            client=client,
        )
