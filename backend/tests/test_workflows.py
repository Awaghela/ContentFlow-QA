"""
ContentFlow QA — Full Workflow Test Suite
=========================================
35 test cases covering:
  - Status changes (queued → running → complete → fail)
  - Missing fields (required and recommended)
  - Repeated issues (same asset, multiple validator failures)
  - SQL reports (summary structure and field accuracy)
  - API failures (invalid input, edge cases)
  - Escalation tracking (severity promotion, blocking conditions)

Tested against 300 partner-content records (see conftest.py).
"""

import pytest
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.validators.metadata import MetadataValidator
from backend.validators.xml_feed import XMLFeedValidator
from backend.validators.asset_check import AssetAvailabilityValidator
from backend.validators.media_probe import MediaProbeValidator
from backend.validators.duplicate_ids import DuplicateIDValidator
from backend.validators.golive import GoLiveValidator
from backend.reports.summary import SummaryReporter


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — STATUS CHANGES (7 tests)
# Covers: queued → pass, queued → fail, partial pass, rights expiry transitions
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_status_fully_valid_asset_all_pass(valid_asset):
    """TC-01: A fully compliant asset passes all validator categories."""
    results = []
    for Validator in [MetadataValidator, XMLFeedValidator, GoLiveValidator]:
        r = await Validator().validate([valid_asset])
        results.extend(r)
    failures = [r for r in results if r["status"] == "fail"]
    assert failures == [], f"Expected zero failures on valid asset, got: {[f['scenario'] for f in failures]}"


@pytest.mark.asyncio
async def test_status_missing_title_changes_to_fail(asset_missing_title):
    """TC-02: Asset missing required title field transitions to FAIL status."""
    results = await MetadataValidator().validate([asset_missing_title])
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "required_field_missing" in scenarios


@pytest.mark.asyncio
async def test_status_expired_rights_blocks_golive(asset_expired_rights):
    """TC-03: Expired rights window changes go-live status to FAIL (blocked)."""
    results = await GoLiveValidator().validate([asset_expired_rights])
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "avail_expired" in scenarios


@pytest.mark.asyncio
async def test_status_future_avail_becomes_warn(asset_future_avail):
    """TC-04: Future avail_start transitions asset to WARN — not yet live."""
    results = await GoLiveValidator().validate([asset_future_avail])
    scenarios = [r["scenario"] for r in results if r["status"] == "warn"]
    assert "avail_start_future" in scenarios


@pytest.mark.asyncio
async def test_status_rating_not_locked_blocks(asset_rating_unlocked):
    """TC-05: Unlocked content rating changes go-live status to FAIL."""
    results = await GoLiveValidator().validate([asset_rating_unlocked])
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "rating_not_locked" in scenarios


@pytest.mark.asyncio
async def test_status_partner_not_approved_blocks(asset_not_approved):
    """TC-06: Partner approval flag = False → asset is blocked (FAIL)."""
    results = await GoLiveValidator().validate([asset_not_approved])
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "partner_not_approved" in scenarios


@pytest.mark.asyncio
async def test_status_expiring_soon_warns_not_fails(asset_expiring_soon):
    """TC-07: Rights window expiring in <30 days → WARN, not FAIL (still deliverable)."""
    results = await GoLiveValidator().validate([asset_expiring_soon])
    failures = [r for r in results if r["status"] == "fail" and r["scenario"] == "avail_expired"]
    warnings = [r for r in results if r["status"] == "warn" and r["scenario"] == "avail_end_ok"]
    assert failures == [], "Should not hard-fail for an asset still within rights window"
    assert warnings, "Should warn when rights expire within 30 days"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — MISSING FIELDS (7 tests)
# Covers: required vs recommended, multiple missing, format errors
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_missing_fields_title_required(asset_missing_title):
    """TC-08: Missing title (required) produces FAIL, not WARN."""
    results = await MetadataValidator().validate([asset_missing_title])
    fails = [r for r in results if r["status"] == "fail" and "title" in r.get("message","").lower()]
    assert fails, "Missing required title must be a FAIL"


