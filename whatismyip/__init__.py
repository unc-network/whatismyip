"""
Basic App
"""

import os
import logging
import sqlite3

try:
    import tomllib
except ImportError:
    import tomli as tomllib
from datetime import datetime, time as dt_time, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    make_response,
    redirect,
    send_from_directory,
    abort,
    url_for,
)
from flask_cors import CORS
from flask_compress import Compress

from dotenv import load_dotenv
from user_agents import parse
from dns import resolver, reversename
import dns.exception

from whatismyip.utils import *

# load dotenv in the base root
APP_ROOT = os.path.join(os.path.dirname(__file__), "..")  # refers to application_top
dotenv_path = os.path.join(APP_ROOT, ".env")
load_dotenv(dotenv_path)

app = Flask(__name__)
app.config.from_object("config.Config")
app.config.from_prefixed_env()
# from_prefixed_env() reads all values as strings; restore the expected int type.
app.config["METRICS_TIME_WINDOW_DAYS"] = int(
    app.config.get("METRICS_TIME_WINDOW_DAYS", 30)
)
Compress(app)

METRICS_TIMEZONE = ZoneInfo("America/New_York")

# Dual stack clients need to access both the v6 and v4 versions of this site.
api_config = {
    "origins": [
        app.config["SERVER_URL"],
        app.config["IPV4_SERVER_URL"],
        app.config["IPV6_SERVER_URL"],
    ]
}
CORS(app, resources={"/hostinfo": api_config})


@app.context_processor
def inject_site_name():
    """Inject site urls into templates."""
    return dict(
        site_url=app.config["SERVER_URL"],
        ipv4_url=app.config["IPV4_SERVER_URL"],
        ipv6_url=app.config["IPV6_SERVER_URL"],
        bing_verification_token=app.config.get("BING_VERIFICATION_TOKEN", ""),
    )


METRICS_DB_PATH = os.path.join(APP_ROOT, "data", "metrics.sqlite3")
SITE_CONFIG_PATH = os.path.join(APP_ROOT, "data", "config.toml")

import ipaddress as _ipaddress

# No built-in campus networks — each deployment must configure data/config.toml.
# An empty list means all visitors are treated as off-campus, which is the safe default.
_DEFAULT_CAMPUS_NETWORKS = []


