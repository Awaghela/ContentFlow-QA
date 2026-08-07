#!/usr/bin/env python3
"""
ContentFlow QA — CLI Validation Runner
=======================================
Run the full validation pipeline from the command line.

Usage:
    python3 scripts/run_validation.py --partner acme --count 500
    python3 scripts/run_validation.py --partner acme --assets path/to/assets.json
"""

import asyncio
import json
import sys
import os
import argparse
from datetime import datetime

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.validators.metadata import MetadataValidator
from backend.validators.xml_feed import XMLFeedValidator
from backend.validators.asset_check import AssetAvailabilityValidator
from backend.validators.media_probe import MediaProbeValidator
from backend.validators.duplicate_ids import DuplicateIDValidator
from backend.validators.golive import GoLiveValidator
from backend.reports.summary import SummaryReporter
from scripts.generate_sample_data import generate_sample_assets

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich import print as rprint
    RICH = True
    console = Console()
except ImportError:
    RICH = False
    console = None


VALIDATORS = [
    ("metadata",      "Metadata validation",    MetadataValidator),
    ("xml_feed",      "XML / Feed parsing",     XMLFeedValidator),
    ("asset_check",   "Asset availability",     AssetAvailabilityValidator),
    ("media_probe",   "FFmpeg media probe",     MediaProbeValidator),
    ("duplicate_ids", "Duplicate ID scan",      DuplicateIDValidator),
    ("golive",        "Go-live readiness gate", GoLiveValidator),
]


async def run_pipeline(partner: str, assets: list[dict]) -> dict:
    all_results = []
    total_pass = total_fail = total_warn = 0

    if RICH:
        console.rule(f"[bold purple]ContentFlow QA[/] — Partner: [cyan]{partner}[/]")
        console.print(f"  Assets: [yellow]{len(assets)}[/]  ·  Scenarios: 40\n")

    for key, label, ValidatorClass in VALIDATORS:
        if RICH:
            with Progress(SpinnerColumn(), TextColumn(f"  {label}..."), console=console, transient=True) as prog:
                prog.add_task("", total=None)
                validator = ValidatorClass()
                results = await validator.validate(assets)
        else:
            print(f"  Running: {label}...")
            validator = ValidatorClass()
            results = await validator.validate(assets)

        p = sum(1 for r in results if r["status"] == "pass")
        f = sum(1 for r in results if r["status"] == "fail")
        w = sum(1 for r in results if r["status"] == "warn")
        total_pass += p; total_fail += f; total_warn += w

        for r in results:
            all_results.append({"category": key, **r})

        status_icon = "✅" if f == 0 else "❌"
        msg = f"  {status_icon} {label:<30} pass={p:>4}  fail={f:>3}  warn={w:>3}"
        if RICH:
            color = "green" if f == 0 else "red"
            console.print(f"  [{color}]{'✅' if f==0 else '❌'}[/] {label:<30} pass=[green]{p:>4}[/]  fail=[red]{f:>3}[/]  warn=[yellow]{w:>3}[/]")
        else:
            print(msg)

    total = total_pass + total_fail + total_warn
    pass_rate = round(total_pass / max(total, 1) * 100, 1)

    run = {
        "run_id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "partner": partner,
        "status": "complete",
        "asset_count": len(assets),
        "results": all_results,
        "summary": {
            "total": total,
            "pass": total_pass,
            "fail": total_fail,
            "warn": total_warn,
            "pass_rate": pass_rate,
        },
    }

    if RICH:
        console.print()
        console.rule("[bold]Summary[/]")
        console.print(f"  Total checks : {total}")
        console.print(f"  [green]Passed       : {total_pass}[/]")
        console.print(f"  [red]Failed       : {total_fail}[/]")
        console.print(f"  [yellow]Warnings     : {total_warn}[/]")
        console.print(f"  Pass rate    : {'[green]' if pass_rate >= 95 else '[yellow]' if pass_rate >= 80 else '[red]'}{pass_rate}%[/]")
    else:
        print(f"\n--- Summary ---")
        print(f"  Total: {total}  Pass: {total_pass}  Fail: {total_fail}  Warn: {total_warn}")
        print(f"  Pass rate: {pass_rate}%")

    reporter = SummaryReporter()
    report = reporter.generate(run)
    if RICH:
        console.print(f"\n  [bold]{report['recommendation']}[/]")
    else:
        print(f"\n  {report['recommendation']}")

    return run


def main():
    parser = argparse.ArgumentParser(description="ContentFlow QA — validation pipeline CLI")
    parser.add_argument("--partner", default="demo_partner", help="Partner name")
    parser.add_argument("--count", type=int, default=500, help="Number of sample assets to generate")
    parser.add_argument("--assets", help="Path to JSON file with asset records (overrides --count)")
    parser.add_argument("--output", help="Write report to JSON file")
    args = parser.parse_args()

    if args.assets:
        with open(args.assets) as f:
            assets = json.load(f)
        print(f"Loaded {len(assets)} assets from {args.assets}")
    else:
        assets = generate_sample_assets(args.count)
        print(f"Generated {len(assets)} sample assets")

    run = asyncio.run(run_pipeline(args.partner, assets))

    if args.output:
        reporter = SummaryReporter()
        report = reporter.generate(run)
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nReport written to {args.output}")


if __name__ == "__main__":
    main()
