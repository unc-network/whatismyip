"""Metrics database — storage and dashboard aggregation."""

import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from datetime import time as dt_time
from typing import Any
from zoneinfo import ZoneInfo

from flask import current_app

_DEFAULT_METRICS_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "metrics.sqlite3"
)
METRICS_TIMEZONE = ZoneInfo("America/New_York")

_metrics_cache: dict = {"data": None, "ts": 0.0}
_METRICS_CACHE_TTL = 1800  # seconds — complete-day data is stable until midnight


def _db_path() -> str:
    return current_app.config.get("METRICS_DB_PATH", _DEFAULT_METRICS_DB_PATH)


def ensure_metrics_store() -> None:
    """Create the metrics database and schema when needed."""
    path = _db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with sqlite3.connect(path) as conn:
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS page_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                page TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_page_views_created_at ON page_views(created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_page_views_page ON page_views(page)"
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
    event_type: str,
    ip_version: int | None = None,
    isp: str | None = None,
    org: str | None = None,
    asn: str | None = None,
    city: str | None = None,
    region: str | None = None,
    country: str | None = None,
    country_code: str | None = None,
    is_campus: bool | None = None,
    network_purpose: str | None = None,
    mobile: bool | None = None,
    proxy: bool | None = None,
    hosting: bool | None = None,
    dns_filtering: str | None = None,
    dns_ip: str | None = None,
    dns_geo: str | None = None,
    edns_ip: str | None = None,
    edns_geo: str | None = None,
) -> None:
    """Store a single aggregate metrics event without persisting raw IP addresses."""
    try:
        ensure_metrics_store()
        with sqlite3.connect(_db_path()) as conn:
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


def log_page_view(page: str) -> None:
    """Record a page view for the given page name."""
    try:
        ensure_metrics_store()
        with sqlite3.connect(_db_path()) as conn:
            conn.execute(
                "INSERT INTO page_views (created_at, page) VALUES (?, ?)",
                (datetime.now(timezone.utc).isoformat(), page),
            )
    except Exception as error:  # pragma: no cover - metrics must not break page loads
        current_app.logger.warning("Page view logging skipped: %s", error)


def _count_by_query(
    conn: sqlite3.Connection, query: str, params: tuple = ()
) -> list[dict[str, Any]]:
    """Return a list of dictionaries from a grouped count query."""
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def _with_percentages(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add percentage values to grouped rows."""
    total = sum(row["count"] for row in rows)
    result = []
    for row in rows:
        percentage = round((row["count"] / total) * 100, 1) if total else 0
        result.append({**row, "percentage": percentage})
    return result


def get_metrics_dashboard(days: int | None = None) -> dict[str, Any]:
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
    last_full_day = today - timedelta(days=1)
    first_day = last_full_day - timedelta(days=days - 1)
    cutoff = (
        datetime.combine(first_day, dt_time.min, tzinfo=METRICS_TIMEZONE)
        .astimezone(timezone.utc)
        .isoformat()
    )

    with sqlite3.connect(_db_path()) as conn:
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

        daily_lookup_v4: dict[str, int] = {}
        daily_lookup_v6: dict[str, int] = {}
        for row in conn.execute(
            """
            SELECT created_at, ip_version
            FROM metrics_events
            WHERE event_type = ? AND created_at >= ?
            ORDER BY created_at
            """,
            ("hostinfo", cutoff),
        ).fetchall():
            day = (
                datetime.fromisoformat(row["created_at"])
                .astimezone(METRICS_TIMEZONE)
                .date()
                .isoformat()
            )
            if row["ip_version"] == 6:
                daily_lookup_v6[day] = daily_lookup_v6.get(day, 0) + 1
            else:
                daily_lookup_v4[day] = daily_lookup_v4.get(day, 0) + 1

        daily_series = []
        for offset in range(days):
            day = (last_full_day - timedelta(days=days - 1 - offset)).isoformat()
            v4 = daily_lookup_v4.get(day, 0)
            v6 = daily_lookup_v6.get(day, 0)
            daily_series.append({"day": day, "count": v4 + v6, "v4": v4, "v6": v6})
        daily_max = max((row["count"] for row in daily_series), default=0) or 1

        daily_page_view_lookup: dict[str, int] = {}
        for row in conn.execute(
            """
            SELECT created_at
            FROM page_views
            WHERE created_at >= ?
            ORDER BY created_at
            """,
            (cutoff,),
        ).fetchall():
            day = (
                datetime.fromisoformat(row["created_at"])
                .astimezone(METRICS_TIMEZONE)
                .date()
                .isoformat()
            )
            daily_page_view_lookup[day] = daily_page_view_lookup.get(day, 0) + 1

        daily_page_views_series = [
            {
                "day": (last_full_day - timedelta(days=days - 1 - offset)).isoformat(),
                "count": daily_page_view_lookup.get(
                    (last_full_day - timedelta(days=days - 1 - offset)).isoformat(), 0
                ),
            }
            for offset in range(days)
        ]

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

        page_view_breakdown = _with_percentages(
            _count_by_query(
                conn,
                """
                SELECT page AS label, COUNT(*) AS count
                FROM page_views
                GROUP BY page
                ORDER BY count DESC
                """,
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
        "page_view_breakdown": page_view_breakdown,
        "daily_page_views_series": daily_page_views_series,
    }
    _metrics_cache["data"] = result
    _metrics_cache["ts"] = time.monotonic()
    return result
