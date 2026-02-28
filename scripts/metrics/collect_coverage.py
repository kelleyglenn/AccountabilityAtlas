"""
Extract JaCoCo test coverage data from all Java microservices.

Parses JaCoCo CSV reports (preferred) or XML reports (fallback) and outputs
a JSON summary with instruction, branch, line, method, and complexity coverage
percentages for each service.

Usage:
    python scripts/metrics/collect_coverage.py

Output:
    scripts/metrics/coverage_data.json
"""

import csv
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Use UTF-8 for stdout on Windows
sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_FILE = BASE_DIR / "scripts" / "metrics" / "coverage_data.json"

SERVICES = {
    "user-service": "AcctAtlas-user-service",
    "video-service": "AcctAtlas-video-service",
    "location-service": "AcctAtlas-location-service",
    "search-service": "AcctAtlas-search-service",
    "moderation-service": "AcctAtlas-moderation-service",
    "api-gateway": "AcctAtlas-api-gateway",
}

JACOCO_REPORT_PATH = Path("build", "reports", "jacoco", "test")
CSV_FILENAME = "jacocoTestReport.csv"
XML_FILENAME = "jacocoTestReport.xml"

# Counter types we care about
COUNTER_TYPES = ["INSTRUCTION", "BRANCH", "LINE", "COMPLEXITY", "METHOD"]


def calc_percentage(covered: int, missed: int) -> float:
    """Calculate coverage percentage, returning 0.0 if no data."""
    total = covered + missed
    if total == 0:
        return 0.0
    return round((covered / total) * 100, 1)


def parse_csv_report(csv_path: Path) -> dict:
    """Parse a JaCoCo CSV report and aggregate coverage across all rows."""
    totals = {}
    for ct in COUNTER_TYPES:
        totals[f"{ct}_COVERED"] = 0
        totals[f"{ct}_MISSED"] = 0

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for ct in COUNTER_TYPES:
                totals[f"{ct}_COVERED"] += int(row[f"{ct}_COVERED"])
                totals[f"{ct}_MISSED"] += int(row[f"{ct}_MISSED"])

    return build_result(totals)


def parse_xml_report(xml_path: Path) -> dict:
    """Parse a JaCoCo XML report and extract report-level counters."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    totals = {}
    for ct in COUNTER_TYPES:
        totals[f"{ct}_COVERED"] = 0
        totals[f"{ct}_MISSED"] = 0

    for counter in root.findall("counter"):
        ctype = counter.attrib["type"]
        if ctype in COUNTER_TYPES:
            totals[f"{ctype}_COVERED"] += int(counter.attrib["covered"])
            totals[f"{ctype}_MISSED"] += int(counter.attrib["missed"])

    return build_result(totals)


def build_result(totals: dict) -> dict:
    """Build the coverage result dict from aggregated totals."""
    return {
        "instruction_coverage": calc_percentage(
            totals["INSTRUCTION_COVERED"], totals["INSTRUCTION_MISSED"]
        ),
        "branch_coverage": calc_percentage(
            totals["BRANCH_COVERED"], totals["BRANCH_MISSED"]
        ),
        "line_coverage": calc_percentage(
            totals["LINE_COVERED"], totals["LINE_MISSED"]
        ),
        "method_coverage": calc_percentage(
            totals["METHOD_COVERED"], totals["METHOD_MISSED"]
        ),
        "complexity_coverage": calc_percentage(
            totals["COMPLEXITY_COVERED"], totals["COMPLEXITY_MISSED"]
        ),
        "lines_covered": totals["LINE_COVERED"],
        "lines_missed": totals["LINE_MISSED"],
        "total_lines": totals["LINE_COVERED"] + totals["LINE_MISSED"],
    }


def main():
    results = {}

    for display_name, dir_name in SERVICES.items():
        service_dir = BASE_DIR / dir_name
        report_dir = service_dir / JACOCO_REPORT_PATH

        csv_path = report_dir / CSV_FILENAME
        xml_path = report_dir / XML_FILENAME

        if csv_path.exists():
            print(f"  {display_name}: parsing CSV report")
            results[display_name] = parse_csv_report(csv_path)
        elif xml_path.exists():
            print(f"  {display_name}: parsing XML report")
            results[display_name] = parse_xml_report(xml_path)
        else:
            print(f"  {display_name}: NO REPORT FOUND (skipped)")
            continue

        cov = results[display_name]
        print(
            f"    -> line={cov['line_coverage']}% "
            f"branch={cov['branch_coverage']}% "
            f"instruction={cov['instruction_coverage']}% "
            f"({cov['lines_covered']}/{cov['total_lines']} lines)"
        )

    output = {"services": results}

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults written to {OUTPUT_FILE}")
    print(f"Services processed: {len(results)}/{len(SERVICES)}")


if __name__ == "__main__":
    main()
