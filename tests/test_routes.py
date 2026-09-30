import dns.exception
import pytest

from whatismyip import create_app
from whatismyip.routes.main import redirect_split_stack_hosts_to_primary


@pytest.fixture
def app(tmp_path):
    db = tmp_path / "metrics.sqlite3"
    return create_app({"TESTING": True, "METRICS_DB_PATH": str(db)})


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


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
        "org_breakdown": [],
        "country_breakdown": [],
        "campus_breakdown": [],
        "purpose_breakdown": [],
        "dns_filtering_breakdown": [],
        "dns_geo_breakdown": [],
    }


def test_metrics_route_is_public_when_no_auth_configured(app, client, monkeypatch):
    monkeypatch.setattr(
        "whatismyip.routes.metrics.get_metrics_dashboard", _metrics_stub
    )
    monkeypatch.setitem(app.config, "METRICS_USERNAME", "")
    monkeypatch.setitem(app.config, "METRICS_PASSWORD", "")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert b"Site Statistics" in response.data


def test_metrics_route_requires_auth_when_configured(app, client, monkeypatch):
    monkeypatch.setattr(
        "whatismyip.routes.metrics.get_metrics_dashboard", _metrics_stub
    )
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
    assert b"whatismyip.unc.edu/connectivity" in response.data
    assert b"whatismyip.unc.edu/dns-lookup" in response.data


@pytest.mark.parametrize(
    ("path", "canonical_url"),
    [
        ("/", "https://whatismyip.unc.edu/"),
        ("/about", "https://whatismyip.unc.edu/about"),
        ("/faq", "https://whatismyip.unc.edu/faq"),
        ("/metrics", "https://whatismyip.unc.edu/metrics"),
    ],
)
def test_pages_use_canonical_urls_from_sitemap(
    app, client, monkeypatch, path, canonical_url
):
    monkeypatch.setitem(app.config, "SERVER_URL", "https://whatismyip.unc.edu")
    monkeypatch.setitem(app.config, "METRICS_USERNAME", "")
    monkeypatch.setitem(app.config, "METRICS_PASSWORD", "")
    monkeypatch.setattr(
        "whatismyip.routes.metrics.get_metrics_dashboard", _metrics_stub
    )

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
    app, client, monkeypatch, incoming_host, path, location
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


def test_split_stack_hostnames_keep_hostinfo_route(app, client, monkeypatch):
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


# --- /hostinfo tests ---


def test_hostinfo_simulate_oncampus_returns_fixture(client):
    response = client.get("/hostinfo?simulate=oncampus")
    assert response.status_code == 200
    data = response.get_json()
    assert data["client_address"] == "192.0.2.50"
    assert data["is_campus"] is True
    assert "network" in data
    assert "address_details" in data
    assert "user_device" in data


def test_hostinfo_simulate_oncampus6_returns_fixture(client):
    response = client.get("/hostinfo?simulate=oncampus6")
    assert response.status_code == 200
    data = response.get_json()
    assert data["client_address"] == "2001:db8::50"
    assert "network" in data
    assert "address_details" in data


def _no_ptr(*a, **kw):
    raise dns.exception.DNSException()


