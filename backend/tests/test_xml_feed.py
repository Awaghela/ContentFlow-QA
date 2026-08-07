"""Tests for XMLFeedValidator."""

import pytest
from backend.validators.xml_feed import XMLFeedValidator


@pytest.mark.asyncio
async def test_valid_xml_passes(valid_asset):
    v = XMLFeedValidator()
    results = await v.validate([valid_asset])
    failures = [r for r in results if r["status"] == "fail"]
    assert failures == []


@pytest.mark.asyncio
async def test_malformed_xml_fails(asset_malformed_xml):
    v = XMLFeedValidator()
    results = await v.validate([asset_malformed_xml])
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "xml_parse_error" in scenarios


@pytest.mark.asyncio
async def test_no_feed_warns():
    v = XMLFeedValidator()
    asset = {"content_id": "NOFEED-001"}
    results = await v.validate([asset])
    scenarios = [r["scenario"] for r in results if r["status"] == "warn"]
    assert "feed_missing" in scenarios


@pytest.mark.asyncio
async def test_valid_json_feed_passes():
    v = XMLFeedValidator()
    import json
    asset = {
        "content_id": "JSON-001",
        "feed_json": json.dumps({
            "content_id": "JSON-001", "title": "Test", "genre": "drama", "rating": "PG"
        })
    }
    results = await v.validate([asset])
    passes = [r for r in results if r["status"] == "pass"]
    assert len(passes) > 0


@pytest.mark.asyncio
async def test_malformed_json_fails():
    v = XMLFeedValidator()
    asset = {"content_id": "BADJSON-001", "feed_json": "{invalid json here"}
    results = await v.validate([asset])
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "json_parse_error" in scenarios
