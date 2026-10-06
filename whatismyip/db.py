"""Metrics database — storage and dashboard aggregation."""

import os
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta, timezone
from datetime import time as dt_time
from typing import Any, NamedTuple
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
        schedule_daily_maintenance()
        return
    with _schema_lock:
        if _schema_initialized_for == path:  # another thread finished while we waited
            return
        _init_metrics_store(path)
        _schema_initialized_for = path
    schedule_daily_maintenance()


def _init_metrics_store(path: str) -> None:
    """Create the schema and migrate indexes. Caller holds the lock."""
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

        # Pre-aggregated per-day counts. The dashboard sums these instead of
        # re-scanning the raw events on every cold build, which is the difference
        # between reading a few thousand rows and a few hundred thousand.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics_daily (
                day TEXT NOT NULL,
                event_type TEXT NOT NULL,
                dim TEXT NOT NULL,
                val TEXT NOT NULL,
                n INTEGER NOT NULL,
                PRIMARY KEY (day, event_type, dim, val)
            ) WITHOUT ROWID
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_daily_dim ON metrics_daily(dim, day)"
        )
        # A day is listed here once it has been rolled up, including days with no
        # traffic at all — otherwise an empty day would be retried forever.
        conn.execute(
            "CREATE TABLE IF NOT EXISTS metrics_daily_done (day TEXT PRIMARY KEY)"
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


# Each entry is (event_type, dim, SQL expression for the bucket value, extra WHERE).
# The expressions normalise exactly as the dashboard used to at read time, so a
# rolled-up value and a live one are always spelled the same way and can be summed
# together. Raw column values are stored where the dashboard applies its own
# labelling later, so relabelling never requires rebuilding history.
_ROLLUP_SPECS: list[tuple[str, str, str, str]] = [
    ("hostinfo", "is_campus", "COALESCE(CAST(is_campus AS TEXT), 'null')", ""),
    ("hostinfo", "ip_version", "COALESCE(CAST(ip_version AS TEXT), 'Unknown')", ""),
    ("hostinfo", "isp", "COALESCE(NULLIF(TRIM(isp), ''), 'Unknown')", ""),
    ("hostinfo", "org", "COALESCE(NULLIF(TRIM(org), ''), 'Unknown')", ""),
    ("hostinfo", "country", "COALESCE(NULLIF(TRIM(country), ''), 'Unknown')", ""),
    (
        "hostinfo",
        "purpose",
        "COALESCE(NULLIF(TRIM(network_purpose), ''), 'Unknown')",
        "AND is_campus = 1",
    ),
    (
        "dns_result",
        "dns_filtering",
        "dns_filtering",
        "AND is_campus = 1 AND dns_filtering IS NOT NULL",
    ),
    (
        "dns_result",
        "dns_geo",
        "COALESCE(NULLIF(TRIM(dns_geo), ''), 'Unknown')",
        "AND dns_geo IS NOT NULL",
    ),
    ("dns_lookup", "lookup_origin", "COALESCE(CAST(is_campus AS TEXT), 'null')", ""),
    ("dns_lookup", "lookup_outcome", "COALESCE(dns_lookup_outcome, 'null')", ""),
]

# Days rolled up per catch-up pass. Bounds how long one pass can run when a fresh
# deployment has months of history to fold in; later passes finish the rest.
_ROLLUP_MAX_DAYS_PER_PASS = 7


class MaintenanceResult(NamedTuple):
    """What one maintenance pass did, for logging and tests."""

    days: int
    events_pruned: int
    page_views_pruned: int


_rollup_lock = threading.Lock()
_rollup_thread_running = False
# How often the pending-day check may touch the database. The check itself is a
# single indexed read, but it sits on the write path for every recorded event, so
# it is gated rather than run per request.
_MAINTENANCE_CHECK_INTERVAL = 900.0
_last_maintenance_check = 0.0


def _day_bounds_utc(day: str) -> tuple[str, str]:
    """Return the UTC ISO bounds [start, end) of one local calendar day."""
    start = datetime.combine(
        date.fromisoformat(day), dt_time.min, tzinfo=METRICS_TIMEZONE
    )
    return (
        start.astimezone(timezone.utc).isoformat(),
        (start + timedelta(days=1)).astimezone(timezone.utc).isoformat(),
    )


def _rollup_one_day(conn: sqlite3.Connection, day: str) -> None:
    """Fold one complete local day of raw rows into metrics_daily."""
    start_utc, end_utc = _day_bounds_utc(day)
    conn.execute("DELETE FROM metrics_daily WHERE day = ?", (day,))
    for event_type, dim, expr, extra in _ROLLUP_SPECS:
        # expr and extra are literals from _ROLLUP_SPECS above, never request data.
        # They are interpolated rather than written out per dimension so that this
        # query and the live one in _merge_counts bucket values through the exact
        # same expression — if the two ever spelled a value differently, rolled-up
        # and live counts for the same bucket would stop adding together.
        sql = f"""
            INSERT INTO metrics_daily (day, event_type, dim, val, n)
            SELECT ?, ?, ?, {expr}, COUNT(*)
            FROM metrics_events
            WHERE event_type = ? AND created_at >= ? AND created_at < ? {extra}
            GROUP BY {expr}
        """  # nosec B608 - interpolated values are module constants, not user input
        conn.execute(sql, (day, event_type, dim, event_type, start_utc, end_utc))
    conn.execute(
        """
        INSERT INTO metrics_daily (day, event_type, dim, val, n)
        SELECT ?, 'page_view', 'page', page, COUNT(*)
        FROM page_views
        WHERE created_at >= ? AND created_at < ?
        GROUP BY page
        """,
        (day, start_utc, end_utc),
    )
    conn.execute("INSERT OR REPLACE INTO metrics_daily_done (day) VALUES (?)", (day,))


def _pending_rollup_days(conn: sqlite3.Connection, retention_days: int) -> list[str]:
    """Complete local days inside retention that have not been rolled up yet."""
    today = datetime.now(METRICS_TIMEZONE).date()
    oldest = today - timedelta(days=retention_days)
    last_done = conn.execute("SELECT MAX(day) FROM metrics_daily_done").fetchone()[0]
    start = (
        max(oldest, date.fromisoformat(last_done) + timedelta(days=1))
        if last_done
        else oldest
    )
    end = today - timedelta(days=1)  # yesterday: the newest complete day
    days = []
    current = start
    while current <= end and len(days) < _ROLLUP_MAX_DAYS_PER_PASS:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def run_daily_maintenance() -> MaintenanceResult:
    """Roll up every outstanding complete day, then drop data past retention.

    Rolling up a day touches only that day's rows — roughly a fortieth of what the
    dashboard used to scan — so this stays cheap even on a CPU-constrained pod. It
    catches up fully rather than a batch at a time: the caller is a background
    thread, so nothing waits on it, and leaving a backlog half-done would mean the
    dashboard keeps falling back to live queries for the missing days. Days with no
    traffic cost almost nothing, which matters on a fresh deployment where the whole
    retention window is outstanding.

    Retention lives here rather than at startup because these containers run for
    weeks at a time, and a prune that only happens on boot never happens.
    """
    path = _db_path()
    retention_days = current_app.config.get("METRICS_RETENTION_DAYS", 90)
    rolled = 0
    with sqlite3.connect(path, timeout=_SCHEMA_LOCK_TIMEOUT) as conn:
        while True:
            pending = _pending_rollup_days(conn, retention_days)
            if not pending:
                break
            for day in pending:
                _rollup_one_day(conn, day)
                rolled += 1
            conn.commit()  # bound each transaction to one batch
        cutoff_day = (
            datetime.now(METRICS_TIMEZONE).date() - timedelta(days=retention_days)
        ).isoformat()
        cutoff_utc = _day_bounds_utc(cutoff_day)[0]
        events_pruned = conn.execute(
            "DELETE FROM metrics_events WHERE created_at < ?", (cutoff_utc,)
        ).rowcount
        views_pruned = conn.execute(
            "DELETE FROM page_views WHERE created_at < ?", (cutoff_utc,)
        ).rowcount
        conn.execute("DELETE FROM metrics_daily WHERE day < ?", (cutoff_day,))
        conn.execute("DELETE FROM metrics_daily_done WHERE day < ?", (cutoff_day,))
    return MaintenanceResult(rolled, max(events_pruned, 0), max(views_pruned, 0))


def _maintenance_due() -> bool:
    """True when at least one complete day is still missing from the rollups."""
    try:
        with sqlite3.connect(f"file:{_db_path()}?mode=ro", uri=True) as conn:
            retention_days = current_app.config.get("METRICS_RETENTION_DAYS", 90)
            return bool(_pending_rollup_days(conn, retention_days))
    except Exception:
        return False


def schedule_daily_maintenance() -> None:
    """Start a one-shot thread to catch the rollups up, if work is pending.

    Deliberately not a resident daemon: it is spawned only when a day is actually
    missing, does the work, and exits. Requests never wait on it, so no visitor
    pays for the rollup the way one would if this ran inline.
    """
    global _rollup_thread_running, _last_maintenance_check
    now = time.monotonic()
    with _rollup_lock:
        if _rollup_thread_running:
            return
        if now - _last_maintenance_check < _MAINTENANCE_CHECK_INTERVAL:
            return
        _last_maintenance_check = now
        if not _maintenance_due():
            return
        _rollup_thread_running = True
    app = current_app._get_current_object()  # type: ignore[attr-defined]

    def _worker() -> None:
        global _rollup_thread_running
        try:
            with app.app_context():
                started = time.monotonic()
                result = run_daily_maintenance()
                if result.days or result.events_pruned or result.page_views_pruned:
                    # Report the prune as well as the rollup. Retention silently not
                    # running was the bug this pass exists to fix, so a line that
                    # only mentions the rollup would leave the half that regressed
                    # just as invisible as before.
                    app.logger.info(
                        "Metrics maintenance: rolled up %d day(s) in %.1fs; "
                        "retention pruned %s event(s) and %s page view(s)",
                        result.days,
                        time.monotonic() - started,
                        f"{result.events_pruned:,}",
                        f"{result.page_views_pruned:,}",
                    )
        except (
            Exception
        ) as error:  # pragma: no cover - maintenance must not break the app
            app.logger.warning("Metrics rollup skipped: %s", error)
        finally:
            with _rollup_lock:
                _rollup_thread_running = False

    threading.Thread(target=_worker, name="metrics-rollup", daemon=True).start()


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


def _merge_counts(
    conn: sqlite3.Connection,
    dim: str,
    event_type: str,
    rollup_from: str,
    rollup_to: str | None,
    live_from: str | None,
) -> dict[str, int]:
    """Counts per bucket value for one dimension, from rollups plus live rows.

    Rolled-up days and not-yet-rolled days are summed together, so the figures are
    the same whether or not the rollup has caught up. The live half covers today
    always, and any backlog while a fresh deployment folds in its history.
    """
    counts: dict[str, int] = {}
    if rollup_to is not None and rollup_to >= rollup_from:
        for val, n in conn.execute(
            """
            SELECT val, SUM(n) FROM metrics_daily
            WHERE dim = ? AND event_type = ? AND day >= ? AND day <= ?
            GROUP BY val
            """,
            (dim, event_type, rollup_from, rollup_to),
        ):
            counts[val] = counts.get(val, 0) + n
    if live_from is not None:
        expr, extra = next(
            (e, x) for et, d, e, x in _ROLLUP_SPECS if d == dim and et == event_type
        )
        # Same reasoning as _rollup_one_day: expr/extra come from _ROLLUP_SPECS, and
        # sharing them is what keeps live buckets spelled like rolled-up ones.
        sql = f"""
            SELECT {expr}, COUNT(*) FROM metrics_events
            WHERE event_type = ? AND created_at >= ? {extra}
            GROUP BY {expr}
        """  # nosec B608 - interpolated values are module constants, not user input
        for val, n in conn.execute(sql, (event_type, live_from)):
            counts[val] = counts.get(val, 0) + n
    return counts


def _ranked(
    counts: dict[str, int],
    labels: dict[str, str] | None = None,
    limit: int | None = None,
    merge_into: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Order buckets by count then name, relabel, and attach percentages."""
    if merge_into:
        folded: dict[str, int] = {}
        for val, n in counts.items():
            folded[merge_into.get(val, val)] = (
                folded.get(merge_into.get(val, val), 0) + n
            )
        counts = folded
    rows = [
        {"label": labels.get(val, val) if labels else val, "count": n}
        for val, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    if limit is not None:
        rows = rows[:limit]
    return _with_percentages(rows)


def get_metrics_dashboard(days: int | None = None) -> dict[str, Any]:
    """Build the metrics summary data for the admin dashboard."""
    if _metrics_cache["data"] is not None and (
        time.monotonic() - _metrics_cache["ts"] < _METRICS_CACHE_TTL
    ):
        return _metrics_cache["data"]
    ensure_metrics_store()
    if days is None:
        days = current_app.config["METRICS_TIME_WINDOW_DAYS"]

    today = datetime.now(METRICS_TIMEZONE).date()
    last_full_day = today - timedelta(days=1)
    first_day = last_full_day - timedelta(days=days - 1)
    cutoff = _day_bounds_utc(first_day.isoformat())[0]

    conn = sqlite3.connect(
        f"file:{_db_path()}?mode=ro", uri=True, timeout=_DASHBOARD_LOCK_TIMEOUT
    )
    conn.row_factory = sqlite3.Row

    try:
        # Split the window: whole days that are already rolled up are read from
        # metrics_daily, everything after that — today, plus any backlog — is read
        # from the raw events. When nothing is rolled up yet this degrades to the
        # original all-live behaviour rather than reporting short.
        last_done = conn.execute(
            "SELECT MAX(day) FROM metrics_daily_done WHERE day >= ?",
            (first_day.isoformat(),),
        ).fetchone()[0]
        rollup_from = first_day.isoformat()
        rollup_to = min(last_done, last_full_day.isoformat()) if last_done else None
        if rollup_to is not None:
            live_from = _day_bounds_utc(
                (date.fromisoformat(rollup_to) + timedelta(days=1)).isoformat()
            )[0]
        else:
            live_from = cutoff

        def counts(dim: str, event_type: str = "hostinfo") -> dict[str, int]:
            return _merge_counts(
                conn, dim, event_type, rollup_from, rollup_to, live_from
            )

        campus_counts = counts("is_campus")
        total_hostinfo = sum(campus_counts.values())
        total_campus = campus_counts.get("1", 0)
        total_remote = campus_counts.get("0", 0)

        # Per-day series: rolled days come straight out of metrics_daily; the live
        # remainder is bucketed by UTC hour and converted, since DST transitions
        # fall on whole hours.
        daily_v4: dict[str, int] = {}
        daily_v6: dict[str, int] = {}
        if rollup_to is not None:
            for day, val, n in conn.execute(
                """
                SELECT day, val, SUM(n) FROM metrics_daily
                WHERE dim = 'ip_version' AND event_type = 'hostinfo'
                      AND day >= ? AND day <= ?
                GROUP BY day, val
                """,
                (rollup_from, rollup_to),
            ):
                target = daily_v6 if val == "6" else daily_v4
                target[day] = target.get(day, 0) + n
        for hour, version, n in conn.execute(
            """
            SELECT substr(created_at, 1, 13),
                   CASE WHEN ip_version = 6 THEN 6 ELSE 4 END,
                   COUNT(*)
            FROM metrics_events
            WHERE event_type = 'hostinfo' AND created_at >= ?
            GROUP BY 1, 2
            """,
            (live_from,),
        ):
            day = _local_day(hour)
            target = daily_v6 if version == 6 else daily_v4
            target[day] = target.get(day, 0) + n

        daily_series = []
        for offset in range(days):
            day = (last_full_day - timedelta(days=days - 1 - offset)).isoformat()
            v4 = daily_v4.get(day, 0)
            v6 = daily_v6.get(day, 0)
            daily_series.append({"day": day, "count": v4 + v6, "v4": v4, "v6": v6})
        daily_max = max((row["count"] for row in daily_series), default=0) or 1

        daily_page_views: dict[str, int] = {}
        if rollup_to is not None:
            for day, n in conn.execute(
                """
                SELECT day, SUM(n) FROM metrics_daily
                WHERE dim = 'page' AND event_type = 'page_view'
                      AND day >= ? AND day <= ?
                GROUP BY day
                """,
                (rollup_from, rollup_to),
            ):
                daily_page_views[day] = daily_page_views.get(day, 0) + n
        for hour, n in conn.execute(
            "SELECT substr(created_at, 1, 13), COUNT(*) FROM page_views "
            "WHERE created_at >= ? GROUP BY 1",
            (live_from,),
        ):
            day = _local_day(hour)
            daily_page_views[day] = daily_page_views.get(day, 0) + n

        daily_page_views_series = [
            {
                "day": (last_full_day - timedelta(days=days - 1 - offset)).isoformat(),
                "count": daily_page_views.get(
                    (last_full_day - timedelta(days=days - 1 - offset)).isoformat(), 0
                ),
            }
            for offset in range(days)
        ]

        ip_versions = _ranked(counts("ip_version"), labels={"4": "IPv4", "6": "IPv6"})
        isp_breakdown = _ranked(counts("isp"), limit=10)
        org_breakdown = _ranked(counts("org"), limit=10)
        country_breakdown = _ranked(counts("country"), limit=10)
        purpose_breakdown = _ranked(counts("purpose"), limit=10)
        campus_breakdown = _ranked(
            campus_counts,
            labels={"1": "Campus", "0": "Off campus"},
            merge_into={"null": "0"},
        )

        dns_filtering_breakdown = _ranked(
            counts("dns_filtering", "dns_result"),
            labels={
                "active": "Active",
                "inactive": "Inactive",
                "inconclusive": "Unable to verify",
            },
        )
        dns_geo_breakdown = _ranked(counts("dns_geo", "dns_result"), limit=8)

        origin_counts = counts("lookup_origin", "dns_lookup")
        outcome_counts = counts("lookup_outcome", "dns_lookup")
        total_dns_lookups = sum(origin_counts.values())
        dns_lookup_origin_breakdown = _ranked(
            origin_counts,
            labels={"1": "On campus", "0": "Off campus", "null": "Unknown"},
        )
        dns_lookup_outcome_breakdown = _ranked(
            outcome_counts,
            labels={
                "matching": "Matching answers",
                "different": "Different answers",
                "public_only": "Public view only",
                "incomplete": "Incomplete or unavailable",
                "null": "Unknown",
            },
        )

        page_counts: dict[str, int] = {}
        if rollup_to is not None:
            for val, n in conn.execute(
                "SELECT val, SUM(n) FROM metrics_daily WHERE dim = 'page' "
                "AND event_type = 'page_view' AND day >= ? AND day <= ? GROUP BY val",
                (rollup_from, rollup_to),
            ):
                page_counts[val] = page_counts.get(val, 0) + n
        for val, n in conn.execute(
            "SELECT page, COUNT(*) FROM page_views WHERE created_at >= ? GROUP BY page",
            (live_from,),
        ):
            page_counts[val] = page_counts.get(val, 0) + n
        page_view_breakdown = _ranked(page_counts)

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
