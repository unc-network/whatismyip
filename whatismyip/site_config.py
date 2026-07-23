"""Site configuration loader — reads data/config.toml into app.config."""

import ipaddress
import os
import shutil

from flask import Flask

try:
    import tomllib
except ImportError:
    import tomli as tomllib

_APP_ROOT = os.path.join(os.path.dirname(__file__), "..")
SITE_CONFIG_PATH = os.path.join(_APP_ROOT, "data", "config.toml")


def load_site_config(app: Flask) -> None:
    """Load data/config.toml and apply settings to app.config.

    If the file does not exist it is written with built-in defaults so that
    the persistent volume in OpenShift self-bootstraps on first deploy.
    Falls back silently to built-in defaults on any error so the app always starts.
    """
    os.makedirs(os.path.dirname(SITE_CONFIG_PATH), exist_ok=True)

    if not os.path.exists(SITE_CONFIG_PATH):
        app.logger.warning(
            f"Site config not found at {SITE_CONFIG_PATH} — writing defaults."
        )
        try:
            _write_default_config()
        except Exception as exc:
            app.logger.error(f"Could not write default config: {exc}")
        _apply_defaults(app)
        return

    try:
        with open(SITE_CONFIG_PATH, "rb") as fh:
            site_cfg = tomllib.load(fh)

        cidr_list = site_cfg.get("campus", {}).get("networks", [])
        if not cidr_list:
            app.logger.warning(
                f"{SITE_CONFIG_PATH} has no campus.networks — all visitors will be treated as off-campus."
            )
        networks = _parse_campus_networks(app, cidr_list)
        app.config["CAMPUS_NETWORKS"] = networks
        app.logger.info(
            f"Loaded {len(networks)} campus networks from {SITE_CONFIG_PATH}"
        )

        dns_test_url = site_cfg.get("dns", {}).get("security_filter_test_url", "")
        app.config["DNS_SECURITY_TEST_URL"] = dns_test_url
        if dns_test_url:
            app.logger.info(f"DNS security filter test URL: {dns_test_url}")
        else:
            app.logger.info(
                "DNS security filter test URL not configured — test disabled."
            )

        map_provider = site_cfg.get("map", {}).get("provider", "leaflet")
        if map_provider not in ("google", "leaflet"):
            app.logger.warning(
                f"Unknown map provider '{map_provider}', falling back to 'leaflet'."
            )
            map_provider = "leaflet"
        app.config["MAP_PROVIDER"] = map_provider

        site_section = site_cfg.get("site", {})
        app.config["SITE_NAME"] = site_section.get("name", "")
        app.config["SITE_CITY"] = site_section.get("city", "")
        app.config["SITE_REGION"] = site_section.get("region", "")
        app.config["SITE_COUNTRY_CODE"] = site_section.get("country_code", "")
        app.config["SITE_COUNTRY_NAME"] = site_section.get("country_name", "")
        app.config["SITE_LAT"] = site_section.get("lat", 0.0)
        app.config["SITE_LON"] = site_section.get("lon", 0.0)
        app.config["BING_VERIFICATION_TOKEN"] = site_section.get(
            "bing_verification_token", ""
        )
        app.config["INDEXNOW_KEY"] = site_section.get("indexnow_key", "")

        app.config["CONNECTIVITY_TARGETS"] = site_cfg.get("connectivity", {}).get(
            "targets", []
        )

        metrics_section = site_cfg.get("metrics", {})
        app.config["METRICS_TIME_WINDOW_DAYS"] = int(
            metrics_section.get("window_days", 30)
        )
        app.config["METRICS_RETENTION_DAYS"] = int(
            metrics_section.get("retention_days", 90)
        )

    except Exception as exc:
        app.logger.error(
            f"Failed to load {SITE_CONFIG_PATH}: {exc} — using built-in defaults."
        )
        _apply_defaults(app)


def _parse_campus_networks(
    app: Flask, cidr_list: list[str]
) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    networks = []
    for cidr in cidr_list:
        try:
            networks.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            app.logger.warning(f"Skipping invalid campus network CIDR: {cidr!r}")
    return networks


def _write_default_config() -> None:
    """Seed SITE_CONFIG_PATH from data/config.toml.example on first deploy."""
    example = os.path.join(
        os.path.dirname(__file__), "..", "data", "config.toml.example"
    )
    if os.path.exists(example):
        shutil.copy2(example, SITE_CONFIG_PATH)
    else:
        with open(SITE_CONFIG_PATH, "w") as fh:
            fh.write(
                "# Configure campus networks — see config.toml.example.\n"
                "[campus]\nnetworks = []\n"
            )


def _apply_defaults(app: Flask) -> None:
    app.config["CAMPUS_NETWORKS"] = []
    app.config["DNS_SECURITY_TEST_URL"] = ""
    app.config["MAP_PROVIDER"] = "leaflet"
    app.config["SITE_NAME"] = ""
    app.config["SITE_CITY"] = ""
    app.config["SITE_REGION"] = ""
    app.config["SITE_COUNTRY_CODE"] = ""
    app.config["SITE_COUNTRY_NAME"] = ""
    app.config["SITE_LAT"] = 0.0
    app.config["SITE_LON"] = 0.0
    app.config["BING_VERIFICATION_TOKEN"] = ""
    app.config["INDEXNOW_KEY"] = ""
    app.config["CONNECTIVITY_TARGETS"] = []
    app.config["METRICS_TIME_WINDOW_DAYS"] = 30
    app.config["METRICS_RETENTION_DAYS"] = 90
