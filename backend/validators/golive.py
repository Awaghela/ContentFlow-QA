"""
Go-Live Readiness Validator
============================
The final gate before content can be made available to viewers.
Checks rights availability windows, launch dates, content ratings lock,
territory restrictions, and partner approval flags.
"""

from typing import Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class GoLiveValidator:
    """Validates that assets are cleared and ready for live platform delivery."""

    async def validate(self, assets: list[dict[str, Any]]) -> list[dict]:
        results = []
        now = datetime.now(timezone.utc)
        for asset in assets:
            results.extend(self._check_asset(asset, now))
        return results

    def _check_asset(self, asset: dict, now: datetime) -> list[dict]:
        issues = []
        asset_id = asset.get("content_id", "unknown")

        # 1. Rights window — avail_start / avail_end
        avail_start = self._parse_dt(asset.get("avail_start"))
        avail_end = self._parse_dt(asset.get("avail_end"))

        if avail_start is None:
            issues.append(self._result(
                asset_id, "avail_start_missing", "fail",
                "No avail_start date — cannot confirm rights window is open",
                "A rights availability start date is required for go-live."
            ))
        elif avail_start > now:
            issues.append(self._result(
                asset_id, "avail_start_future", "warn",
                f"Rights window does not open until {avail_start.date()} (future)",
                "Content will not be deliverable until avail_start."
            ))
        else:
            issues.append(self._result(
                asset_id, "avail_start_ok", "pass",
                f"Rights window is open (started {avail_start.date()})"
            ))

        if avail_end is None:
            issues.append(self._result(
                asset_id, "avail_end_missing", "warn",
                "No avail_end date — perpetual rights assumed",
                "Define an expiry to avoid serving content after rights lapse."
            ))
        elif avail_end < now:
            issues.append(self._result(
                asset_id, "avail_expired", "fail",
                f"Rights window expired on {avail_end.date()} — content cannot go live",
                "Renew rights or remove the asset from the submission."
            ))
        else:
            days_remaining = (avail_end - now).days
            status = "warn" if days_remaining < 30 else "pass"
            issues.append(self._result(
                asset_id, "avail_end_ok", status,
                f"Rights window expires in {days_remaining} days ({avail_end.date()})",
                "Expiry within 30 days — flag for rights renewal." if status == "warn" else ""
            ))

        # 2. Launch date
        launch_dt = self._parse_dt(asset.get("launch_date"))
        if launch_dt is None:
            issues.append(self._result(
                asset_id, "launch_date_missing", "warn",
                "No launch_date set — defaulting to immediate availability"
            ))
        elif launch_dt > now:
            issues.append(self._result(
                asset_id, "launch_date_future", "warn",
                f"Launch date is {launch_dt.date()} — content is scheduled, not live",
            ))
        else:
            issues.append(self._result(
                asset_id, "launch_date_passed", "pass",
                f"Launch date {launch_dt.date()} has passed — content is cleared for delivery"
            ))

        # 3. Ratings lock
        rating_locked = asset.get("rating_locked", False)
        if not rating_locked:
            issues.append(self._result(
                asset_id, "rating_not_locked", "fail",
                "Content rating is not locked — classification may still change",
                "Ratings must be locked by a certified classifier before going live."
            ))
        else:
            issues.append(self._result(
                asset_id, "rating_locked_ok", "pass",
                "Content rating is locked and finalised"
            ))

        # 4. Territory clearance
        territories = asset.get("territories", [])
        if not territories:
            issues.append(self._result(
                asset_id, "no_territories_defined", "warn",
                "No territory restrictions defined — worldwide assumed",
                "Confirm territorial rights before worldwide release."
            ))
        elif "BLOCKED" in [t.upper() for t in territories]:
            issues.append(self._result(
                asset_id, "territory_blocked", "fail",
                "One or more territories are explicitly blocked for this content",
                "Remove blocked territory codes or resolve rights disputes."
            ))

        # 5. Partner approval flag
        approved = asset.get("partner_approved", True)
        if not approved:
            issues.append(self._result(
                asset_id, "partner_not_approved", "fail",
                "Partner has not marked this asset as approved for delivery",
                "All assets must be approved via the partner portal before submission."
            ))

        return issues

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        try:
            return datetime.fromisoformat(str(value)).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _result(asset_id: str, scenario: str, status: str, message: str, detail: str = "") -> dict:
        return {
            "asset_id": asset_id,
            "scenario": scenario,
            "status": status,
            "message": message,
            "detail": detail,
        }