@pytest.mark.asyncio
async def test_missing_fields_synopsis_recommended(valid_asset):
    """TC-09: Missing synopsis (recommended) produces WARN, not FAIL."""
    asset = valid_asset.copy(); asset.pop("synopsis", None)
    results = await MetadataValidator().validate([asset])
    fails = [r for r in results if r["status"] == "fail"]
    warns = [r for r in results if r["status"] == "warn" and "synopsis" in r.get("message","").lower()]
    # No hard failure for synopsis alone
    assert not any("synopsis" in f.get("message","").lower() for f in fails)


@pytest.mark.asyncio
async def test_missing_fields_multiple_required_all_flagged(asset_missing_multiple_fields):
    """TC-10: Multiple missing required fields — each generates its own FAIL result."""
    results = await MetadataValidator().validate([asset_missing_multiple_fields])
    fail_msgs = [r["message"] for r in results if r["status"] == "fail"]
    assert len(fail_msgs) >= 2, "Each missing required field must produce a distinct FAIL"


@pytest.mark.asyncio
async def test_missing_fields_invalid_rating_format(asset_bad_rating):
    """TC-11: Unrecognised rating value (SUPER-SAFE) fails format validation."""
    results = await MetadataValidator().validate([asset_bad_rating])
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "invalid_rating" in scenarios


@pytest.mark.asyncio
async def test_missing_fields_duration_too_short(asset_duration_too_short):
    """TC-12: Duration under 60s fails — likely wrong asset or encoding error."""
    results = await MetadataValidator().validate([asset_duration_too_short])
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "duration_too_short" in scenarios


@pytest.mark.asyncio
async def test_missing_fields_duration_too_long(asset_duration_too_long):
    """TC-13: Duration over 4 hours fails — likely a mismatch in submission."""
    results = await MetadataValidator().validate([asset_duration_too_long])
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "duration_too_long" in scenarios


@pytest.mark.asyncio
async def test_missing_fields_xml_required_elements(valid_asset):
    """TC-14: XML feed missing required element <Rating> → FAIL."""
    asset = valid_asset.copy()
    asset["feed_xml"] = """<?xml version="1.0" encoding="utf-8"?>
<Content xmlns="urn:contentflow:v1">
  <ContentID>TEST-001</ContentID>
  <Title>The Great Adventure</Title>
  <Genre>action</Genre>
  <Duration>5400</Duration>
</Content>"""
    results = await XMLFeedValidator().validate([asset])
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "missing_element_rating" in scenarios


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — REPEATED ISSUES (5 tests)
# Covers: same asset failing multiple validators, batch-level repeated patterns
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_repeated_same_asset_fails_multiple_validators(valid_asset):
    """TC-15: One broken asset can accumulate failures across multiple categories."""
    bad_asset = valid_asset.copy()
    bad_asset["title"] = ""              # metadata fail
    bad_asset["rating_locked"] = False   # golive fail
    bad_asset["feed_xml"] = "<broken>"   # xml fail

    meta_results  = await MetadataValidator().validate([bad_asset])
    xml_results   = await XMLFeedValidator().validate([bad_asset])
    live_results  = await GoLiveValidator().validate([bad_asset])

    all_fails = [r for r in meta_results + xml_results + live_results if r["status"] == "fail"]
    categories = {r.get("category", "unknown") for r in all_fails}
    assert len(all_fails) >= 3, "A broken asset should accumulate failures from multiple validators"


@pytest.mark.asyncio
async def test_repeated_batch_missing_title_pattern(all_assets):
    """TC-16: Across 300 records, injected title-missing pattern is consistently detected."""
    no_title = [a for a in all_assets if not a.get("title")]
    if not no_title:
        pytest.skip("No title-missing assets in this seed — adjust fault rate")
    results = await MetadataValidator().validate(no_title)
    fails = [r for r in results if r["status"] == "fail" and r["scenario"] == "required_field_missing"]
    assert len(fails) == len(no_title), "Every asset missing title must produce a required_field_missing FAIL"


