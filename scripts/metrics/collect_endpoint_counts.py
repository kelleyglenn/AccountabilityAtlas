#!/usr/bin/env python
"""Count REST API endpoints from OpenAPI specification files across all services.

Parses the `paths:` section of each service's docs/api-specification.yaml and
counts HTTP methods (GET, POST, PUT, DELETE, PATCH) per service.

Usage:
    python scripts/metrics/collect_endpoint_counts.py

Output:
    scripts/metrics/endpoint_counts.json
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT = ROOT / "scripts" / "metrics" / "endpoint_counts.json"

HTTP_METHODS = ("get", "post", "put", "delete", "patch")

SERVICES = {
    "user-service": ROOT / "AcctAtlas-user-service" / "docs" / "api-specification.yaml",
    "video-service": ROOT / "AcctAtlas-video-service" / "docs" / "api-specification.yaml",
    "location-service": ROOT / "AcctAtlas-location-service" / "docs" / "api-specification.yaml",
    "search-service": ROOT / "AcctAtlas-search-service" / "docs" / "api-specification.yaml",
    "moderation-service": ROOT / "AcctAtlas-moderation-service" / "docs" / "api-specification.yaml",
    "notification-service": ROOT / "AcctAtlas-notification-service" / "docs" / "api-specification.yaml",
    "api-gateway": ROOT / "AcctAtlas-api-gateway" / "docs" / "api-specification.yaml",
}


def count_endpoints(spec_path):
    """Parse an OpenAPI YAML file and count endpoints by HTTP method.

    Uses simple line-based parsing to avoid requiring a YAML library.
    Relies on the standard OpenAPI structure where paths are top-level keys
    under `paths:` and HTTP methods are indented under each path.
    """
    counts = {m.upper(): 0 for m in HTTP_METHODS}
    paths = 0
    in_paths = False
    current_indent = None

    try:
        with open(spec_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"  WARNING: {spec_path} not found, skipping")
        return None

    for line in lines:
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())

        # Detect the `paths:` top-level section
        if stripped == "paths:":
            in_paths = True
            current_indent = indent
            continue

        # Detect leaving the paths section (another top-level key)
        if in_paths and indent == current_indent and stripped.endswith(":"):
            in_paths = False
            continue

        if not in_paths:
            continue

        # A path entry is typically indented one level under `paths:`
        # and starts with / (e.g., "  /users:" or "  '/users/{id}':")
        key = stripped.rstrip(":").strip().strip("'\"")
        if key.startswith("/"):
            paths += 1
            continue

        # HTTP method entries are indented under the path
        method = stripped.strip().rstrip(":").lower()
        if method in HTTP_METHODS:
            counts[method.upper()] += 1

    counts["total"] = sum(counts[m.upper()] for m in HTTP_METHODS)
    counts["paths"] = paths
    return counts


def main():
    print("Counting API endpoints from OpenAPI specifications...")

    results = {"services": {}, "overall": {}}
    overall = {m.upper(): 0 for m in HTTP_METHODS}
    overall["total"] = 0
    overall["paths"] = 0

    for name, spec_path in SERVICES.items():
        print(f"  {name}: {spec_path}")
        counts = count_endpoints(spec_path)
        if counts is None:
            continue

        results["services"][name] = counts
        for m in HTTP_METHODS:
            overall[m.upper()] += counts[m.upper()]
        overall["total"] += counts["total"]
        overall["paths"] += counts["paths"]

        print(f"    {counts['total']} endpoints across {counts['paths']} paths")

    results["overall"] = overall

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nResults written to {OUTPUT}")
    print(f"Overall: {overall['total']} endpoints across {overall['paths']} paths")


if __name__ == "__main__":
    main()
