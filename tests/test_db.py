"""Tests for whatismyip.db — metrics storage and dashboard aggregation."""

import sqlite3

import pytest

from whatismyip import create_app
from whatismyip.db import ensure_metrics_store, get_metrics_dashboard, log_metrics_event


@pytest.fixture
def app(tmp_path):
    db = tmp_path / "metrics.sqlite3"
    return create_app({"TESTING": True, "METRICS_DB_PATH": str(db)})


# --- ensure_metrics_store ---


def test_ensure_metrics_store_creates_table(app):
    with app.app_context():
        ensure_metrics_store()
        db_path = app.config["METRICS_DB_PATH"]

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "metrics_events" in tables


def test_ensure_metrics_store_is_idempotent(app):
    with app.app_context():
        ensure_metrics_store()
        ensure_metrics_store()  # second call must not raise


# --- log_metrics_event ---


def test_log_metrics_event_writes_row(app):
    with app.app_context():
        log_metrics_event(
            "hostinfo",
            ip_version=4,
            isp="Test ISP",
            city="Chapel Hill",
            is_campus=True,
        )
        db_path = app.config["METRICS_DB_PATH"]

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM metrics_events WHERE event_type = 'hostinfo'"
        ).fetchone()

    assert row is not None
    assert row["ip_version"] == 4
    assert row["isp"] == "Test ISP"
    assert row["city"] == "Chapel Hill"
    assert row["is_campus"] == 1


def test_log_metrics_event_dns_result(app):
    with app.app_context():
        log_metrics_event(
            "dns_result",
            dns_filtering="active",
            dns_geo="US",
        )
        db_path = app.config["METRICS_DB_PATH"]

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM metrics_events WHERE event_type = 'dns_result'"
        ).fetchone()

    assert row is not None
    assert row["dns_filtering"] == "active"
    assert row["dns_geo"] == "US"


def test_log_metrics_event_dns_lookup(app):
    with app.app_context():
        log_metrics_event(
            "dns_lookup",
            is_campus=True,
            dns_lookup_outcome="different",
        )
        db_path = app.config["METRICS_DB_PATH"]

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM metrics_events WHERE event_type = 'dns_lookup'"
        ).fetchone()

    assert row is not None
    assert row["is_campus"] == 1
    assert row["dns_lookup_outcome"] == "different"


def test_log_metrics_event_does_not_raise_on_bad_db(app, monkeypatch):
    monkeypatch.setitem(app.config, "METRICS_DB_PATH", "/no/such/dir/metrics.sqlite3")
    with app.app_context():
        log_metrics_event("hostinfo")  # must not raise


# --- get_metrics_dashboard ---


def test_get_metrics_dashboard_returns_expected_keys(app):
    with app.app_context():
        data = get_metrics_dashboard()

    expected = {
        "window_days",
        "total_hostinfo",
        "total_campus",
        "total_remote",
        "daily_series",
        "daily_max",
        "ip_versions",
        "isp_breakdown",
        "org_breakdown",
        "country_breakdown",
        "campus_breakdown",
        "purpose_breakdown",
        "dns_filtering_breakdown",
        "dns_geo_breakdown",
        "total_dns_lookups",
        "dns_lookup_origin_breakdown",
        "dns_lookup_outcome_breakdown",
    }
    assert expected <= data.keys()


def test_get_metrics_dashboard_counts_events(app):
    with app.app_context():
        log_metrics_event("hostinfo", is_campus=True)
        log_metrics_event("hostinfo", is_campus=True)
        log_metrics_event("hostinfo", is_campus=False)
        log_metrics_event(
            "dns_result", is_campus=True, dns_filtering="active", dns_geo="US"
        )
        log_metrics_event(
            "dns_result", is_campus=False, dns_filtering="inactive", dns_geo="US"
        )
        log_metrics_event("dns_result", dns_filtering="inconclusive", dns_geo="US")
        log_metrics_event("dns_lookup", is_campus=True, dns_lookup_outcome="matching")
        log_metrics_event(
            "dns_lookup", is_campus=False, dns_lookup_outcome="public_only"
        )
        log_metrics_event("dns_lookup", is_campus=True, dns_lookup_outcome="different")
        # clear cache so dashboard re-queries
        import whatismyip.db as db_module

        db_module._metrics_cache["data"] = None

        data = get_metrics_dashboard()

    assert data["total_hostinfo"] == 3
    assert data["total_campus"] == 2
    assert data["total_remote"] == 1
    assert data["dns_filtering_breakdown"] == [
        {"label": "Active", "count": 1, "percentage": 100.0}
    ]
    assert data["total_dns_lookups"] == 3
    assert {
        row["label"]: row["count"] for row in data["dns_lookup_origin_breakdown"]
    } == {
        "On campus": 2,
        "Off campus": 1,
    }
    assert {
        row["label"]: row["count"] for row in data["dns_lookup_outcome_breakdown"]
    } == {
        "Different answers": 1,
        "Matching answers": 1,
        "Public view only": 1,
    }