def test_hostinfo_off_campus_ip_returns_valid_json(client, monkeypatch):
    monkeypatch.delenv("CLIENT_ADDRESS", raising=False)
    monkeypatch.delenv("CLIENT_ADDRESS_V4", raising=False)
    monkeypatch.delenv("CLIENT_ADDRESS_V6", raising=False)
    monkeypatch.delenv("FORWARDED_FOR", raising=False)
    monkeypatch.setattr("whatismyip.routes.api.is_campus_ip", lambda ip: False)
    monkeypatch.setattr("whatismyip.routes.api.get_network", lambda ip: None)
    monkeypatch.setattr("whatismyip.routes.api.get_address_objects", lambda ip: None)
    monkeypatch.setattr(
        "whatismyip.routes.api.log_metrics_event", lambda *a, **kw: None
    )
    monkeypatch.setattr("whatismyip.routes.api.resolver.query", _no_ptr)

    response = client.get("/hostinfo", environ_base={"REMOTE_ADDR": "10.0.0.1"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["client_address"] == "10.0.0.1"
    assert data["is_campus"] is False
    assert data["network"]["cidr"] is None


def test_hostinfo_campus_ip_populates_network_and_purpose(client, monkeypatch):
    monkeypatch.delenv("CLIENT_ADDRESS", raising=False)
    monkeypatch.delenv("CLIENT_ADDRESS_V4", raising=False)
    monkeypatch.delenv("CLIENT_ADDRESS_V6", raising=False)
    monkeypatch.delenv("FORWARDED_FOR", raising=False)
    mock_network = {
        "network": "152.2.0.0/16",
        "comment": "UNC Chapel Hill",
        "extattrs": {"Purpose": {"value": "Wired"}},
        "members": [],
        "options": [],
        "vlans": [],
    }
    monkeypatch.setattr("whatismyip.routes.api.is_campus_ip", lambda ip: True)
    monkeypatch.setattr("whatismyip.routes.api.get_network", lambda ip: mock_network)
    monkeypatch.setattr("whatismyip.routes.api.get_address_objects", lambda ip: None)
    monkeypatch.setattr("whatismyip.routes.api.get_nac_info", lambda ip, mac=None: None)
    monkeypatch.setattr(
        "whatismyip.routes.api.log_metrics_event", lambda *a, **kw: None
    )
    monkeypatch.setattr("whatismyip.routes.api.resolver.query", _no_ptr)

    response = client.get("/hostinfo", environ_base={"REMOTE_ADDR": "10.0.0.1"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["is_campus"] is True
    assert data["network"]["cidr"] == "152.2.0.0/16"
    assert data["network"]["purpose"] == "Wired"


def test_hostinfo_external_failures_degrade_gracefully(client, monkeypatch):
    def _ipam_down(*a, **kw):
        raise Exception("IPAM down")

    monkeypatch.delenv("CLIENT_ADDRESS", raising=False)
    monkeypatch.delenv("CLIENT_ADDRESS_V4", raising=False)
    monkeypatch.delenv("CLIENT_ADDRESS_V6", raising=False)
    monkeypatch.delenv("FORWARDED_FOR", raising=False)
    monkeypatch.setattr("whatismyip.routes.api.is_campus_ip", lambda ip: False)
    monkeypatch.setattr("whatismyip.routes.api.get_network", _ipam_down)
    monkeypatch.setattr("whatismyip.routes.api.get_address_objects", _ipam_down)
    monkeypatch.setattr(
        "whatismyip.routes.api.log_metrics_event", lambda *a, **kw: None
    )
    monkeypatch.setattr("whatismyip.routes.api.resolver.query", _no_ptr)

    response = client.get("/hostinfo", environ_base={"REMOTE_ADDR": "10.0.0.1"})
    assert response.status_code == 200
    assert response.get_json()["client_address"] == "10.0.0.1"


# --- /api/dns-lookup tests ---


def _dns_response_for_targets(name, record_type, targets, timeout):
    return [
        {
            "id": target["id"],
            "label": target["label"],
            "address": target["address"],
            "status": "success",
            "rcode": "NOERROR",
            "latency_ms": 4,
            "negative_ttl": None,
            "answers": [
                {
                    "name": name,
                    "type": record_type,
                    "ttl": 300,
                    "data": "192.0.2.10",
                }
            ],
            "error": None,
        }
        for target in targets
    ]


def test_dns_lookup_off_campus_queries_only_public(app, client, monkeypatch):
    app.config.update(
        DNS_LOOKUP_ENABLED=True,
        DNS_LOOKUP_INTERNAL_RESOLVER="172.22.255.100",
        DNS_LOOKUP_PUBLIC_RESOLVER="8.8.8.8",
        DNS_LOOKUP_INTERNAL_CAMPUS_ONLY=True,
        DNS_LOOKUP_RATE_LIMIT=300,
    )
    monkeypatch.setattr("whatismyip.routes.api.is_campus_ip", lambda address: False)
    monkeypatch.setattr(
        "whatismyip.routes.api.query_resolvers", _dns_response_for_targets
    )

    response = client.post("/api/dns-lookup", json={"name": "Example.COM", "type": "A"})
    data = response.get_json()

    assert response.status_code == 200
    assert response.cache_control.no_store is True
    assert data["internal_included"] is False
    assert [result["id"] for result in data["results"]] == ["public"]
    assert data["query"] == {"name": "example.com.", "type": "A"}


def test_dns_lookup_on_campus_compares_internal_and_public(app, client, monkeypatch):
    app.config.update(
        DNS_LOOKUP_ENABLED=True,
        DNS_LOOKUP_INTERNAL_RESOLVER="172.22.255.100",
        DNS_LOOKUP_PUBLIC_RESOLVER="8.8.8.8",
        DNS_LOOKUP_INTERNAL_CAMPUS_ONLY=True,
        DNS_LOOKUP_RATE_LIMIT=300,
    )
    monkeypatch.setattr("whatismyip.routes.api.is_campus_ip", lambda address: True)
    monkeypatch.setattr(
        "whatismyip.routes.api.query_resolvers", _dns_response_for_targets
    )

    response = client.post("/api/dns-lookup", json={"name": "example.com", "type": "A"})
    data = response.get_json()

    assert response.status_code == 200
    assert data["internal_included"] is True
    assert [result["id"] for result in data["results"]] == ["internal", "public"]
    assert data["comparison"]["same_answers"] is True
    assert data["comparison"]["rows"][0]["internal_ttl"] == 300
    assert data["comparison"]["rows"][0]["public_ttl"] == 300


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": "bad name", "type": "A"},
        {"name": "example.com", "type": "ANY"},
        {"name": "example.com", "type": "PTR"},
    ],
)
def test_dns_lookup_rejects_invalid_queries(app, client, payload):
    app.config["DNS_LOOKUP_ENABLED"] = True
    app.config["DNS_LOOKUP_RATE_LIMIT"] = 300
    response = client.post("/api/dns-lookup", json=payload)
    assert response.status_code == 400
    assert response.cache_control.no_store is True


def test_dns_lookup_api_returns_404_when_disabled(app, client):
    app.config["DNS_LOOKUP_ENABLED"] = False
    assert (
        client.post("/api/dns-lookup", json={"name": "example.com"}).status_code == 404
    )


def test_dns_lookup_rate_limits_each_client(app, client, monkeypatch):
    import whatismyip.routes.api as api_routes

    api_routes._dns_rate_windows.clear()
    api_routes._dns_global_window.clear()
    app.config.update(
        DNS_LOOKUP_ENABLED=True,
        DNS_LOOKUP_INTERNAL_RESOLVER="",
        DNS_LOOKUP_PUBLIC_RESOLVER="8.8.8.8",
        DNS_LOOKUP_RATE_LIMIT=1,
    )
    monkeypatch.setattr(
        "whatismyip.routes.api.query_resolvers", _dns_response_for_targets
    )

    first = client.post("/api/dns-lookup", json={"name": "example.com", "type": "A"})
    second = client.post("/api/dns-lookup", json={"name": "example.com", "type": "A"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "60"
    api_routes._dns_rate_windows.clear()
    api_routes._dns_global_window.clear()


def test_dns_lookup_rejects_non_json_without_consuming_quota(app, client, monkeypatch):
    import whatismyip.routes.api as api_routes

    api_routes._dns_rate_windows.clear()
    api_routes._dns_global_window.clear()
    app.config.update(
        DNS_LOOKUP_ENABLED=True,
        DNS_LOOKUP_INTERNAL_RESOLVER="",
        DNS_LOOKUP_PUBLIC_RESOLVER="8.8.8.8",
        DNS_LOOKUP_RATE_LIMIT=1,
        DNS_LOOKUP_GLOBAL_RATE_LIMIT=10,
    )
    monkeypatch.setattr(
        "whatismyip.routes.api.query_resolvers", _dns_response_for_targets
    )

    rejected = client.post(
        "/api/dns-lookup",
        data="name=example.com",
        content_type="application/x-www-form-urlencoded",
    )
    valid = client.post("/api/dns-lookup", json={"name": "example.com", "type": "A"})

    assert rejected.status_code == 415
    assert valid.status_code == 200
    api_routes._dns_rate_windows.clear()
    api_routes._dns_global_window.clear()


def test_dns_lookup_rejects_oversized_json(app, client):
    app.config["DNS_LOOKUP_ENABLED"] = True
    app.config["MAX_CONTENT_LENGTH"] = 128

    response = client.post("/api/dns-lookup", json={"name": "a" * 1000, "type": "A"})

    assert response.status_code == 413
    assert response.get_json()["error"] == "The DNS query request is too large."


def test_dns_lookup_applies_global_rate_limit(app, client, monkeypatch):
    import whatismyip.routes.api as api_routes

    api_routes._dns_rate_windows.clear()
    api_routes._dns_global_window.clear()
    app.config.update(
        DNS_LOOKUP_ENABLED=True,
        DNS_LOOKUP_INTERNAL_RESOLVER="",
        DNS_LOOKUP_PUBLIC_RESOLVER="8.8.8.8",
        DNS_LOOKUP_RATE_LIMIT=10,
        DNS_LOOKUP_GLOBAL_RATE_LIMIT=1,
    )
    monkeypatch.setattr(
        "whatismyip.routes.api.query_resolvers", _dns_response_for_targets
    )

    first = client.post(
        "/api/dns-lookup",
        json={"name": "example.com", "type": "A"},
        environ_base={"REMOTE_ADDR": "192.0.2.1"},
    )
    second = client.post(
        "/api/dns-lookup",
        json={"name": "example.com", "type": "A"},
        environ_base={"REMOTE_ADDR": "192.0.2.2"},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    api_routes._dns_rate_windows.clear()
    api_routes._dns_global_window.clear()


def test_dns_lookup_rejects_when_all_query_slots_are_busy(app, client, monkeypatch):
    import whatismyip.routes.api as api_routes

    api_routes._dns_rate_windows.clear()
    api_routes._dns_global_window.clear()
    app.config.update(
        DNS_LOOKUP_ENABLED=True,
        DNS_LOOKUP_INTERNAL_RESOLVER="",
        DNS_LOOKUP_PUBLIC_RESOLVER="8.8.8.8",
        DNS_LOOKUP_RATE_LIMIT=10,
        DNS_LOOKUP_GLOBAL_RATE_LIMIT=10,
        DNS_LOOKUP_MAX_CONCURRENT=1,
    )
    monkeypatch.setattr(api_routes, "_dns_inflight", 1)

    response = client.post("/api/dns-lookup", json={"name": "example.com", "type": "A"})

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "2"
