import pytest

from whatismyip import app, redirect_split_stack_hosts_to_primary


@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client


def _metrics_stub():
    return {
        "window_days": 30,
        "total_hostinfo": 0,
        "total_campus": 0,
        "total_remote": 0,
        "daily_series": [],
        "daily_max": 0,
        "ip_versions": [],
        "isp_breakdown": [],
        "country_breakdown": [],
        "campus_breakdown": [],
        "purpose_breakdown": [],
    }


def test_metrics_route_is_public_when_no_auth_configured(client, monkeypatch):
    monkeypatch.setattr("whatismyip.get_metrics_dashboard", _metrics_stub)
    monkeypatch.setitem(app.config, "METRICS_USERNAME", "")
    monkeypatch.setitem(app.config, "METRICS_PASSWORD", "")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert b"Usage Metrics" in response.data


def test_metrics_route_requires_auth_when_configured(client, monkeypatch):
    monkeypatch.setattr("whatismyip.get_metrics_dashboard", _metrics_stub)
    monkeypatch.setitem(app.config, "METRICS_USERNAME", "admin")
    monkeypatch.setitem(app.config, "METRICS_PASSWORD", "secret")

    assert client.get("/metrics").status_code == 401

    authed = client.get("/metrics", headers={"Authorization": "Basic YWRtaW46c2VjcmV0"})
    assert authed.status_code == 200


def test_sitemap_includes_core_pages(client):
    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert b"whatismyip.unc.edu/" in response.data
    assert b"whatismyip.unc.edu/faq" in response.data
    assert b"whatismyip.unc.edu/about" in response.data
    assert b"whatismyip.unc.edu/metrics" in response.data


@pytest.mark.parametrize(
    ("path", "canonical_url"),
    [
        ("/", "https://whatismyip.unc.edu"),
        ("/about", "https://whatismyip.unc.edu/about"),
        ("/faq", "https://whatismyip.unc.edu/faq"),
        ("/metrics", "https://whatismyip.unc.edu/metrics"),
    ],
)
def test_pages_use_canonical_urls_from_sitemap(
    client, monkeypatch, path, canonical_url
):
    monkeypatch.setitem(app.config, "SERVER_URL", "https://whatismyip.unc.edu")
    monkeypatch.setitem(app.config, "METRICS_USERNAME", "")
    monkeypatch.setitem(app.config, "METRICS_PASSWORD", "")
    monkeypatch.setattr("whatismyip.get_metrics_dashboard", _metrics_stub)

    response = client.get(path)

    assert response.status_code == 200
    assert f'<link rel="canonical" href="{canonical_url}">'.encode() in response.data


@pytest.mark.parametrize(
    ("incoming_host", "path", "location"),
    [
        (
            "ipv4.whatismyip.unc.edu",
            "/",
            "https://whatismyip.unc.edu/",
        ),
        (
            "ipv4.whatismyip.unc.edu",
            "/faq",
            "https://whatismyip.unc.edu/faq",
        ),
        (
            "ipv6.whatismyip.unc.edu",
            "/about?ref=dualstack",
            "https://whatismyip.unc.edu/about?ref=dualstack",
        ),
    ],
)
def test_split_stack_hostnames_redirect_to_primary_site(
    client, monkeypatch, incoming_host, path, location
):
    monkeypatch.setitem(app.config, "SERVER_URL", "https://whatismyip.unc.edu")
    monkeypatch.setitem(
        app.config, "IPV4_SERVER_URL", "https://ipv4.whatismyip.unc.edu"
    )
    monkeypatch.setitem(
        app.config, "IPV6_SERVER_URL", "https://ipv6.whatismyip.unc.edu"
    )

    response = client.get(path, headers={"Host": incoming_host})

    assert response.status_code == 308
    assert response.headers["Location"] == location


def test_split_stack_hostnames_keep_hostinfo_route(client, monkeypatch):
    monkeypatch.setitem(app.config, "SERVER_URL", "https://whatismyip.unc.edu")
    monkeypatch.setitem(
        app.config, "IPV4_SERVER_URL", "https://ipv4.whatismyip.unc.edu"
    )
    monkeypatch.setitem(
        app.config, "IPV6_SERVER_URL", "https://ipv6.whatismyip.unc.edu"
    )

    with app.test_request_context(
        "/hostinfo", headers={"Host": "ipv4.whatismyip.unc.edu"}
    ):
        response = redirect_split_stack_hosts_to_primary()

    assert response is None
