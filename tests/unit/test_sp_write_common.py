from unittest.mock import AsyncMock

import pytest

from amazon_ads_mcp.tools.sp.common import SPContextError
from amazon_ads_mcp.tools.sp.write_common import (
    SPWriteValidationError,
    build_mutation_response,
    build_result,
    extract_error_message,
    extract_mutation_items,
    normalize_adjustment_requests,
    normalize_keyword_create_requests,
    normalize_negative_keyword_requests,
    normalize_keyword_id_requests,
    sp_post,
)


def test_build_mutation_response_counts_outcomes():
    response = build_mutation_response(
        "profile-1",
        "na",
        [
            build_result("applied", "UPDATED", keyword_id="1"),
            build_result("skipped", "DUPLICATE", keyword_id="2"),
            build_result("failed", "ERROR", keyword_id="3"),
        ],
    )

    assert response["requested_count"] == 3
    assert response["applied_count"] == 1
    assert response["skipped_count"] == 1
    assert response["failed_count"] == 1


def test_extract_mutation_items_supports_results_fallback():
    assert extract_mutation_items({"results": [{"keywordId": 1}]}, "keywords") == [
        {"keywordId": 1}
    ]


def test_extract_error_message_prefers_nested_details():
    assert extract_error_message({"error": {"details": "Bid too low"}}) == "Bid too low"


def test_normalize_adjustment_requests_rejects_out_of_range_bid():
    with pytest.raises(SPWriteValidationError, match="new_bid must be between"):
        normalize_adjustment_requests([{"keyword_id": "kw-1", "new_bid": 0.01}])


def test_normalize_keyword_create_requests_rejects_duplicate_pairs():
    with pytest.raises(
        SPWriteValidationError, match="duplicate keyword_text/match_type"
    ):
        normalize_keyword_create_requests(
            [
                {"keyword_text": "Running Shoes", "match_type": "EXACT", "bid": 1.0},
                {"keyword_text": "running shoes", "match_type": "exact", "bid": 1.2},
            ]
        )


def test_normalize_negative_keyword_requests_rejects_duplicate_phrases():
    with pytest.raises(SPWriteValidationError, match="duplicate keyword phrases"):
        normalize_negative_keyword_requests(["Running Shoes", "running   shoes"])


def test_normalize_keyword_id_requests_rejects_duplicates():
    with pytest.raises(SPWriteValidationError, match="duplicate keyword_id"):
        normalize_keyword_id_requests(["kw-1", "kw-1"])


@pytest.mark.asyncio
async def test_sp_post_passes_explicit_media_headers():
    client = AsyncMock()

    await sp_post(client, "/sp/keywords", {"keywords": []}, "application/test")

    client.post.assert_awaited_once_with(
        "/sp/keywords",
        json={"keywords": []},
        headers={"Content-Type": "application/test", "Accept": "application/test"},
    )


def test_sp_context_error_is_available_for_write_tools():
    error = SPContextError("missing profile")
    assert str(error) == "missing profile"
