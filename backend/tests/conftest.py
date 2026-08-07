"""
Shared pytest fixtures for ContentFlow QA.
Provides 300 partner-content records across 4 partners.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime, timezone, timedelta
from scripts.generate_sample_data import generate_sample_assets


# ─── 300 PARTNER-CONTENT RECORDS ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def all_assets():
    """300 seeded partner-content records across 4 partners."""
    return generate_sample_assets(count=300, seed=42)

@pytest.fixture(scope="session")
def acme_assets(all_assets):
    return [a for a in all_assets if a.get("partner") == "acme_studios"]

@pytest.fixture(scope="session")
def globalmax_assets(all_assets):
    return [a for a in all_assets if a.get("partner") == "globalmax"]

@pytest.fixture(scope="session")
def indie_assets(all_assets):
    return [a for a in all_assets if a.get("partner") == "indie_films"]

@pytest.fixture(scope="session")
def legacy_assets(all_assets):
    return [a for a in all_assets if a.get("partner") == "legacy_media"]


# ─── SINGLE ASSET FIXTURES ────────────────────────────────────────────────────

@pytest.fixture
def valid_asset():
    return {
        "content_id": "TEST-001",
        "title": "The Great Adventure",
        "genre": "action",
        "rating": "PG-13",
        "duration_seconds": 5400,
        "language": "en",
        "synopsis": "An epic adventure across three continents.",
        "release_year": 2023,
        "cast": ["Actor A", "Actor B"],
        "director": "Director C",
        "keywords": ["adventure", "action"],
        "asset_url": "https://cdn.example.com/TEST-001.mp4",
        "avail_start": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        "avail_end":   (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
        "launch_date": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
        "rating_locked": True,
        "territories": ["US", "GB", "CA"],
        "partner_approved": True,
        "partner": "acme_studios",
        "feed_xml": """<?xml version="1.0" encoding="utf-8"?>
<Content xmlns="urn:contentflow:v1">
  <ContentID>TEST-001</ContentID>
  <Title>The Great Adventure</Title>
  <Genre>action</Genre>
  <Rating>PG-13</Rating>
  <Duration>5400</Duration>
</Content>""",
    }


# ─── STATUS CHANGE FIXTURES ───────────────────────────────────────────────────

@pytest.fixture
def asset_missing_title(valid_asset):
    a = valid_asset.copy(); del a["title"]; return a

@pytest.fixture
def asset_missing_genre(valid_asset):
    a = valid_asset.copy(); del a["genre"]; return a

@pytest.fixture
def asset_missing_rating(valid_asset):
    a = valid_asset.copy(); del a["rating"]; return a

@pytest.fixture
def asset_missing_multiple_fields(valid_asset):
    a = valid_asset.copy()
    del a["title"]; del a["genre"]; del a["synopsis"]; return a

@pytest.fixture
def asset_bad_rating(valid_asset):
    a = valid_asset.copy(); a["rating"] = "SUPER-SAFE"; return a

@pytest.fixture
def asset_expired_rights(valid_asset):
    a = valid_asset.copy()
    a["avail_end"] = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    return a

@pytest.fixture
def asset_future_avail(valid_asset):
    a = valid_asset.copy()
    a["avail_start"] = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    return a

@pytest.fixture
def asset_rating_unlocked(valid_asset):
    a = valid_asset.copy(); a["rating_locked"] = False; return a

@pytest.fixture
def asset_not_approved(valid_asset):
    a = valid_asset.copy(); a["partner_approved"] = False; return a

@pytest.fixture
def asset_malformed_xml(valid_asset):
    a = valid_asset.copy()
    a["feed_xml"] = "<Content><Broken></Content><Wrong>"; return a

@pytest.fixture
def asset_duration_too_short(valid_asset):
    a = valid_asset.copy(); a["duration_seconds"] = 30; return a

@pytest.fixture
def asset_duration_too_long(valid_asset):
    a = valid_asset.copy(); a["duration_seconds"] = 50000; return a

@pytest.fixture
def asset_blocked_territory(valid_asset):
    a = valid_asset.copy(); a["territories"] = ["US", "BLOCKED", "GB"]; return a

@pytest.fixture
def asset_expiring_soon(valid_asset):
    a = valid_asset.copy()
    a["avail_end"] = (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()
    return a

@pytest.fixture
def batch_with_duplicate_ids(valid_asset):
    """Two assets sharing the same content_id — duplicate within batch."""
    a1 = valid_asset.copy(); a1["content_id"] = "DUP-001"
    a2 = valid_asset.copy(); a2["content_id"] = "DUP-001"; a2["title"] = "Different Title"
    return [a1, a2]

@pytest.fixture
def batch_with_cross_partner_collision(valid_asset):
    """Asset ID that collides with a known platform-existing ID."""
    a = valid_asset.copy(); a["content_id"] = "CF-001"
    return [a]
