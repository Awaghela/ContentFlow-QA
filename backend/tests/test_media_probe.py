"""Tests for MediaProbeValidator (using simulated FFprobe)."""

import pytest
from backend.validators.media_probe import MediaProbeValidator


@pytest.mark.asyncio
async def test_valid_asset_passes(valid_asset):
    v = MediaProbeValidator()
    results = await v.validate([valid_asset])
    # At least a probe_success result should be present
    statuses = [r["status"] for r in results]
    # Should not be all failures
    assert "pass" in statuses or "warn" in statuses


@pytest.mark.asyncio
async def test_no_url_skipped():
    v = MediaProbeValidator()
    asset = {"content_id": "NOURL-001"}
    results = await v.validate([asset])
    scenarios = [r["scenario"] for r in results]
    assert "probe_no_url" in scenarios


@pytest.mark.asyncio
async def test_probe_data_invalid_codec():
    v = MediaProbeValidator()
    probe = {
        "streams": [
            {"codec_type": "video", "codec_name": "wmv3", "width": 640, "height": 480,
             "bit_rate": "1000000", "duration": "3600"},
        ],
        "format": {"format_name": "asf", "duration": "3600", "bit_rate": "1000000"}
    }
    issues = v._check_probe_data("TEST-BAD-CODEC", probe)
    scenarios = [r["scenario"] for r in issues if r["status"] == "fail"]
    assert "invalid_video_codec" in scenarios
    assert "invalid_container" in scenarios


@pytest.mark.asyncio
async def test_probe_data_low_bitrate():
    v = MediaProbeValidator()
    probe = {
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1280, "height": 720,
             "bit_rate": "100000", "duration": "3600"},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
        "format": {"format_name": "mp4", "duration": "3600", "bit_rate": "100000"}
    }
    issues = v._check_probe_data("TEST-LOW-BR", probe)
    scenarios = [r["scenario"] for r in issues if r["status"] == "fail"]
    assert "bitrate_too_low" in scenarios