def test_get_metrics_dashboard_uses_cache(app):
    with app.app_context():
        import whatismyip.db as db_module

        db_module._metrics_cache["data"] = None
        first = get_metrics_dashboard()
        # write a new event — should NOT appear because cache is warm
        log_metrics_event("hostinfo")
        second = get_metrics_dashboard()

    assert first is second


# --- daily rollups and maintenance ---


def _seed_days(app, days_back):
    """Write one hostinfo + one page view per day, days_back..1 days ago."""
    import sqlite3
    from datetime import datetime, timedelta, timezone

    path = app.config["METRICS_DB_PATH"]
    with app.app_context():
        ensure_metrics_store()
    rows = []
    for d in range(days_back, 0, -1):
        ts = (datetime.now(timezone.utc) - timedelta(days=d, hours=6)).isoformat()
        rows.append((ts, "hostinfo", 4, "Test ISP", 1, "Campus"))
    with sqlite3.connect(path) as conn:
        for ts, et, ipv, isp, campus, purpose in rows:
            conn.execute(
                "INSERT INTO metrics_events (created_at, event_type, ip_version, isp,"
                " is_campus, network_purpose) VALUES (?,?,?,?,?,?)",
                (ts, et, ipv, isp, campus, purpose),
            )
            conn.execute(
                "INSERT INTO page_views (created_at, page) VALUES (?, 'Home')", (ts,)
            )


def test_run_daily_maintenance_rolls_up_complete_days(app):
    import sqlite3

    from whatismyip.db import run_daily_maintenance

    _seed_days(app, 5)
    with app.app_context():
        rolled = run_daily_maintenance()
    assert rolled.days > 0
    with sqlite3.connect(app.config["METRICS_DB_PATH"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM metrics_daily").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM metrics_daily_done").fetchone()[0] > 0


def test_dashboard_matches_with_and_without_rollups(app):
    """The merged read path must report the same numbers either way."""
    import whatismyip.db as db_module
    from whatismyip.db import run_daily_maintenance

    _seed_days(app, 5)
    with app.app_context():
        db_module._metrics_cache["data"] = None
        live_only = get_metrics_dashboard()
        run_daily_maintenance()
        db_module._metrics_cache["data"] = None
        from_rollups = get_metrics_dashboard()

    for key in (
        "total_hostinfo",
        "total_campus",
        "daily_series",
        "isp_breakdown",
        "purpose_breakdown",
        "page_view_breakdown",
        "daily_page_views_series",
    ):
        assert live_only[key] == from_rollups[key], f"{key} differs"


def test_maintenance_applies_retention(app):
    import sqlite3
    from datetime import datetime, timedelta, timezone

    from whatismyip.db import run_daily_maintenance

    path = app.config["METRICS_DB_PATH"]
    with app.app_context():
        ensure_metrics_store()
    old = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO metrics_events (created_at, event_type) VALUES (?, 'hostinfo')",
            (old,),
        )
        conn.execute(
            "INSERT INTO page_views (created_at, page) VALUES (?, 'Home')", (old,)
        )
    with app.app_context():
        run_daily_maintenance()
    with sqlite3.connect(path) as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM metrics_events WHERE created_at = ?", (old,)
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM page_views WHERE created_at = ?", (old,)
            ).fetchone()[0]
            == 0
        )


def test_schedule_daily_maintenance_does_not_block(app):
    import time

    import whatismyip.db as db_module

    _seed_days(app, 3)
    with app.app_context():
        db_module._last_maintenance_check = 0.0
        start = time.perf_counter()
        db_module.schedule_daily_maintenance()
        elapsed = time.perf_counter() - start
        for _ in range(50):
            if not db_module._rollup_thread_running:
                break
            time.sleep(0.1)
    assert elapsed < 0.5, "scheduling must not do the work inline"