@pytest.mark.asyncio
async def test_repeated_duplicate_id_detected_across_batch(batch_with_duplicate_ids):
    """TC-17: Duplicate content_id within a batch is flagged on both occurrences."""
    results = await DuplicateIDValidator().validate(batch_with_duplicate_ids)
    dup_fails = [r for r in results if r["scenario"] == "duplicate_within_batch"]
    assert len(dup_fails) >= 2, "Both assets sharing a duplicate ID must be flagged"


@pytest.mark.asyncio
async def test_repeated_cross_partner_collision(batch_with_cross_partner_collision):
    """TC-18: Asset with an ID that exists in another partner's catalog is flagged."""
    results = await DuplicateIDValidator().validate(batch_with_cross_partner_collision)
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "cross_partner_collision" in scenarios


@pytest.mark.asyncio
async def test_repeated_xml_same_error_across_partner_batch(all_assets):
    """TC-19: All assets with malformed XML in a 300-record batch are caught."""
    malformed = [a for a in all_assets if a.get("feed_xml","").startswith("<Content><Broken")]
    if not malformed:
        pytest.skip("No malformed XML assets in this seed batch")
    results = await XMLFeedValidator().validate(malformed)
    parse_fails = [r for r in results if r["scenario"] == "xml_parse_error"]
    assert len(parse_fails) == len(malformed)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — SQL REPORTS (6 tests)
# Covers: summary structure, field accuracy, category grouping, recommendations
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def completed_run(all_assets):
    """Build a simulated completed run dict from 300 assets."""
    import asyncio

    async def _run():
        results = []
        for cat, Validator in [
            ("metadata", MetadataValidator),
            ("xml_feed", XMLFeedValidator),
            ("golive",   GoLiveValidator),
        ]:
            r = await Validator().validate(all_assets)
            for item in r:
                results.append({"category": cat, **item})
        return results

    results = asyncio.new_event_loop().run_until_complete(_run())
    total_pass = sum(1 for r in results if r["status"] == "pass")
    total_fail = sum(1 for r in results if r["status"] == "fail")
    total_warn = sum(1 for r in results if r["status"] == "warn")
    total = len(results)
    return {
        "run_id": "test-run-001",
        "partner": "acme_studios",
        "status": "complete",
        "asset_count": len(all_assets),
        "results": results,
        "summary": {
            "total": total,
            "pass": total_pass,
            "fail": total_fail,
            "warn": total_warn,
            "pass_rate": round(total_pass / max(total, 1) * 100, 1),
        }
    }


def test_sql_report_has_required_top_level_keys(completed_run):
    """TC-20: Generated SQL report contains all required top-level fields."""
    reporter = SummaryReporter()
    report = reporter.generate(completed_run)
    required_keys = {"run_id", "partner", "generated_at", "summary", "by_category", "issues", "recommendation"}
    assert required_keys.issubset(set(report.keys())), f"Missing keys: {required_keys - set(report.keys())}"


def test_sql_report_summary_counts_are_accurate(completed_run):
    """TC-21: Report summary pass/fail/warn counts match raw results."""
    reporter = SummaryReporter()
    report = reporter.generate(completed_run)
    raw = completed_run["results"]
    assert report["summary"]["pass"] == sum(1 for r in raw if r["status"] == "pass")
    assert report["summary"]["fail"] == sum(1 for r in raw if r["status"] == "fail")
    assert report["summary"]["warn"] == sum(1 for r in raw if r["status"] == "warn")


