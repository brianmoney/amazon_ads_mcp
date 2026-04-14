"""Unit tests for media type handling."""

from amazon_ads_mcp.utils.media import MediaTypeRegistry


def test_registry_resolves_exact_entries():
    reg = MediaTypeRegistry()
    reg.add_entries(
        {("post", "/v2/items"): "application/json"},
        {
            ("get", "/v2/items"): ["application/json", "text/csv"],
            ("post", "/v2/items"): ["application/json"],
        },
    )

    content_type, accepts = reg.resolve("POST", "https://api/v2/items")

    assert content_type == "application/json"
    assert accepts == ["application/json"]


def test_registry_resolves_templated_paths():
    reg = MediaTypeRegistry()
    reg.add_entries(
        {("post", "/v2/items/{itemId}"): "application/vnd.custom+json"},
        {("get", "/v2/items/{itemId}"): ["application/json", "text/csv"]},
    )

    content_type, accepts = reg.resolve("GET", "https://api/v2/items/123")

    assert content_type is None
    assert accepts == ["application/json", "text/csv"]


def test_registry_returns_none_when_no_match():
    reg = MediaTypeRegistry()

    assert reg.resolve("GET", "https://api/v2/missing") == (None, None)
