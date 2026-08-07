"""
Asset Availability Validator
=============================
Probes each asset URL to verify it is reachable, checks HTTP status codes,
validates CDN response headers, and follows redirect chains.
Uses async HTTP for high-throughput concurrent probing.
"""

from typing import Any
import asyncio
import logging
import random

logger = logging.getLogger(__name__)

# Simulated CDN domains that should serve assets
KNOWN_CDN_DOMAINS = {
    "cdn.partner.com", "assets.streaming.io",
    "media.contentflow.com", "cdn.example.com",
}

MAX_REDIRECTS = 5
TIMEOUT_SECONDS = 10


class AssetAvailabilityValidator:
    """Checks that every asset URL is reachable and returns a valid response."""

    async def validate(self, assets: list[dict[str, Any]]) -> list[dict]:
        tasks = [self._check_asset(asset) for asset in assets]
        results_nested = await asyncio.gather(*tasks)
        return [r for sublist in results_nested for r in sublist]

    async def _check_asset(self, asset: dict) -> list[dict]:
        issues = []
        asset_id = asset.get("content_id", "unknown")
        url = asset.get("asset_url", "")

        if not url:
            return [self._result(
                asset_id, "asset_url_missing", "fail",
                "No asset URL provided for this content item",
                "Every asset must have a resolvable asset_url."
            )]

        # Simulate async HTTP probe (in production use httpx.AsyncClient)
        await asyncio.sleep(0)  # yield to event loop
        probe = self._simulate_probe(url)

        # URL format check
        if not url.startswith(("http://", "https://")):
            issues.append(self._result(
                asset_id, "invalid_url_scheme", "fail",
                f"URL does not start with http:// or https://: {url}",
            ))
            return issues

        # HTTPS enforcement
        if url.startswith("http://"):
            issues.append(self._result(
                asset_id, "insecure_url", "warn",
                f"Asset URL uses HTTP instead of HTTPS: {url}",
                "All production asset URLs should use HTTPS."
            ))

        # Reachability
        if probe["status_code"] == 0:
            issues.append(self._result(
                asset_id, "asset_unreachable", "fail",
                f"Asset URL is not reachable (connection error): {url}",
                "Check CDN origin configuration and DNS resolution."
            ))
            return issues

        if probe["status_code"] >= 400:
            issues.append(self._result(
                asset_id, "asset_http_error", "fail",
                f"Asset URL returned HTTP {probe['status_code']}: {url}",
                "A 4xx/5xx response means the file is unavailable."
            ))
            return issues

        issues.append(self._result(
            asset_id, "asset_reachable", "pass",
            f"Asset URL is reachable (HTTP {probe['status_code']})"
        ))

        # Redirect chain
        if probe["redirect_count"] > MAX_REDIRECTS:
            issues.append(self._result(
                asset_id, "excessive_redirects", "warn",
                f"Asset URL followed {probe['redirect_count']} redirects (max {MAX_REDIRECTS})",
            ))

        # Content-Type
        ct = probe.get("content_type", "")
        if ct and not any(t in ct for t in ["video/", "application/octet-stream", "binary"]):
            issues.append(self._result(
                asset_id, "unexpected_content_type", "warn",
                f"Unexpected Content-Type '{ct}' — expected a video MIME type",
            ))

        # CDN header
        if not probe.get("cdn_hit"):
            issues.append(self._result(
                asset_id, "not_served_from_cdn", "warn",
                "Asset does not appear to be served from a known CDN",
                "Production assets should be served via CDN for performance."
            ))
        else:
            issues.append(self._result(
                asset_id, "cdn_hit_confirmed", "pass",
                "Asset is served from CDN with cache hit"
            ))

        return issues

    def _simulate_probe(self, url: str) -> dict:
        """Simulate an HTTP probe result. Replace with real httpx call in production."""
        import hashlib
        # Use md5 for a stable seed unaffected by PYTHONHASHSEED randomisation
        seed = int(hashlib.md5(url.encode()).hexdigest(), 16) % 100
        if seed < 6:
            return {"status_code": 404, "redirect_count": 0, "content_type": "", "cdn_hit": False}
        if seed < 8:
            return {"status_code": 0, "redirect_count": 0, "content_type": "", "cdn_hit": False}
        return {
            "status_code": 200,
            "redirect_count": 1 if seed % 7 == 0 else 0,
            "content_type": "video/mp4",
            "cdn_hit": seed % 5 != 0,
        }

    @staticmethod
    def _result(asset_id: str, scenario: str, status: str, message: str, detail: str = "") -> dict:
        return {
            "asset_id": asset_id,
            "scenario": scenario,
            "status": status,
            "message": message,
            "detail": detail,
        }
