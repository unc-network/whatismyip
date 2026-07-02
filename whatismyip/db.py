"""Metrics database — storage and dashboard aggregation."""

import os
import sqlite3
import time
from datetime import datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import current_app

_APP_ROOT = os.path.join(os.path.dirname(__file__), "..")
METRICS_DB_PATH = os.path.join(_APP_ROOT, "data", "metrics.sqlite3")
METRICS_TIMEZONE = ZoneInfo("America/New_York")

_metrics_cache: dict = {"data": None, "ts": 0.0}
_METRICS_CACHE_TTL = 300  # seconds


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
                hosting INTEGER,
                dns_filtering TEXT,
                dns_ip TEXT,
                dns_geo TEXT,
                edns_ip TEXT,
                edns_geo TEXT
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
            ("dns_filtering", "TEXT"),
            ("dns_ip", "TEXT"),
            ("dns_geo", "TEXT"),
            ("edns_ip", "TEXT"),
            ("edns_geo", "TEXT"),
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
    dns_filtering=None,
    dns_ip=None,
    dns_geo=None,
    edns_ip=None,
    edns_geo=None,
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
                    hosting,
                    dns_filtering,
                    dns_ip,
                    dns_geo,
                    edns_ip,
                    edns_geo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    dns_filtering,
                    dns_ip,
                    dns_geo,
                    edns_ip,
                    edns_geo,
                ),
            )
    except Exception as error:  # pragma: no cover - metrics must not break diagnostics
        current_app.logger.warning("Metrics logging skipped: %s", error)


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
    if _metrics_cache["data"] is not None and (
        time.monotonic() - _metrics_cache["ts"] < _METRICS_CACHE_TTL
    ):
        return _metrics_cache["data"]
    if days is None:
        days = current_app.config["METRICS_TIME_WINDOW_DAYS"]

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

        dns_filtering_breakdown = _with_percentages(
            _count_by_query(
                conn,
                """
                SELECT CASE dns_filtering
                         WHEN 'active'       THEN 'Active'
                         WHEN 'inactive'     THEN 'Inactive'
                         WHEN 'inconclusive' THEN 'Unable to verify'
                         ELSE 'Unknown'
                       END AS label,
                       COUNT(*) AS count
                FROM metrics_events
                WHERE event_type = ? AND dns_filtering IS NOT NULL
                GROUP BY dns_filtering
                ORDER BY count DESC
                """,
                ("dns_result",),
            )
        )

        dns_geo_breakdown = _with_percentages(
            _count_by_query(
                conn,
                """
                SELECT COALESCE(NULLIF(TRIM(dns_geo), ''), 'Unknown') AS label, COUNT(*) AS count
                FROM metrics_events
                WHERE event_type = ? AND dns_geo IS NOT NULL
                GROUP BY label
                ORDER BY count DESC
                LIMIT 8
                """,
                ("dns_result",),
            )
        )

    result = {
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
        "dns_filtering_breakdown": dns_filtering_breakdown,
        "dns_geo_breakdown": dns_geo_breakdown,
    }
    _metrics_cache["data"] = result
    _metrics_cache["ts"] = time.monotonic()
    return result
