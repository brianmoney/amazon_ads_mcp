import gzip
import json

import httpx
import pytest

from amazon_ads_mcp.tools.sd.report_helper import (
    SDReportError,
    create_sd_report,
    download_sd_report_rows,
    resume_sd_report,
    run_sd_report,
    wait_for_sd_report,
)


class FakeResponse:
    def __init__(self, *, status_code=200, json_data=None, content=b""):
        self.status_code = status_code
        self._json_data = json_data
        self.content = content
        self.request = httpx.Request("GET", "https://example.com")

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
    def __init__(self, post_responses, get_responses):
        self.post_responses = list(post_responses)
        self.get_responses = list(get_responses)
        self.calls = []

    async def post(self, path, json=None, headers=None):
        self.calls.append(("POST", path, json, headers))
        return self.post_responses.pop(0)

    async def get(self, path):
        self.calls.append(("GET", path, None))
        return self.get_responses.pop(0)


def _gzip_payload(payload):
    return gzip.compress(json.dumps(payload).encode("utf-8"))


@pytest.mark.asyncio
async def test_run_sd_report_returns_parsed_rows():
    client = FakeReportClient(
        post_responses=[FakeResponse(json_data={"reportId": "sd-rpt-1"})],
        get_responses=[
            FakeResponse(
                json_data={
                    "status": "COMPLETED",
                    "url": "https://download.example/report.gz",
                }
            ),
            FakeResponse(content=_gzip_payload([{"targetingGroupId": 1, "clicks": 2}])),
        ],
    )

    result = await run_sd_report(
        report_type_id="sdTargeting",
        start_date="2026-01-01",
        end_date="2026-01-31",
        group_by=["targetingGroup"],
        columns=["targetingGroupId"],
        timeout_seconds=5,
        client=client,
    )

    assert result == {
        "report_id": "sd-rpt-1",
        "rows": [{"targetingGroupId": 1, "clicks": 2}],
    }
    assert client.calls[0][0:2] == ("POST", "/reporting/reports")
    assert client.calls[0][2]["configuration"]["adProduct"] == "SPONSORED_DISPLAY"


@pytest.mark.asyncio
async def test_wait_for_sd_report_times_out_with_status_diagnostics():
    client = FakeReportClient(
        post_responses=[],
        get_responses=[
            FakeResponse(json_data={"status": "IN_PROGRESS"}),
            FakeResponse(json_data={"status": "IN_PROGRESS"}),
        ],
    )
    now = {"value": 0.0}

    async def fake_sleep(delay):
        now["value"] += delay

    def fake_monotonic():
        return now["value"]

    with pytest.raises(
        SDReportError,
        match=r"timed out while polling after 1\.0s \(last status: PROCESSING\)",
    ):
        await wait_for_sd_report(
            "sd-rpt-2",
            timeout_seconds=1,
            client=client,
            sleep_func=fake_sleep,
            monotonic_func=fake_monotonic,
            jitter_func=lambda low, high: 0.0,
        )


@pytest.mark.asyncio
async def test_resume_sd_report_rejects_non_ready_status():
    client = FakeReportClient(
        post_responses=[],
        get_responses=[FakeResponse(json_data={"status": "PROCESSING"})],
    )

    with pytest.raises(SDReportError, match=r"is not ready \(status: PROCESSING\)"):
        await resume_sd_report("sd-rpt-3", client=client)


@pytest.mark.asyncio
async def test_create_sd_report_reuses_duplicate_report_id():
    client = FakeReportClient(
        post_responses=[
            FakeResponse(
                status_code=425,
                content=b'{"code":"425","detail":"The Request is a duplicate of : a15115d8-3da4-49a4-95d5-cc0a3af5f85d"}',
            )
        ],
        get_responses=[],
    )

    result = await create_sd_report(
        report_type_id="sdTargeting",
        start_date="2026-01-01",
        end_date="2026-01-31",
        group_by=["targetingGroup"],
        columns=["targetingGroupId"],
        client=client,
    )

    assert result == "a15115d8-3da4-49a4-95d5-cc0a3af5f85d"


@pytest.mark.asyncio
async def test_download_sd_report_rows_surfaces_download_failure():
    client = FakeReportClient(
        post_responses=[],
        get_responses=[
            FakeResponse(
                json_data={
                    "status": "COMPLETED",
                    "url": "https://download.example/report.gz",
                }
            ),
            FakeResponse(status_code=503, json_data={"message": "temporary outage"}),
        ],
    )

    with pytest.raises(
        SDReportError,
        match=r"Sponsored Display report sd-rpt-4 download failed\. \(status 503\): temporary outage",
    ):
        await download_sd_report_rows("sd-rpt-4", client=client)


@pytest.mark.asyncio
async def test_run_sd_report_rejects_malformed_payloads():
    client = FakeReportClient(
        post_responses=[FakeResponse(json_data={"reportId": "sd-rpt-5"})],
        get_responses=[
            FakeResponse(
                json_data={
                    "status": "COMPLETED",
                    "url": "https://download.example/report.gz",
                }
            ),
            FakeResponse(content=b"not-gzip"),
        ],
    )

    with pytest.raises(
        SDReportError,
        match=r"Sponsored Display report payload could not be decompressed",
    ):
        await run_sd_report(
            report_type_id="sdTargeting",
            start_date="2026-01-01",
            end_date="2026-01-31",
            group_by=["targetingGroup"],
            columns=["targetingGroupId"],
            timeout_seconds=5,
            client=client,
        )
