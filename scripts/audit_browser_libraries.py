#!/usr/bin/env python3
"""Verify vendored asset hashes and query OSV for their exact npm versions.

No npm installation or frontend build is needed. Run with --offline to check
only the local assets; CI always includes the live advisory query.
"""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
OSV_URL = "https://api.osv.dev/v1/querybatch"


def verify_assets(packages: list[dict], root: Path) -> None:
    if not packages:
        raise ValueError("Browser library inventory is empty")
    for package in packages:
        if not package["files"]:
            raise ValueError(f"No assets recorded for {package['name']}")
        for filename, expected in package["files"].items():
            actual = hashlib.sha256((root / filename).read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError(f"Vendored asset hash mismatch: {filename}")


def find_advisories(packages: list[dict]) -> list[str]:
    queries = [
        {
            "package": {"name": package["name"], "ecosystem": "npm"},
            "version": package["version"],
        }
        for package in packages
    ]
    response = requests.post(OSV_URL, json={"queries": queries}, timeout=(5, 30))
    response.raise_for_status()
    results = response.json()["results"]
    if not isinstance(results, list) or len(results) != len(packages):
        raise ValueError("OSV returned an incomplete advisory response")
    advisories = []
    for package, result in zip(packages, results, strict=True):
        vulns = result.get("vulns", [])
        if not isinstance(vulns, list):
            raise ValueError("OSV returned an invalid advisory response")
        for vuln in vulns:
            advisories.append(
                f"{package['name']}@{package['version']}: "
                f"https://osv.dev/vulnerability/{vuln['id']}"
            )
    return advisories


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    try:
        packages = json.loads((REPO_ROOT / "browser-libraries.json").read_text())[
            "packages"
        ]
        verify_assets(packages, REPO_ROOT)
        print("Vendored browser asset hashes verified.")
        if args.offline:
            print("Offline mode: vulnerability advisories were not checked.")
            return 0
        advisories = find_advisories(packages)
        if advisories:
            print("Known browser dependency vulnerabilities:", file=sys.stderr)
            for advisory in advisories:
                print(f"  {advisory}", file=sys.stderr)
            return 1
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        print(
            f"No known OSV vulnerabilities for {len(packages)} libraries ({timestamp})."
        )
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        requests.RequestException,
    ) as error:
        print(f"Browser dependency audit failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
