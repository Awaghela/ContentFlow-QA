"""Tests for MetadataValidator."""

import pytest
from backend.validators.metadata import MetadataValidator


@pytest.mark.asyncio
async def test_valid_asset_passes(valid_asset):
    v = MetadataValidator()
    results = await v.validate([valid_asset])
    failures = [r for r in results if r["status"] == "fail"]
    assert failures == [], f"Expected no failures but got: {failures}"


@pytest.mark.asyncio
async def test_missing_title_fails(asset_missing_title):
    v = MetadataValidator()
    results = await v.validate([asset_missing_title])
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "required_field_missing" in scenarios


@pytest.mark.asyncio
async def test_invalid_rating_fails(asset_bad_rating):
    v = MetadataValidator()
    results = await v.validate([asset_bad_rating])
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "invalid_rating" in scenarios


@pytest.mark.asyncio
async def test_duration_too_short():
    v = MetadataValidator()
    asset = {"content_id": "SHORT-001", "title": "T", "genre": "drama",
             "rating": "G", "duration_seconds": 30, "language": "en"}
    results = await v.validate([asset])
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "duration_too_short" in scenarios


@pytest.mark.asyncio
async def test_bulk_validation_counts():
    v = MetadataValidator()
    assets = [
        {"content_id": f"BULK-{i:03d}", "title": f"Title {i}", "genre": "comedy",
         "rating": "G", "duration_seconds": 3600, "language": "en"}
        for i in range(20)
    ]
    results = await v.validate(assets)
    assert len(results) > 0
    passes = [r for r in results if r["status"] == "pass"]
    assert len(passes) > 0
