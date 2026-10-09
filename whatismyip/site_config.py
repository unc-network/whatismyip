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

        dns_section = site_cfg.get("dns", {})
        app.config["DNS_LOOKUP_ENABLED"] = bool(
            dns_section.get("lookup_enabled", False)
        )
        app.config["DNS_LOOKUP_PAGE_CAMPUS_ONLY"] = bool(
            dns_section.get("page_campus_only", False)
        )
        app.config["DNS_LOOKUP_INTERNAL_CAMPUS_ONLY"] = bool(
            dns_section.get("internal_results_campus_only", True)
        )
        app.config["DNS_LOOKUP_INTERNAL_RESOLVER"] = _parse_resolver_address(
            app, dns_section.get("internal_resolver", ""), "internal"
        )
        app.config["DNS_LOOKUP_PUBLIC_RESOLVER"] = _parse_resolver_address(
            app, dns_section.get("public_resolver", "8.8.8.8"), "public"
        )
        allowed_types = dns_section.get(
            "allowed_record_types",
            ["A", "AAAA", "CNAME", "MX", "TXT", "NS", "SOA", "PTR"],
        )
        valid_types = {"A", "AAAA", "CNAME", "MX", "TXT", "NS", "SOA", "PTR"}
        app.config["DNS_LOOKUP_ALLOWED_TYPES"] = [
            str(value).upper()
            for value in allowed_types
            if str(value).upper() in valid_types
        ] or ["A", "AAAA"]
        app.config["DNS_LOOKUP_TIMEOUT"] = _bounded_float(
            dns_section.get("query_timeout_seconds", 3.0), 3.0, 0.25, 10.0
        )
        app.config["DNS_LOOKUP_RATE_LIMIT"] = _bounded_int(
            dns_section.get("queries_per_minute", 30), 30, 1, 300
        )
        app.config["DNS_LOOKUP_GLOBAL_RATE_LIMIT"] = _bounded_int(
            dns_section.get("global_queries_per_minute", 300), 300, 1, 3000
        )
        app.config["DNS_LOOKUP_MAX_CONCURRENT"] = _bounded_int(
            dns_section.get("max_concurrent_lookups", 4), 4, 1, 4
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

        app.config["STATUS_PAGE_URL"] = (
            site_cfg.get("status_page", {}).get("url", "").rstrip("/")
        )

        metrics_section = site_cfg.get("metrics", {})
        app.config["METRICS_TIME_WINDOW_DAYS"] = int(
            metrics_section.get("window_days", 30)
        )
        app.config["METRICS_RETENTION_DAYS"] = int(
            metrics_section.get("retention_days", 90)
        )

        vpn_section = site_cfg.get("vpn", {})
        app.config["VPN_PROVIDER_NAME"] = vpn_section.get("provider_name", "")
        app.config["VPN_INSTALL_URL"] = vpn_section.get("install_url", "")
        app.config["VPN_NETWORKS"] = _parse_campus_networks(
            app, vpn_section.get("networks", [])
        )

        ssid_map: dict = {}
        for entry in site_cfg.get("wireless", {}).get("ssids", []):
            name = entry.get("name", "").strip()
            if name:
                ssid_map[name] = {
                    "description": entry.get("description", ""),
                    "usage": entry.get("usage", ""),
                    "expected": entry.get("expected", True),
                }
        app.config["SSID_INFO"] = ssid_map

        app.config["NETWORK_NOTES"] = _parse_network_notes(
            app, site_cfg.get("network_notes", [])
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


def _parse_network_notes(
    app: Flask, entries: list[dict]
) -> list[tuple[ipaddress.IPv4Network, str]]:
    """Flatten [[network_notes]] blocks into (network, message) pairs.

    Only IPv4 networks are accepted; notes are shown from the IPv4 result alone.
    """
    notes = []
    for entry in entries:
        message = str(entry.get("message", "")).strip()
        if not message:
            app.logger.warning(f"Skipping network note with no message: {entry!r}")
            continue
        for cidr in entry.get("networks", []):
            try:
                network = ipaddress.ip_network(cidr, strict=False)
            except ValueError:
                app.logger.warning(f"Skipping invalid network note CIDR: {cidr!r}")
                continue
            if network.version != 4:
                app.logger.warning(f"Skipping non-IPv4 network note CIDR: {cidr!r}")
                continue
            notes.append((network, message))
    return notes


def _parse_resolver_address(app: Flask, value: object, label: str) -> str:
    address = str(value).strip()
    if not address:
        return ""
    try:
        return str(ipaddress.ip_address(address))
    except ValueError:
        app.logger.warning(
            f"Ignoring invalid {label} DNS resolver address: {address!r}"
        )
        return ""


def _bounded_float(
    value: object, default: float, minimum: float, maximum: float
) -> float:
    try:
        return max(minimum, min(maximum, float(value)))
    except (TypeError, ValueError):
        return default


def _bounded_int(value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


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
    app.config["DNS_LOOKUP_ENABLED"] = False
    app.config["DNS_LOOKUP_PAGE_CAMPUS_ONLY"] = False
    app.config["DNS_LOOKUP_INTERNAL_CAMPUS_ONLY"] = True
    app.config["DNS_LOOKUP_INTERNAL_RESOLVER"] = ""
    app.config["DNS_LOOKUP_PUBLIC_RESOLVER"] = "8.8.8.8"
    app.config["DNS_LOOKUP_ALLOWED_TYPES"] = [
        "A",
        "AAAA",
        "CNAME",
        "MX",
        "TXT",
        "NS",
        "SOA",
        "PTR",
    ]
    app.config["DNS_LOOKUP_TIMEOUT"] = 3.0
    app.config["DNS_LOOKUP_RATE_LIMIT"] = 30
    app.config["DNS_LOOKUP_GLOBAL_RATE_LIMIT"] = 300
    app.config["DNS_LOOKUP_MAX_CONCURRENT"] = 4
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
    app.config["STATUS_PAGE_URL"] = ""
    app.config["METRICS_TIME_WINDOW_DAYS"] = 30
    app.config["METRICS_RETENTION_DAYS"] = 90
    app.config["VPN_PROVIDER_NAME"] = ""
    app.config["VPN_INSTALL_URL"] = ""
    app.config["VPN_NETWORKS"] = []
    app.config["SSID_INFO"] = {}
    app.config["NETWORK_NOTES"] = []
