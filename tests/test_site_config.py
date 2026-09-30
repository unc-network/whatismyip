"""Tests for whatismyip.site_config — config loading and fallback behaviour."""

import pytest

from whatismyip import create_app


@pytest.fixture
def app(tmp_path):
    db = tmp_path / "metrics.sqlite3"
    return create_app({"TESTING": True, "METRICS_DB_PATH": str(db)})


# --- Valid config ---


def test_load_site_config_applies_campus_networks(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[campus]\nnetworks = ["152.2.0.0/16", "152.19.0.0/16"]\n')
    from whatismyip.site_config import load_site_config

    app = create_app({"TESTING": True, "METRICS_DB_PATH": str(tmp_path / "m.sqlite3")})
    with app.app_context():
        import whatismyip.site_config as sc

        original = sc.SITE_CONFIG_PATH
        sc.SITE_CONFIG_PATH = str(cfg)
        try:
            load_site_config(app)
        finally:
            sc.SITE_CONFIG_PATH = original

    assert len(app.config["CAMPUS_NETWORKS"]) == 2


def test_load_site_config_skips_invalid_cidr(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[campus]\nnetworks = ["not-a-cidr", "152.2.0.0/16"]\n')
    from whatismyip.site_config import load_site_config

    app = create_app({"TESTING": True, "METRICS_DB_PATH": str(tmp_path / "m.sqlite3")})
    with app.app_context():
        import whatismyip.site_config as sc

        original = sc.SITE_CONFIG_PATH
        sc.SITE_CONFIG_PATH = str(cfg)
        try:
            load_site_config(app)
        finally:
            sc.SITE_CONFIG_PATH = original

    assert len(app.config["CAMPUS_NETWORKS"]) == 1


def test_load_site_config_validates_map_provider(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[campus]\nnetworks = []\n[map]\nprovider = "unknown"\n')
    from whatismyip.site_config import load_site_config

    app = create_app({"TESTING": True, "METRICS_DB_PATH": str(tmp_path / "m.sqlite3")})
    with app.app_context():
        import whatismyip.site_config as sc

        original = sc.SITE_CONFIG_PATH
        sc.SITE_CONFIG_PATH = str(cfg)
        try:
            load_site_config(app)
        finally:
            sc.SITE_CONFIG_PATH = original

    assert app.config["MAP_PROVIDER"] == "leaflet"


# --- Missing config file ---


def test_load_site_config_applies_defaults_when_file_missing(tmp_path):
    missing = tmp_path / "nonexistent" / "config.toml"
    from whatismyip.site_config import load_site_config

    app = create_app({"TESTING": True, "METRICS_DB_PATH": str(tmp_path / "m.sqlite3")})
    with app.app_context():
        import whatismyip.site_config as sc

        original = sc.SITE_CONFIG_PATH
        sc.SITE_CONFIG_PATH = str(missing)
        try:
            load_site_config(app)
        finally:
            sc.SITE_CONFIG_PATH = original

    assert app.config["CAMPUS_NETWORKS"] == []
    assert app.config["DNS_SECURITY_TEST_URL"] == ""


# --- Broken config file ---


def test_load_site_config_falls_back_on_invalid_toml(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text("this is not valid toml ][")
    from whatismyip.site_config import load_site_config

    app = create_app({"TESTING": True, "METRICS_DB_PATH": str(tmp_path / "m.sqlite3")})
    with app.app_context():
        import whatismyip.site_config as sc

        original = sc.SITE_CONFIG_PATH
        sc.SITE_CONFIG_PATH = str(cfg)
        try:
            load_site_config(app)
        finally:
            sc.SITE_CONFIG_PATH = original

    assert app.config["CAMPUS_NETWORKS"] == []


def test_load_site_config_applies_dns_lookup_settings(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text("""[campus]
networks = []
[dns]
lookup_enabled = true
internal_resolver = "172.22.255.100"
public_resolver = "8.8.8.8"
allowed_record_types = ["A", "TXT", "ANY"]
query_timeout_seconds = 25
queries_per_minute = 0
global_queries_per_minute = 5000
max_concurrent_lookups = 20
""")
    from whatismyip.site_config import load_site_config

    app = create_app({"TESTING": True, "METRICS_DB_PATH": str(tmp_path / "m.sqlite3")})
    with app.app_context():
        import whatismyip.site_config as sc

        original = sc.SITE_CONFIG_PATH
        sc.SITE_CONFIG_PATH = str(cfg)
        try:
            load_site_config(app)
        finally:
            sc.SITE_CONFIG_PATH = original

    assert app.config["DNS_LOOKUP_ENABLED"] is True
    assert app.config["DNS_LOOKUP_INTERNAL_RESOLVER"] == "172.22.255.100"
    assert app.config["DNS_LOOKUP_ALLOWED_TYPES"] == ["A", "TXT"]
    assert app.config["DNS_LOOKUP_TIMEOUT"] == 10.0
    assert app.config["DNS_LOOKUP_RATE_LIMIT"] == 1
    assert app.config["DNS_LOOKUP_GLOBAL_RATE_LIMIT"] == 3000
    assert app.config["DNS_LOOKUP_MAX_CONCURRENT"] == 4
