"""Metrics database — storage and dashboard aggregation."""

import os
import sqlite3
import threading
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

# The one-time index migration in ensure_metrics_store holds an exclusive lock for
# as long as it takes to rebuild the composite index — a full scan of the events
# table on PVC-backed storage. Other gunicorn workers starting at the same moment
# must wait that out rather than fail with "database is locked", so schema and
# dashboard connections get a far longer busy timeout than sqlite3's 5 s default.
# The per-event write paths deliberately keep the short default: a blocked metrics
# insert should be dropped, not stall the request that triggered it.
_SCHEMA_LOCK_TIMEOUT = 120.0
_DASHBOARD_LOCK_TIMEOUT = 30.0

_metrics_cache: dict = {"data": None, "ts": 0.0}
_METRICS_CACHE_TTL = 1800  # seconds — complete-day data is stable until midnight
_schema_initialized_for: str | None = None  # db path last initialized; None = never
# Serializes first-run schema setup across threads. Without it, every thread that
# arrives during the one-time index migration piles onto SQLite's write lock and then
# redundantly repeats the DDL and the retention DELETE once it gets through. One
# thread does the work; the rest wait on this and return immediately.
_schema_lock = threading.Lock()


def _db_path() -> str:
    return current_app.config.get("METRICS_DB_PATH", _DEFAULT_METRICS_DB_PATH)


def ensure_metrics_store() -> None:
    """Create the metrics database and schema when needed.

    Runs at most once per process lifetime — subsequent calls return immediately.
    On network-mounted storage (OpenShift PVC) the DDL round-trips are expensive,
    so skipping them after the first successful run is a meaningful speedup.
    """
    global _schema_initialized_for
    path = _db_path()
    if _schema_initialized_for == path:
        return
    with _schema_lock:
        if _schema_initialized_for == path:  # another thread finished while we waited
            return
        _init_metrics_store(path)
        _schema_initialized_for = path