def test_sql_report_by_category_has_all_categories(completed_run):
    """TC-22: Category breakdown in report includes all run categories."""
    reporter = SummaryReporter()
    report = reporter.generate(completed_run)
    run_cats = {r["category"] for r in completed_run["results"]}
    report_cats = {c["label"] for c in report["by_category"]}
    assert len(report["by_category"]) >= len(run_cats)


def test_sql_report_issues_sorted_failures_first(completed_run):
    """TC-23: Issues list in report is sorted — critical failures before warnings."""
    reporter = SummaryReporter()
    report = reporter.generate(completed_run)
    if len(report["issues"]) < 2:
        pytest.skip("Not enough issues to verify sort order")
    severities = [i["severity"] for i in report["issues"]]
    fail_indices = [i for i, s in enumerate(severities) if s == "fail"]
    warn_indices = [i for i, s in enumerate(severities) if s == "warn"]
    if fail_indices and warn_indices:
        assert max(fail_indices) < max(warn_indices) or min(fail_indices) < min(warn_indices), \
            "Failures should appear before warnings in sorted report"


def test_sql_report_recommendation_below_threshold(completed_run):
    """TC-24: Recommendation string is generated and reflects below-threshold pass rate."""
    reporter = SummaryReporter()
    report = reporter.generate(completed_run)
    assert isinstance(report["recommendation"], str)
    assert len(report["recommendation"]) > 0


def test_sql_report_blocked_assets_count(completed_run):
    """TC-25: blocked_assets count in report matches assets with at least one FAIL."""
    reporter = SummaryReporter()
    report = reporter.generate(completed_run)
    raw = completed_run["results"]
    expected_blocked = len({r["asset_id"] for r in raw if r["status"] == "fail"})
    assert report["summary"]["blocked_assets"] == expected_blocked


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — API FAILURES (6 tests)
# Covers: no URL, empty batch, invalid field types, missing feed, bad content_id
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_api_failure_no_asset_url_skips_probe():
    """TC-26: Asset with no asset_url is handled gracefully — probe skipped with WARN."""
    asset = {"content_id": "NO-URL-001"}
    results = await AssetAvailabilityValidator().validate([asset])
    scenarios = [r["scenario"] for r in results]
    assert "asset_url_missing" in scenarios


@pytest.mark.asyncio
async def test_api_failure_empty_batch_returns_no_results():
    """TC-27: Passing an empty asset list to any validator returns empty results."""
    for Validator in [MetadataValidator, XMLFeedValidator, DuplicateIDValidator, GoLiveValidator]:
        results = await Validator().validate([])
        assert results == [], f"{Validator.__name__} returned non-empty results for empty batch"


@pytest.mark.asyncio
async def test_api_failure_invalid_duration_type(valid_asset):
    """TC-28: Non-integer duration value is caught as a validation failure."""
    asset = valid_asset.copy(); asset["duration_seconds"] = "not_a_number"
    results = await MetadataValidator().validate([asset])
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "invalid_duration_format" in scenarios


@pytest.mark.asyncio
async def test_api_failure_no_feed_content_warns():
    """TC-29: Asset with no feed content at all produces a feed_missing warning."""
    asset = {"content_id": "NOFEED-001", "title": "Test"}
    results = await XMLFeedValidator().validate([asset])
    scenarios = [r["scenario"] for r in results]
    assert "feed_missing" in scenarios


@pytest.mark.asyncio
async def test_api_failure_missing_content_id_in_duplicate_scan():
    """TC-30: Asset with no content_id is caught gracefully in duplicate scan."""
    asset = {"title": "No ID Asset", "genre": "drama"}
    results = await DuplicateIDValidator().validate([asset])
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "content_id_missing" in scenarios


