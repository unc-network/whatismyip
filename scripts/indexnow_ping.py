#!/usr/bin/env python3
"""Notify Bing IndexNow of updated pages after a production deployment.

Usage:
    python scripts/indexnow_ping.py

Reads indexnow_key from data/config.toml and SERVER_URL from .env.
Run this from the repo root after confirming production is live.
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        print("error: requires Python 3.11+ or 'pip install tomli'", file=sys.stderr)
        sys.exit(1)

REPO_ROOT = Path(__file__).parent.parent


def load_config() -> dict:
    config_path = REPO_ROOT / "data" / "config.toml"
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def load_env_var(name: str) -> str:
    # Check real environment first (production containers set FLASK_-prefixed vars)
    for candidate in (name, f"FLASK_{name}"):
        val = os.environ.get(candidate, "")
        if val:
            return val

    # Fall back to .env file for local dev
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            if key.strip() in (name, f"FLASK_{name}"):
                return val.strip().strip('"').strip("'")
    return ""


def main() -> None:
    config = load_config()
    key = config.get("site", {}).get("indexnow_key", "")
    if not key:
        print("error: indexnow_key not set in data/config.toml", file=sys.stderr)
        sys.exit(1)

    site_url = load_env_var("SERVER_URL").rstrip("/")
    if not site_url or "127.0.0.1" in site_url or "localhost" in site_url:
        print(f"error: SERVER_URL looks like a dev URL: {site_url!r}", file=sys.stderr)
        print(
            "       Set SERVER_URL in .env to the production URL before running.",
            file=sys.stderr,
        )
        sys.exit(1)

    host = site_url.removeprefix("https://").removeprefix("http://")

    pages = [
        "/",
        "/speedtest",
        "/connectivity",
        "/faq",
        "/about",
        "/metrics",
    ]
    url_list = [f"{site_url}{path}" for path in pages]

    payload = json.dumps(
        {
            "host": host,
            "key": key,
            "urlList": url_list,
        }
    ).encode()

    print(f"Pinging Bing IndexNow for {host}...")
    for url in url_list:
        print(f"  {url}")

    req = urllib.request.Request(
        "https://www.bing.com/indexnow",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            print(f"\nResponse: {resp.status} {resp.reason}")
            if resp.status == 200:
                print("Success — Bing has been notified.")
            elif resp.status == 202:
                print("Accepted — URLs queued for crawling.")
    except urllib.error.HTTPError as e:
        print(f"\nHTTP error: {e.code} {e.reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