def _init_metrics_store(path: str) -> None:
    """Create the schema, migrate indexes, and apply retention. Caller holds the lock."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with sqlite3.connect(path, timeout=_SCHEMA_LOCK_TIMEOUT) as conn:
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
                edns_geo TEXT,
                dns_lookup_outcome TEXT
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
            ("dns_lookup_outcome", "TEXT"),
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

        # Every dashboard query filters on event_type plus a created_at window, so one
        # composite index serves all of them, most as covering scans. The older
        # single-column indexes were never chosen by the planner — it fell back to a
        # temp B-tree for each GROUP BY regardless — while costing ~99 MB of file size
        # and a B-tree write per insert, so drop them wherever they still exist.
        # Drop before create so the new index builds into pages the old ones freed,
        # rather than growing the file by its own size first and only then releasing
        # theirs — that ordering matters on a space-constrained PVC.
        obsolete_indexes = [
            "idx_metrics_events_created_at",
            "idx_metrics_events_event_type",
            "idx_metrics_events_ip_version",
            "idx_metrics_events_isp",
            "idx_metrics_events_org",
            "idx_metrics_events_country",
            "idx_metrics_events_country_code",
            "idx_metrics_events_city",
            "idx_page_views_page",
        ]
        existing = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        # Report the one-time rebuild, which dominates startup the first time a
        # pre-1.11.5 database is opened and is otherwise invisible in the logs.
        migrating = bool(existing.intersection(obsolete_indexes)) or (
            "idx_metrics_events_type_created" not in existing
        )
        if migrating:
            current_app.logger.info(
                "Metrics index migration starting (%d obsolete indexes to drop)",
                len(existing.intersection(obsolete_indexes)),
            )
        started = time.monotonic()

        for obsolete in obsolete_indexes:
            conn.execute(f"DROP INDEX IF EXISTS {obsolete}")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_events_type_created "
            "ON metrics_events(event_type, created_at)"
        )

        if migrating:
            current_app.logger.info(
                "Metrics index migration complete in %.1fs",
                time.monotonic() - started,
            )

    retention_days = current_app.config.get("METRICS_RETENTION_DAYS", 90)
    retention_cutoff = (
        datetime.now(timezone.utc) - timedelta(days=retention_days)
    ).isoformat()
    with sqlite3.connect(path, timeout=_SCHEMA_LOCK_TIMEOUT) as conn:
        conn.execute(
            "DELETE FROM metrics_events WHERE created_at < ?", (retention_cutoff,)
        )
        conn.execute("DELETE FROM page_views WHERE created_at < ?", (retention_cutoff,))


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
    dns_lookup_outcome: str | None = None,
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
                    edns_geo,
                    dns_lookup_outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    dns_lookup_outcome,
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


def _local_day(utc_hour: str) -> str:
    """Convert a 'YYYY-MM-DDTHH' UTC bucket key to a local-timezone date string."""
    return (
        datetime.fromisoformat(f"{utc_hour}:00:00+00:00")
        .astimezone(METRICS_TIMEZONE)
        .date()
        .isoformat()
    )


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
    if _metrics_cache["data"] is not None and (
        time.monotonic() - _metrics_cache["ts"] < _METRICS_CACHE_TTL
    ):
        return _metrics_cache["data"]
    ensure_metrics_store()
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

    # Query the file directly, read-only. An earlier revision snapshotted the whole
    # database into :memory: to collapse PVC round-trips, but that cost is linear in
    # total file size rather than in the window being shown: at 367 MB it read every
    # byte and peaked near 500 MB RSS per worker to render one page, and it held a
    # shared lock across the copy, stalling concurrent metrics writes.
    # idx_metrics_events_type_created lets each query touch only its slice instead.
    conn = sqlite3.connect(
        f"file:{_db_path()}?mode=ro", uri=True, timeout=_DASHBOARD_LOCK_TIMEOUT
    )
    conn.row_factory = sqlite3.Row

    try:
        totals_row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN is_campus = 1 THEN 1 ELSE 0 END) AS campus,
                SUM(CASE WHEN is_campus = 0 THEN 1 ELSE 0 END) AS remote
            FROM metrics_events
            WHERE event_type = ? AND created_at >= ?
            """,
            ("hostinfo", cutoff),
        ).fetchone()
        total_hostinfo = totals_row["total"]
        total_campus = totals_row["campus"]
        total_remote = totals_row["remote"]

        # Bucket by UTC hour in SQL, then convert at most 24 * days buckets to local
        # dates in Python. US DST transitions land on whole hours, so this is exactly
        # as accurate as converting every row, at a fraction of the Python work.
        daily_lookup_v4: dict[str, int] = {}
        daily_lookup_v6: dict[str, int] = {}
        for row in conn.execute(
            """
            SELECT substr(created_at, 1, 13) AS hour,
                   CASE WHEN ip_version = 6 THEN 6 ELSE 4 END AS version,
                   COUNT(*) AS count
            FROM metrics_events
            WHERE event_type = ? AND created_at >= ?
            GROUP BY hour, version
            """,
            ("hostinfo", cutoff),
        ).fetchall():
            day = _local_day(row["hour"])
            bucket = daily_lookup_v6 if row["version"] == 6 else daily_lookup_v4
            bucket[day] = bucket.get(day, 0) + row["count"]

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
            SELECT substr(created_at, 1, 13) AS hour, COUNT(*) AS count
            FROM page_views
            WHERE created_at >= ?
            GROUP BY hour
            """,
            (cutoff,),
        ).fetchall():
            day = _local_day(row["hour"])
            daily_page_view_lookup[day] = (
                daily_page_view_lookup.get(day, 0) + row["count"]
            )

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
                WHERE event_type = ? AND created_at >= ?
                GROUP BY label
                ORDER BY count DESC
                """,
                ("hostinfo", cutoff),
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
                WHERE event_type = ? AND created_at >= ?
                GROUP BY label
                ORDER BY count DESC
                LIMIT 10
                """,
                ("hostinfo", cutoff),
            )
        )

        org_breakdown = _with_percentages(
            _count_by_query(
                conn,
                """
                SELECT COALESCE(NULLIF(TRIM(org), ''), 'Unknown') AS label, COUNT(*) AS count
                FROM metrics_events
                WHERE event_type = ? AND created_at >= ?
                GROUP BY label
                ORDER BY count DESC
                LIMIT 10
                """,
                ("hostinfo", cutoff),
            )
        )

        country_breakdown = _with_percentages(
            _count_by_query(
                conn,
                """
                SELECT COALESCE(NULLIF(TRIM(country), ''), 'Unknown') AS label, COUNT(*) AS count
                FROM metrics_events
                WHERE event_type = ? AND created_at >= ?
                GROUP BY label
                ORDER BY count DESC
                LIMIT 10
                """,
                ("hostinfo", cutoff),
            )
        )

        campus_breakdown = _with_percentages(
            _count_by_query(
                conn,
                """
                SELECT CASE WHEN is_campus = 1 THEN 'Campus' ELSE 'Off campus' END AS label,
                       COUNT(*) AS count
                FROM metrics_events
                WHERE event_type = ? AND created_at >= ?
                GROUP BY label
                ORDER BY count DESC
                """,
                ("hostinfo", cutoff),
            )
        )

        purpose_breakdown = _with_percentages(
            _count_by_query(
                conn,
                """
                SELECT COALESCE(NULLIF(TRIM(network_purpose), ''), 'Unknown') AS label, COUNT(*) AS count
                FROM metrics_events
                WHERE event_type = ? AND is_campus = 1 AND created_at >= ?
                GROUP BY label
                ORDER BY count DESC
                LIMIT 10
                """,
                ("hostinfo", cutoff),
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
                WHERE event_type = ? AND is_campus = 1
                      AND dns_filtering IS NOT NULL AND created_at >= ?
                GROUP BY dns_filtering
                ORDER BY count DESC
                """,
                ("dns_result", cutoff),
            )
        )

        dns_geo_breakdown = _with_percentages(
            _count_by_query(
                conn,
                """
                SELECT COALESCE(NULLIF(TRIM(dns_geo), ''), 'Unknown') AS label, COUNT(*) AS count
                FROM metrics_events
                WHERE event_type = ? AND dns_geo IS NOT NULL AND created_at >= ?
                GROUP BY label
                ORDER BY count DESC
                LIMIT 8
                """,
                ("dns_result", cutoff),
            )
        )

        # Build all DNS lookup cards from one scan of the in-memory snapshot.
        dns_lookup_groups = _count_by_query(
            conn,
            """
            SELECT is_campus, dns_lookup_outcome, COUNT(*) AS count
            FROM metrics_events
            WHERE event_type = ? AND created_at >= ?
            GROUP BY is_campus, dns_lookup_outcome
            """,
            ("dns_lookup", cutoff),
        )
        total_dns_lookups = sum(row["count"] for row in dns_lookup_groups)

        origin_labels = {1: "On campus", 0: "Off campus"}
        outcome_labels = {
            "matching": "Matching answers",
            "different": "Different answers",
            "public_only": "Public view only",
            "incomplete": "Incomplete or unavailable",
        }
        origin_counts: dict[str, int] = {}
        outcome_counts: dict[str, int] = {}
        for row in dns_lookup_groups:
            origin = origin_labels.get(row["is_campus"], "Unknown")
            outcome = outcome_labels.get(row["dns_lookup_outcome"], "Unknown")
            origin_counts[origin] = origin_counts.get(origin, 0) + row["count"]
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + row["count"]

        dns_lookup_origin_breakdown = _with_percentages(
            [
                {"label": label, "count": count}
                for label, count in sorted(
                    origin_counts.items(), key=lambda item: (-item[1], item[0])
                )
            ]
        )
        dns_lookup_outcome_breakdown = _with_percentages(
            [
                {"label": label, "count": count}
                for label, count in sorted(
                    outcome_counts.items(), key=lambda item: (-item[1], item[0])
                )
            ]
        )

        page_view_breakdown = _with_percentages(
            _count_by_query(
                conn,
                """
                SELECT page AS label, COUNT(*) AS count
                FROM page_views
                WHERE created_at >= ?
                GROUP BY page
                ORDER BY count DESC
                """,
                (cutoff,),
            )
        )

    finally:
        conn.close()

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
        "total_dns_lookups": total_dns_lookups,
        "dns_lookup_origin_breakdown": dns_lookup_origin_breakdown,
        "dns_lookup_outcome_breakdown": dns_lookup_outcome_breakdown,
        "page_view_breakdown": page_view_breakdown,
        "daily_page_views_series": daily_page_views_series,
    }
    _metrics_cache["data"] = result
    _metrics_cache["ts"] = time.monotonic()
    return result
