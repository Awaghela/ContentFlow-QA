"""
Generate Sample Data
====================
Produces a realistic set of content asset records for testing the
ContentFlow QA pipeline. Injects known bad data at realistic rates
to exercise all validation scenarios.
"""

import random
import json
from datetime import datetime, timezone, timedelta
from typing import Optional


GENRES = ["action", "drama", "comedy", "thriller", "documentary", "sci-fi", "romance", "horror", "animation", "kids"]
RATINGS = ["G", "PG", "PG-13", "R", "TV-MA", "TV-14", "TV-G", "TV-PG"]
BAD_RATINGS = ["SUPER-SAFE", "ADULT", "M18", "XXX"]
LANGUAGES = ["en", "es", "fr", "de", "it", "pt", "ja", "ko"]
CODECS = ["h264", "hevc", "av1"]
BAD_CODECS = ["wmv3", "mpeg4", "xvid"]
PARTNERS = ["acme_studios", "globalmax", "indie_films", "legacy_media"]

# IDs that will collide with existing platform content
COLLISION_IDS = {"CF-001", "CF-100", "MEDIA-999"}


def _rand_xml(content_id: str, title: str, genre: str, rating: str, duration: int, malformed: bool = False) -> str:
    if malformed:
        return f"<Content><Broken>{content_id}</Wrong></Content><Unclosed>"
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Content xmlns="urn:contentflow:v1">
  <ContentID>{content_id}</ContentID>
  <Title>{title}</Title>
  <Genre>{genre}</Genre>
  <Rating>{rating}</Rating>
  <Duration>{duration}</Duration>
</Content>"""


def generate_sample_assets(count: int = 500, seed: int = 42) -> list[dict]:
    """
    Generate `count` sample asset records.
    Approximately:
      - 89% fully valid (pass all checks)
      - 6% with critical failures
      - 5% with warnings only
    """
    random.seed(seed)
    assets = []
    now = datetime.now(timezone.utc)

    for i in range(count):
        cid = f"CF-{i+1:04d}"
        genre = random.choice(GENRES)
        duration = random.randint(1800, 10800)  # 30 min – 3 hr
        title = f"{genre.title()} Story #{i+1}"

        # Inject faults at realistic rates
        fault_roll = random.random()

        # Missing metadata (~2%)
        missing_title = fault_roll < 0.02

        # Bad rating (~2%)
        bad_rating = 0.02 <= fault_roll < 0.04
        rating = random.choice(BAD_RATINGS) if bad_rating else random.choice(RATINGS)

        # Malformed XML (~1.5%)
        malformed_xml = 0.04 <= fault_roll < 0.055

        # Duplicate ID (~0.8%) — reuse an early ID
        if 0.055 <= fault_roll < 0.063 and i > 10:
            cid = assets[random.randint(0, min(10, i-1))]["content_id"]

        # Cross-partner collision (~0.5%)
        if 0.063 <= fault_roll < 0.068:
            cid = random.choice(list(COLLISION_IDS))

        # Expired rights (~2%)
        rights_expired = 0.068 <= fault_roll < 0.088
        avail_end = (
            (now - timedelta(days=random.randint(1, 90))).isoformat()
            if rights_expired
            else (now + timedelta(days=random.randint(30, 730))).isoformat()
        )

        # Rating not locked (~1%)
        rating_locked = fault_roll >= 0.088 or fault_roll < 0.078

        # Short duration (~0.5%)
        if 0.095 <= fault_roll < 0.10:
            duration = random.randint(5, 55)

        asset = {
            "content_id": cid,
            "title": "" if missing_title else title,
            "genre": genre,
            "rating": rating,
            "duration_seconds": duration,
            "language": random.choice(LANGUAGES),
            "synopsis": f"A compelling {genre} story." if fault_roll > 0.05 else None,
            "release_year": random.randint(1995, 2025),
            "cast": [f"Actor {random.randint(1, 200)}" for _ in range(random.randint(1, 4))],
            "director": f"Director {random.randint(1, 50)}",
            "keywords": [genre, "streaming", "featured"],
            "asset_url": f"https://cdn.example.com/{cid.lower()}.mp4",
            "avail_start": (now - timedelta(days=random.randint(1, 180))).isoformat(),
            "avail_end": avail_end,
            "launch_date": (now - timedelta(days=random.randint(0, 30))).isoformat(),
            "rating_locked": bool(rating_locked),
            "territories": random.sample(["US", "GB", "CA", "AU", "DE", "FR"], k=random.randint(2, 5)),
            "partner_approved": True,
            "partner": random.choice(PARTNERS),
            "feed_xml": _rand_xml(cid, title, genre, rating, duration, malformed=malformed_xml),
        }
        assets.append(asset)

    return assets


if __name__ == "__main__":
    import sys
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    assets = generate_sample_assets(count)
    print(json.dumps(assets[:3], indent=2))
    print(f"\n✅  Generated {len(assets)} sample assets")
    fails = sum(1 for a in assets if not a["title"] or a["rating"] in BAD_RATINGS)
    print(f"   ~{fails} assets with known metadata issues")
