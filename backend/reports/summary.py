"""
Summary Reporter
================
Generates structured issue reports from a completed validation run.
Groups failures by category, ranks by severity, and produces
an ops-review-friendly summary with recommended actions.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


CATEGORY_LABELS = {
    "metadata":     "Metadata Validation",
    "xml_feed":     "XML / Feed Parsing",
    "asset_check":  "Asset Availability",
    "media_probe":  "FFmpeg Media Probe",
    "duplicate_ids":"Duplicate ID Scan",
    "golive":       "Go-Live Readiness",
}

RECOMMENDED_ACTIONS = {
    "required_field_missing":   "Partner must supply missing metadata fields before resubmission.",
    "xml_parse_error":          "Partner engineering team must fix XML malformation.",
    "asset_unreachable":        "CDN/origin team to verify file hosting and DNS.",
    "probe_failed":             "Re-encode or re-upload the affected video file.",
    "duplicate_within_batch":   "Partner must deduplicate IDs before resubmission.",
    "cross_partner_collision":  "Assign new globally unique IDs for colliding assets.",
    "avail_expired":            "Rights team to renew or remove expired content.",
    "rating_not_locked":        "Classification team to finalise and lock content rating.",
}


class SummaryReporter:
    """Produces an ops-review report from a completed validation run."""

    def generate(self, run: dict[str, Any]) -> dict:
        results = run.get("results", [])
        summary = run.get("summary", {})

        by_category: dict[str, dict] = {}
        issue_details: list[dict] = []
        assets_with_failures: set[str] = set()

        for r in results:
            cat = r.get("category", "unknown")
            status = r.get("status", "pass")
            label = CATEGORY_LABELS.get(cat, cat)

            if cat not in by_category:
                by_category[cat] = {"label": label, "pass": 0, "fail": 0, "warn": 0}

            by_category[cat][status] = by_category[cat].get(status, 0) + 1

            if status in ("fail", "warn"):
                asset_id = r.get("asset_id", "")
                if status == "fail":
                    assets_with_failures.add(asset_id)
                action = RECOMMENDED_ACTIONS.get(r.get("scenario", ""), "Review and remediate with the partner.")
                issue_details.append({
                    "severity": status,
                    "category": label,
                    "asset_id": asset_id,
                    "scenario": r.get("scenario"),
                    "message": r.get("message"),
                    "recommended_action": action,
                })

        # Sort: fails first, then warns
        issue_details.sort(key=lambda x: (0 if x["severity"] == "fail" else 1, x["category"]))

        return {
            "run_id": run.get("run_id"),
            "partner": run.get("partner"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                **summary,
                "blocked_assets": len(assets_with_failures),
                "categories_checked": len(by_category),
            },
            "by_category": list(by_category.values()),
            "issues": issue_details[:200],  # cap at 200 for readability
            "recommendation": self._overall_recommendation(summary),
        }

    @staticmethod
    def _overall_recommendation(summary: dict) -> str:
        pass_rate = summary.get("pass_rate", 0)
        fail = summary.get("fail", 0)
        if fail == 0:
            return "✅ All assets passed. Content is cleared for go-live pending final review."
        if pass_rate >= 95:
            return f"⚠️ {fail} asset(s) failed. Minor remediation required before go-live."
        if pass_rate >= 80:
            return f"🚧 Pass rate {pass_rate}% — significant issues must be resolved. Escalate to partner."
        return f"🔴 Pass rate {pass_rate}% — critical failures across multiple categories. Do not go live."