def _parse_campus_networks(cidr_list):
    """Parse a list of CIDR strings into ip_network objects, skipping invalid entries."""
    networks = []
    for cidr in cidr_list:
        try:
            networks.append(_ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            app.logger.warning(f"Skipping invalid campus network CIDR: {cidr!r}")
    return networks


def _load_site_config():
    """Load data/config.toml and apply settings to app.config.

    If the file does not exist it is written with built-in defaults so that
    the persistent volume in OpenShift self-bootstraps on first deploy.
    Falls back silently to built-in defaults on any error so the app always starts.
    """
    # Ensure the data directory exists (important for fresh OpenShift PVCs).
    os.makedirs(os.path.dirname(SITE_CONFIG_PATH), exist_ok=True)

    if not os.path.exists(SITE_CONFIG_PATH):
        app.logger.warning(
            f"Site config not found at {SITE_CONFIG_PATH} — writing defaults."
        )
        try:
            _write_default_config()
        except Exception as exc:
            app.logger.error(f"Could not write default config: {exc}")
        app.config["CAMPUS_NETWORKS"] = _DEFAULT_CAMPUS_NETWORKS
        app.config["DNS_SECURITY_TEST_URL"] = ""
        app.config["SITE_NAME"] = ""
        app.config["SITE_CITY"] = ""
        app.config["SITE_COUNTRY_CODE"] = ""
        app.config["SITE_COUNTRY_NAME"] = ""
        app.config["SITE_LAT"] = 0.0
        app.config["SITE_LON"] = 0.0
        app.config["BING_VERIFICATION_TOKEN"] = ""
        app.config["INDEXNOW_KEY"] = ""
        return

    try:
        with open(SITE_CONFIG_PATH, "rb") as fh:
            site_cfg = tomllib.load(fh)
        cidr_list = site_cfg.get("campus", {}).get("networks", [])
        if not cidr_list:
            app.logger.warning(
                f"{SITE_CONFIG_PATH} has no campus.networks — all visitors will be treated as off-campus."
            )
        networks = _parse_campus_networks(cidr_list)
        app.config["CAMPUS_NETWORKS"] = networks
        app.logger.info(
            f"Loaded {len(networks)} campus networks from {SITE_CONFIG_PATH}"
        )

        dns_test_url = site_cfg.get("dns", {}).get("security_filter_test_url", "")
        app.config["DNS_SECURITY_TEST_URL"] = dns_test_url

        map_provider = site_cfg.get("map", {}).get("provider", "leaflet")
        if map_provider not in ("google", "leaflet"):
            app.logger.warning(
                f"Unknown map provider '{map_provider}', falling back to 'leaflet'."
            )
            map_provider = "leaflet"
        app.config["MAP_PROVIDER"] = map_provider
        if dns_test_url:
            app.logger.info(f"DNS security filter test URL: {dns_test_url}")
        else:
            app.logger.info(
                "DNS security filter test URL not configured — test disabled."
            )

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
    except Exception as exc:
        app.logger.error(
            f"Failed to load {SITE_CONFIG_PATH}: {exc} — using built-in defaults."
        )
        app.config["CAMPUS_NETWORKS"] = _DEFAULT_CAMPUS_NETWORKS
        app.config["DNS_SECURITY_TEST_URL"] = ""
        app.config["MAP_PROVIDER"] = "leaflet"
        app.config["SITE_REGION"] = ""
        app.config["SITE_NAME"] = ""
        app.config["SITE_CITY"] = ""
        app.config["SITE_COUNTRY_CODE"] = ""
        app.config["SITE_COUNTRY_NAME"] = ""
        app.config["SITE_LAT"] = 0.0
        app.config["SITE_LON"] = 0.0
        app.config["BING_VERIFICATION_TOKEN"] = ""
        app.config["INDEXNOW_KEY"] = ""


def _write_default_config():
    """Seed SITE_CONFIG_PATH from data/config.toml.example on first deploy."""
    import shutil

    example = os.path.join(
        os.path.dirname(__file__), "..", "data", "config.toml.example"
    )
    if os.path.exists(example):
        shutil.copy2(example, SITE_CONFIG_PATH)
    else:
        # Last resort: write a minimal valid stub.
        with open(SITE_CONFIG_PATH, "w") as fh:
            fh.write(
                "# Configure campus networks — see config.toml.example.\n"
                "[campus]\nnetworks = []\n"
            )


_load_site_config()


def _configured_hostname(url):
    """Return the lowercase hostname component for a configured URL."""
    return (urlsplit(url).hostname or "").lower()


@app.before_request
def redirect_split_stack_hosts_to_primary():
    """Redirect ipv4/ipv6 hostnames to the primary site, except for /hostinfo."""
    if request.path == "/hostinfo":
        return None

    incoming_host = (request.host.split(":", 1)[0] or "").lower()
    split_stack_hosts = {
        _configured_hostname(app.config["IPV4_SERVER_URL"]),
        _configured_hostname(app.config["IPV6_SERVER_URL"]),
    }

    if incoming_host == "127.0.0.1" or incoming_host == "localhost":
        # Allow localhost access for testing without redirecting.
        return None

    if incoming_host not in split_stack_hosts:
        return None

    primary = urlsplit(app.config["SERVER_URL"])
    target = f"{primary.scheme}://{primary.netloc}{request.path}"
    if request.query_string:
        target = f"{target}?{request.query_string.decode()}"
    return redirect(target, code=308)


def ensure_metrics_store():
    """Create the metrics database and schema when needed."""
    os.makedirs(os.path.dirname(METRICS_DB_PATH), exist_ok=True)
    with sqlite3.connect(METRICS_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                ip_version INTEGER,
                isp TEXT,
                org TEXT,
                asn TEXT,
                city TEXT,
                region TEXT,
                country TEXT,
                country_code TEXT,
                is_campus INTEGER,
                network_purpose TEXT,
                mobile INTEGER,
                proxy INTEGER,
                hosting INTEGER
            )
            """)

        # Backward-compatible schema migrations for existing DB files.
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(metrics_events)").fetchall()
        }
        for col, definition in [
            ("country", "TEXT"),
            ("org", "TEXT"),
            ("asn", "TEXT"),
            ("city", "TEXT"),
            ("region", "TEXT"),
            ("country_code", "TEXT"),
            ("mobile", "INTEGER"),
            ("proxy", "INTEGER"),
            ("hosting", "INTEGER"),
        ]:
            if col not in columns:
                conn.execute(
                    f"ALTER TABLE metrics_events ADD COLUMN {col} {definition}"
                )

        for index_sql in [
            "CREATE INDEX IF NOT EXISTS idx_metrics_events_created_at ON metrics_events(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_metrics_events_event_type ON metrics_events(event_type)",
            "CREATE INDEX IF NOT EXISTS idx_metrics_events_ip_version ON metrics_events(ip_version)",
            "CREATE INDEX IF NOT EXISTS idx_metrics_events_isp ON metrics_events(isp)",
            "CREATE INDEX IF NOT EXISTS idx_metrics_events_org ON metrics_events(org)",
            "CREATE INDEX IF NOT EXISTS idx_metrics_events_country ON metrics_events(country)",
            "CREATE INDEX IF NOT EXISTS idx_metrics_events_country_code ON metrics_events(country_code)",
            "CREATE INDEX IF NOT EXISTS idx_metrics_events_city ON metrics_events(city)",
        ]:
            conn.execute(index_sql)


def log_metrics_event(
    event_type,
    ip_version=None,
    isp=None,
    org=None,
    asn=None,
    city=None,
    region=None,
    country=None,
    country_code=None,
    is_campus=None,
    network_purpose=None,
    mobile=None,
    proxy=None,
    hosting=None,
):
    """Store a single aggregate metrics event without persisting raw IP addresses."""
    try:
        ensure_metrics_store()
        with sqlite3.connect(METRICS_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO metrics_events (
                    created_at,
                    event_type,
                    ip_version,
                    isp,
                    org,
                    asn,
                    city,
                    region,
                    country,
                    country_code,
                    is_campus,
                    network_purpose,
                    mobile,
                    proxy,
                    hosting
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    event_type,
                    ip_version,
                    isp,
                    org,
                    asn,
                    city,
                    region,
                    country,
                    country_code,
                    None if is_campus is None else int(bool(is_campus)),
                    network_purpose,
                    None if mobile is None else int(bool(mobile)),
                    None if proxy is None else int(bool(proxy)),
                    None if hosting is None else int(bool(hosting)),
                ),
            )
    except Exception as error:  # pragma: no cover - metrics must not break diagnostics
        app.logger.warning("Metrics logging skipped: %s", error)


def _count_by_query(conn, query, params=()):
    """Return a list of dictionaries from a grouped count query."""
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def _with_percentages(rows):
    """Add percentage values to grouped rows."""
    total = sum(row["count"] for row in rows)
    result = []
    for row in rows:
        percentage = round((row["count"] / total) * 100, 1) if total else 0
        result.append({**row, "percentage": percentage})
    return result


def get_metrics_dashboard(days=None):
    """Build the metrics summary data for the admin dashboard."""
    ensure_metrics_store()
    if days is None:
        days = app.config["METRICS_TIME_WINDOW_DAYS"]

    now_local = datetime.now(METRICS_TIMEZONE)
    today = now_local.date()
    first_day = today - timedelta(days=days - 1)
    cutoff = (
        datetime.combine(first_day, dt_time.min, tzinfo=METRICS_TIMEZONE)
        .astimezone(timezone.utc)
        .isoformat()
    )

    with sqlite3.connect(METRICS_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        total_hostinfo = conn.execute(
            "SELECT COUNT(*) AS count FROM metrics_events WHERE event_type = ?",
            ("hostinfo",),
        ).fetchone()["count"]

        total_campus = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM metrics_events
            WHERE event_type = ? AND is_campus = 1
            """,
            ("hostinfo",),
        ).fetchone()["count"]

        total_remote = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM metrics_events
            WHERE event_type = ? AND is_campus = 0
            """,
            ("hostinfo",),
        ).fetchone()["count"]

        daily_lookup = {}
        daily_events = conn.execute(
            """
            SELECT created_at
            FROM metrics_events
            WHERE event_type = ? AND created_at >= ?
            ORDER BY created_at
            """,
            ("hostinfo", cutoff),
        ).fetchall()
        for row in daily_events:
            day = (
                datetime.fromisoformat(row["created_at"])
                .astimezone(METRICS_TIMEZONE)
                .date()
                .isoformat()
            )
            daily_lookup[day] = daily_lookup.get(day, 0) + 1

        daily_series = []
        for offset in range(days):
            day = (today - timedelta(days=days - 1 - offset)).isoformat()
            daily_series.append({"day": day, "count": daily_lookup.get(day, 0)})
        daily_max = max((row["count"] for row in daily_series), default=0) or 1

        ip_versions = _with_percentages(
            _count_by_query(
                conn,
                """
                SELECT COALESCE(CAST(ip_version AS TEXT), 'Unknown') AS label, COUNT(*) AS count
                FROM metrics_events
                WHERE event_type = ?
                GROUP BY label
                ORDER BY count DESC
                """,
                ("hostinfo",),
            )
        )
        for row in ip_versions:
            if row["label"] == "4":
                row["label"] = "IPv4"
            elif row["label"] == "6":
                row["label"] = "IPv6"

        isp_breakdown = _with_percentages(
            _count_by_query(
                conn,
                """
                SELECT COALESCE(NULLIF(TRIM(isp), ''), 'Unknown') AS label, COUNT(*) AS count
                FROM metrics_events
                WHERE event_type = ?
                GROUP BY label
                ORDER BY count DESC
                LIMIT 10
                """,
                ("hostinfo",),
            )
        )

        org_breakdown = _with_percentages(
            _count_by_query(
                conn,
                """
                SELECT COALESCE(NULLIF(TRIM(org), ''), 'Unknown') AS label, COUNT(*) AS count
                FROM metrics_events
                WHERE event_type = ?
                GROUP BY label
                ORDER BY count DESC
                LIMIT 10
                """,
                ("hostinfo",),
            )
        )

        country_breakdown = _with_percentages(
            _count_by_query(
                conn,
                """
                SELECT COALESCE(NULLIF(TRIM(country), ''), 'Unknown') AS label, COUNT(*) AS count
                FROM metrics_events
                WHERE event_type = ?
                GROUP BY label
                ORDER BY count DESC
                LIMIT 10
                """,
                ("hostinfo",),
            )
        )

        campus_breakdown = _with_percentages(
            _count_by_query(
                conn,
                """
                SELECT CASE WHEN is_campus = 1 THEN 'Campus' ELSE 'Off campus' END AS label,
                       COUNT(*) AS count
                FROM metrics_events
                WHERE event_type = ?
                GROUP BY label
                ORDER BY count DESC
                """,
                ("hostinfo",),
            )
        )

        purpose_breakdown = _with_percentages(
            _count_by_query(
                conn,
                """
                SELECT COALESCE(NULLIF(TRIM(network_purpose), ''), 'Unknown') AS label, COUNT(*) AS count
                FROM metrics_events
                WHERE event_type = ? AND is_campus = 1
                GROUP BY label
                ORDER BY count DESC
                LIMIT 10
                """,
                ("hostinfo",),
            )
        )

    return {
        "window_days": days,
        "total_hostinfo": total_hostinfo,
        "total_campus": total_campus,
        "total_remote": total_remote,
        "daily_series": daily_series,
        "daily_max": daily_max,
        "ip_versions": ip_versions,
        "isp_breakdown": isp_breakdown,
        "org_breakdown": org_breakdown,
        "country_breakdown": country_breakdown,
        "campus_breakdown": campus_breakdown,
        "purpose_breakdown": purpose_breakdown,
    }


# Routes
@app.route("/")
def home():
    """Display the base homepage with IP address information."""
    data = {}
    client_address = None

    # get the request headers
    forwarded_for = request.environ.get("HTTP_X_FORWARDED_FOR", None)
    remote_address = request.environ.get("REMOTE_ADDR", None)

    # Check for PROXY usage
    tmp_forwarded_for = os.getenv("FORWARDED_FOR", forwarded_for)
    client_address = get_client_address(remote_address, tmp_forwarded_for)
    data["client_address"] = os.getenv("CLIENT_ADDRESS", client_address)
    app.logger.info(
        f"Home view from {client_address} with forwarded_for {tmp_forwarded_for}"
    )

    # Quickly flag if this is campus or not
    data["is_campus"] = is_campus_ip(client_address)
    app.logger.debug(
        f"Client address {client_address} is campus IP {data['is_campus']}"
    )

    # Add the ipv4/ipv6 specific test urls
    data["ipv4_url"] = app.config["IPV4_SERVER_URL"]
    data["ipv6_url"] = app.config["IPV6_SERVER_URL"]

    # Add Google Maps API key for client-side use
    data["google_maps_api_key"] = app.config["GOOGLE_MAPS_API_KEY"]
    data["map_provider"] = app.config.get("MAP_PROVIDER", "leaflet")
    data["dns_security_test_url"] = app.config.get("DNS_SECURITY_TEST_URL", "")

    return render_template("home.html", context=data)


# @app.route("/hostinfo.php")
@app.route("/hostinfo")
def hostinfo():
    """
    Return JSON structure with IP address information.
    """

    # get the request headers
    forwarded_for = request.environ.get("HTTP_X_FORWARDED_FOR", None)
    remote_address = request.environ.get("REMOTE_ADDR", None)

    # build the main data dictionary
    data = {
        "forwarded_for": request.environ.get("HTTP_X_FORWARDED_FOR", ""),
        "remote_address": request.environ.get("REMOTE_ADDR", ""),
        "remote_port": request.environ.get("REMOTE_PORT", ""),
        "request_method": request.environ.get("REQUEST_METHOD", ""),
        "server_protocol": request.environ.get("SERVER_PROTOCOL", ""),
        "user_agent": request.environ.get("HTTP_USER_AGENT", ""),
        "network": "",
        "proxy_detected": None,
    }

    # Check for PROXY usage
    tmp_forwarded_for = os.getenv("FORWARDED_FOR", forwarded_for)
    client_address = get_client_address(remote_address, tmp_forwarded_for)
    data["client_address"] = os.getenv("CLIENT_ADDRESS", client_address)
    app.logger.info(
        f"Hostinfo view from {data['client_address']} with forwarded_for {tmp_forwarded_for}"
    )

    # calculate the IP address basics at the start
    if not data["client_address"]:
        abort(400)
    ip = ipaddress.ip_address(str(data["client_address"]))

    # Check if campus address
    data["is_campus"] = is_campus_ip(data["client_address"])

    # collect device information
    ua = parse(data["user_agent"])
    data["user_device"] = {
        "browser": ua.browser.family,
        "browser_version": ua.browser.version_string,
        "os": ua.os.family,
        "os_version": ua.os.version_string,
        "device_family": ua.device.family if ua.device.family != "Other" else None,
        "device_brand": ua.device.brand,
        "device_model": ua.device.model,
        "is_mobile": ua.is_mobile,
        "is_tablet": ua.is_tablet,
        "is_pc": ua.is_pc,
        "is_bot": ua.is_bot,
    }

    # collect dns data
    reverse_addr = reversename.from_address(data["client_address"])
    try:
        dns_response = resolver.query(reverse_addr, "PTR")
        for val in dns_response:
            app.logger.debug(
                f"PTR {val.to_text()}"
            )  # pylint: disable=logging-fstring-interpolation
            data["ptr"] = val.to_text()
    except dns.exception.DNSException:
        app.logger.warning("reverse DNS lookup failed")

    # collect isp info
    if ip.is_global:
        try:
            iplocation = get_ip_location(data["client_address"])
        except Exception as error:
            app.logger.warning(f"IP location lookup failed: {error}")
            iplocation = {
                "country_code2": None,
                "country_name": "Unknown",
                "ip": str(ip),
                "ip_number": None,
                "ip_version": ip.version,
                "isp": "Unknown",
                "response_code": None,
                "response_message": None,
                "city": None,
                "lat": None,
                "lon": None,
            }

        # ipwhois = getWhoIs( data['client_address'])
        # data['ipwhois'] = ipwhois
    else:
        # non-global addresses get a default location from site config
        site_name = app.config.get("SITE_NAME", "")
        iplocation = {
            "country_code2": app.config.get("SITE_COUNTRY_CODE", ""),
            "country_name": app.config.get("SITE_COUNTRY_NAME", ""),
            "ip": str(ip),
            "ip_number": None,
            "ip_version": ip.version,
            "isp": site_name,
            "org": site_name,
            "asn": None,
            "region": app.config.get("SITE_REGION") or None,
            "response_code": None,
            "response_message": None,
            "city": app.config.get("SITE_CITY", ""),
            "lat": app.config.get("SITE_LAT", 0.0),
            "lon": app.config.get("SITE_LON", 0.0),
            "mobile": False,
            "proxy": False,
            "hosting": False,
        }
    data["iplocation"] = iplocation

    # collect information about the network for this address
    try:
        network = get_network(data["client_address"])
    except Exception as error:
        app.logger.warning(f"Network lookup failed: {error}")
        network = None

    net_details = {
        "cidr": None,
        "comment": "",
        "ip_version": None,
        "netmask": None,
        "prefixlen": None,
        "contact": None,
        "contact_name": None,
        "contact_email": None,
        "contact_dept": None,
        "cost_center": None,
        "purpose": None,
        "router_device": None,
        "dhcp_servers": [],
        "dhcp_routers": None,
        "dhcp_dns_servers": [],
        "dhcp_domain_name": None,
        "dhcp_lease_time": None,
        "dhcp_ntp_servers": [],
        "vlan_id": None,
        "vlan_name": None,
    }
    if network:
        # collect network data to display
        net_details["cidr"] = network.get("network", None)
        net_details["comment"] = network.get("comment", "")

        # calculate the IP address basics
        if net_details["cidr"]:
            ip_net = ipaddress.ip_network(str(net_details["cidr"]))
            net_details["ip_version"] = str(ip_net.version)
            net_details["netmask"] = str(ip_net.netmask)
            net_details["prefixlen"] = str(ip_net.prefixlen)

        # collect specific extattr data
        net_details["contact"] = (
            network.get("extattrs", {}).get("Admin Onyen", {}).get("value", None)
        )
        net_details["contact_name"] = (
            network.get("extattrs", {}).get("Administrator", {}).get("value", None)
        )
        net_details["contact_email"] = (
            network.get("extattrs", {}).get("Admin Email", {}).get("value", None)
        )
        net_details["contact_dept"] = (
            network.get("extattrs", {}).get("Department", {}).get("value", None)
        )
        net_details["cost_center"] = (
            network.get("extattrs", {}).get("Cost Center", {}).get("value", None)
        )
        net_details["purpose"] = (
            network.get("extattrs", {}).get("Purpose", {}).get("value", None)
        )
        net_details["router_device"] = (
            network.get("extattrs", {}).get("Router Device", {}).get("value", None)
        )

        # iterate members to get dhcp servers
        for member in network.get("members", []):
            if net_details["ip_version"] == "4":
                net_details["dhcp_servers"].append(member["ipv4addr"])
            else:
                net_details["dhcp_servers"].append(member["ipv6addr"])

        # iterate dhcp options for specific
        options = network.get("options", [])
        for option in options:
            values = option.get("values", [])
            for value in values:
                if value.get("name", "") == "routers":
                    net_details["dhcp_routers"] = value.get("value", None)
                if value.get("name", "") == "domain-name-servers":
                    server_list = value.get("value", "")
                    net_details["dhcp_dns_servers"] = server_list.split(",")
                if value.get("name", "") == "domain-name":
                    net_details["dhcp_domain_name"] = value.get("value", None)
                if value.get("name", "") == "dhcp-lease-time":
                    net_details["dhcp_lease_time"] = value.get("value", None)
                if value.get("name", "") == "ntp-servers":
                    server_list = value.get("value", "")
                    net_details["dhcp_ntp_servers"] = server_list.split(",")

        # collect vlan data to display
        vlan_list = network.get("vlans", None)
        if vlan_list:
            net_details["vlan_id"] = vlan_list[0].get("id", None)
            net_details["vlan_name"] = vlan_list[0].get("name", None)

    data["network"] = net_details

    # collect details about this address
    addr_details = {
        "comment": "",
        "status": None,
        "mac": None,
        "username": None,
        "dhcp_lease_state": None,
        "names": [],
        "types": [],
        "usage": [],
        "contact": None,
        "contact_name": None,
        "contact_email": None,
        "contact_dept": None,
    }
    # calculate the IP address basics
    addr_details["ip_version"] = ip.version
    addr_details["is_private"] = ip.is_private
    addr_details["is_global"] = ip.is_global
    addr_details["is_link_local"] = ip.is_link_local

    # Find any address objects
    try:
        address_records = get_address_objects(data["client_address"])
    except Exception as error:
        app.logger.warning(f"Address lookup failed: {error}")
        address_records = None

    if address_records:
        addr_details["comment"] = address_records.get("comment", "")
        addr_details["status"] = address_records.get("status", None)
        addr_details["mac"] = address_records.get("mac_address", None)
        addr_details["username"] = address_records.get("username", None)
        addr_details["dhcp_lease_state"] = address_records.get("lease_state", None)
        addr_details["names"] = address_records.get("names", [])
        addr_details["types"] = address_records.get("types", [])
        addr_details["usage"] = address_records.get("usage", [])

        # collect specific extattr data
        addr_details["contact"] = (
            address_records.get("extattrs", {})
            .get("Admin Onyen", {})
            .get("value", None)
        )
        addr_details["contact_name"] = (
            address_records.get("extattrs", {})
            .get("Administrator", {})
            .get("value", None)
        )
        addr_details["contact_email"] = (
            address_records.get("extattrs", {})
            .get("Admin Email", {})
            .get("value", None)
        )
        addr_details["contact_dept"] = (
            address_records.get("extattrs", {}).get("Department", {}).get("value", None)
        )

    data["address_details"] = addr_details

    # collect NAC data to display
    data["nac"] = {}
    if data["is_campus"] and ip.version == 4:
        try:
            nac_data = get_nac_info(data["client_address"], mac=addr_details["mac"])
        except Exception as error:
            app.logger.warning(f"NAC info lookup failed: {error}")
            nac_data = None

        if nac_data:
            data["nac"] = nac_data

    log_metrics_event(
        "hostinfo",
        ip_version=ip.version,
        isp=iplocation.get("isp"),
        org=iplocation.get("org"),
        asn=iplocation.get("asn"),
        city=iplocation.get("city"),
        region=iplocation.get("region"),
        country=iplocation.get("country_name") or iplocation.get("country"),
        country_code=iplocation.get("country_code2"),
        is_campus=data["is_campus"],
        network_purpose=net_details.get("purpose"),
        mobile=iplocation.get("mobile"),
        proxy=iplocation.get("proxy"),
        hosting=iplocation.get("hosting"),
    )

    # build the json response
    message = jsonify(data)
    response = make_response(message)
    return response


@app.route("/health")
@app.route("/about")
def about():
    """Display a basic webpage with about information."""
    return render_template("about.html")


@app.route("/about/")
def about_redirect():
    """Redirect slash variant to canonical about page."""
    return redirect(url_for("about"), code=308)


@app.route("/faq")
def faq():
    """Display a basic webpage with about information."""
    return render_template("faq.html")


@app.route("/faq/")
def faq_redirect():
    """Redirect slash variant to canonical FAQ page."""
    return redirect(url_for("faq"), code=308)


@app.route("/metrics")
def metrics():
    """Display aggregate usage metrics."""
    username = app.config.get("METRICS_USERNAME", "")
    password = app.config.get("METRICS_PASSWORD", "")
    if username and password:
        auth = request.authorization
        if not auth or auth.username != username or auth.password != password:
            return (
                "Unauthorized",
                401,
                {"WWW-Authenticate": 'Basic realm="Metrics"'},
            )
    return render_template(
        "metrics.html",
        metrics=get_metrics_dashboard(),
    )


@app.route("/favicon.ico")
@app.route("/robots.txt")
@app.route("/sitemap.xml")
def static_from_root():
    """Serve root-level static files."""
    return send_from_directory(app.static_folder or APP_ROOT, request.path[1:])


@app.route("/<path:filename>")
def indexnow_key_file(filename):
    """Serve the IndexNow key verification file from config.toml."""
    key = app.config.get("INDEXNOW_KEY", "")
    if key and filename == f"{key}.txt":
        return key, 200, {"Content-Type": "text/plain; charset=utf-8"}
    abort(404)


# Custom handler for 404 Not Found errors
@app.errorhandler(404)
def page_not_found(e):
    # The handler function receives the exception instance
    return render_template("404.html"), 404


# Custom handler for 500 Internal Server Errors
@app.errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500


if app.config.get("TESTING"):

    @app.route("/trigger-500")
    def trigger_500():
        abort(500)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