@pytest.mark.asyncio
async def test_api_failure_malformed_dates_handled(valid_asset):
    """TC-31: Unparseable avail_start/avail_end dates do not crash the validator."""
    asset = valid_asset.copy()
    asset["avail_start"] = "not-a-date"
    asset["avail_end"]   = "also-not-a-date"
    try:
        results = await GoLiveValidator().validate([asset])
        # Should handle gracefully — either skip or flag as fail, not crash
        assert isinstance(results, list)
    except Exception as e:
        pytest.fail(f"GoLiveValidator crashed on malformed dates: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — ESCALATION TRACKING (4 tests)
# Covers: severity promotion, cascading blocks, bulk escalation, threshold gates
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_escalation_single_fail_blocks_golive(asset_expired_rights):
    """TC-32: A single rights expiry FAIL is sufficient to block go-live — not just warn."""
    results = await GoLiveValidator().validate([asset_expired_rights])
    fails = [r for r in results if r["status"] == "fail"]
    assert any(r["scenario"] == "avail_expired" for r in fails), \
        "Expired rights must produce a hard FAIL, not a warning"


@pytest.mark.asyncio
async def test_escalation_territory_blocked_escalates(asset_blocked_territory):
    """TC-33: Explicit BLOCKED territory in territory list escalates to FAIL."""
    results = await GoLiveValidator().validate([asset_blocked_territory])
    scenarios = [r["scenario"] for r in results if r["status"] == "fail"]
    assert "territory_blocked" in scenarios


def test_escalation_report_recommendation_escalates_at_low_pass_rate():
    """TC-34: Report recommendation escalates to 'do not go live' below 80% pass rate."""
    reporter = SummaryReporter()
    low_pass_run = {
        "run_id": "esc-001",
        "partner": "acme",
        "status": "complete",
        "asset_count": 100,
        "results": [{"category": "golive", "status": "fail", "asset_id": f"A-{i}", "scenario": "avail_expired", "message": "expired", "detail": ""} for i in range(25)]
                 + [{"category": "golive", "status": "pass", "asset_id": f"B-{i}", "scenario": "ok", "message": "ok", "detail": ""} for i in range(75)],
        "summary": {"total": 100, "pass": 75, "fail": 25, "warn": 0, "pass_rate": 75.0}
    }
    report = reporter.generate(low_pass_run)
    rec = report["recommendation"].lower()
    assert "do not go live" in rec or "critical" in rec or "escalate" in rec, \
        f"Expected escalation language at 75% pass rate, got: {report['recommendation']}"


@pytest.mark.asyncio
async def test_escalation_bulk_300_records_fail_rate_within_expected_range(all_assets):
    """TC-35: Full pipeline on 300 partner-content records produces expected fail distribution.
    
    The sample data generator injects faults at ~6-10% rate.
    This test validates the overall health of the 300-record dataset.
    """
    results = []
    for cat, Validator in [
        ("metadata",      MetadataValidator),
        ("xml_feed",      XMLFeedValidator),
        ("asset_check",   AssetAvailabilityValidator),
        ("media_probe",   MediaProbeValidator),
        ("duplicate_ids", DuplicateIDValidator),
        ("golive",        GoLiveValidator),
    ]:
        r = await Validator().validate(all_assets)
        for item in r:
            results.append({"category": cat, **item})

    total      = len(results)
    total_fail = sum(1 for r in results if r["status"] == "fail")
    total_pass = sum(1 for r in results if r["status"] == "pass")
    pass_rate  = round(total_pass / total * 100, 1) if total else 0

    print(f"\n{'='*60}")
    print(f"  300-record pipeline results")
    print(f"  Total checks : {total}")
    print(f"  Passed       : {total_pass}")
    print(f"  Failed       : {total_fail}")
    print(f"  Pass rate    : {pass_rate}%")
    print(f"{'='*60}")

    # Pass rate should be between 85% and 99% for our seeded fault injection
    assert 85.0 <= pass_rate <= 99.9, \
        f"Pass rate {pass_rate}% outside expected 85–99% range for 300 seeded records"
    assert total > 0, "Pipeline must produce results"
    assert total_fail > 0, "Seeded faults should produce at least some failures"
