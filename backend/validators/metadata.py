"""
Metadata Validator
==================
Checks that each content asset has all required and recommended metadata fields,
validates field formats (e.g. rating values, year ranges, language codes), and
flags assets with missing or malformed data.
"""

from typing import Any
import re
import logging

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ["content_id", "title", "genre", "rating", "duration_seconds", "language"]
RECOMMENDED_FIELDS = ["synopsis", "release_year", "cast", "director", "keywords"]

VALID_RATINGS = {"G", "PG", "PG-13", "R", "NC-17", "TV-Y", "TV-G", "TV-PG", "TV-14", "TV-MA", "NR"}
VALID_LANGUAGES = {"en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh", "ar", "hi"}
VALID_GENRES = {
    "action", "adventure", "animation", "comedy", "crime", "documentary",
    "drama", "fantasy", "horror", "mystery", "romance", "sci-fi",
    "thriller", "western", "sports", "reality", "news", "kids"
}


class MetadataValidator:
    """Validates content asset metadata completeness and format."""

    async def validate(self, assets: list[dict[str, Any]]) -> list[dict]:
        results = []
        for asset in assets:
            results.extend(self._check_asset(asset))
        return results

    def _check_asset(self, asset: dict) -> list[dict]:
        issues = []
        asset_id = asset.get("content_id", asset.get("id", "unknown"))

        # 1. Required fields presence
        for field in REQUIRED_FIELDS:
            if not asset.get(field):
                issues.append(self._result(
                    asset_id, "required_field_missing", "fail",
                    f"Required field '{field}' is missing or empty",
                    f"Asset must have a non-empty '{field}' value."
                ))
            else:
                issues.append(self._result(
                    asset_id, f"required_field_{field}", "pass",
                    f"Required field '{field}' present"
                ))

        # 2. Recommended fields
        missing_recommended = [f for f in RECOMMENDED_FIELDS if not asset.get(f)]
        if missing_recommended:
            issues.append(self._result(
                asset_id, "recommended_fields_missing", "warn",
                f"Recommended fields missing: {', '.join(missing_recommended)}",
                "These fields improve discoverability and are expected by most platforms."
            ))

        # 3. Rating validation
        rating = asset.get("rating", "")
        if rating and rating.upper() not in VALID_RATINGS:
            issues.append(self._result(
                asset_id, "invalid_rating", "fail",
                f"Rating '{rating}' is not a recognised value",
                f"Valid ratings: {', '.join(sorted(VALID_RATINGS))}"
            ))

        # 4. Language code
        lang = asset.get("language", "")
        if lang and lang.lower() not in VALID_LANGUAGES:
            issues.append(self._result(
                asset_id, "invalid_language_code", "warn",
                f"Language code '{lang}' is not in the known list",
                "Use ISO 639-1 two-letter codes (en, es, fr, ...)."
            ))

        # 5. Genre check
        genre = str(asset.get("genre", "")).lower()
        if genre and genre not in VALID_GENRES:
            issues.append(self._result(
                asset_id, "unrecognised_genre", "warn",
                f"Genre '{genre}' is not in the standard taxonomy",
            ))

        # 6. Duration sanity (1 min – 4 hours)
        duration = asset.get("duration_seconds", 0)
        try:
            dur = int(duration)
            if dur < 60:
                issues.append(self._result(
                    asset_id, "duration_too_short", "fail",
                    f"Duration {dur}s is under 60 seconds",
                    "Content shorter than 1 minute is likely a mismatch."
                ))
            elif dur > 14400:
                issues.append(self._result(
                    asset_id, "duration_too_long", "fail",
                    f"Duration {dur}s exceeds 4 hours",
                    "Durations over 14400s are flagged for manual review."
                ))
        except (TypeError, ValueError):
            issues.append(self._result(
                asset_id, "invalid_duration_format", "fail",
                f"Duration value '{duration}' is not a valid integer",
            ))

        # 7. Release year
        year = asset.get("release_year")
        if year:
            try:
                y = int(year)
                if not (1888 <= y <= 2030):
                    issues.append(self._result(
                        asset_id, "invalid_release_year", "warn",
                        f"Release year {y} is outside expected range 1888–2030",
                    ))
            except (TypeError, ValueError):
                issues.append(self._result(
                    asset_id, "invalid_release_year_format", "warn",
                    f"Release year '{year}' is not a valid integer",
                ))

        return issues

    @staticmethod
    def _result(asset_id: str, scenario: str, status: str, message: str, detail: str = "") -> dict:
        return {
            "asset_id": asset_id,
            "scenario": scenario,
            "status": status,
            "message": message,
            "detail": detail,
        }
