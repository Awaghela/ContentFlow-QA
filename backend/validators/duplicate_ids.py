"""
Duplicate ID Validator
=======================
Scans all assets in a run for duplicate content_id values.
Also checks for IDs that collide with previously onboarded partner content
(simulated here; in production, query the PostgreSQL validation_results table).
"""

from typing import Any
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# Simulated IDs already in the platform from prior partner onboardings
_EXISTING_PLATFORM_IDS = {
    "CF-001", "CF-002", "CF-003", "CF-100", "CF-200",
    "MEDIA-999", "MEDIA-1000", "LEGACY-42",
}


class DuplicateIDValidator:
    """Detects duplicate content_id values within the batch and against the platform."""

    async def validate(self, assets: list[dict[str, Any]]) -> list[dict]:
        results = []
        seen: dict[str, list[int]] = defaultdict(list)

        # First pass: build ID → indices map
        for idx, asset in enumerate(assets):
            cid = str(asset.get("content_id", "")).strip()
            if cid:
                seen[cid].append(idx)

        # Second pass: emit results per asset
        for asset in assets:
            asset_id = str(asset.get("content_id", "unknown")).strip()

            # 1. Missing ID
            if not asset_id or asset_id == "unknown":
                results.append(self._result(
                    asset_id, "content_id_missing", "fail",
                    "Asset has no content_id — cannot check uniqueness",
                ))
                continue

            # 2. Within-batch duplicate
            if len(seen.get(asset_id, [])) > 1:
                count = len(seen[asset_id])
                results.append(self._result(
                    asset_id, "duplicate_within_batch", "fail",
                    f"content_id '{asset_id}' appears {count} times in this batch",
                    "Duplicate IDs within the same submission will cause import failures."
                ))
            else:
                results.append(self._result(
                    asset_id, "unique_within_batch", "pass",
                    f"content_id '{asset_id}' is unique within this batch"
                ))

            # 3. Cross-partner collision
            if asset_id in _EXISTING_PLATFORM_IDS:
                results.append(self._result(
                    asset_id, "cross_partner_collision", "fail",
                    f"content_id '{asset_id}' already exists from another partner",
                    "IDs must be globally unique across all onboarded partners."
                ))
            else:
                results.append(self._result(
                    asset_id, "no_cross_partner_collision", "pass",
                    f"content_id '{asset_id}' has no conflict with existing platform content"
                ))

            # 4. ID format check (basic pattern: letters, digits, hyphens/underscores)
            import re
            if not re.match(r'^[A-Za-z0-9_\-]{3,64}$', asset_id):
                results.append(self._result(
                    asset_id, "invalid_id_format", "warn",
                    f"content_id '{asset_id}' contains unexpected characters or length",
                    "IDs should be 3–64 alphanumeric characters, hyphens, or underscores."
                ))

        return results

    @staticmethod
    def _result(asset_id: str, scenario: str, status: str, message: str, detail: str = "") -> dict:
        return {
            "asset_id": asset_id,
            "scenario": scenario,
            "status": status,
            "message": message,
            "detail": detail,
        }
