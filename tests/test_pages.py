"""Tests for pages blueprint — static pages, redirects, file serving, error handlers."""

import json
import re

import pytest

from whatismyip import create_app


@pytest.fixture
def app(tmp_path):
    db = tmp_path / "metrics.sqlite3"
    return create_app({"TESTING": True, "METRICS_DB_PATH": str(db)})


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


def _structured_data(response):
    blocks = re.findall(
        rb'<script type="application/ld\+json">\s*(.*?)\s*</script>',
        response.data,
        re.DOTALL,
    )
    return [json.loads(block) for block in blocks]


# --- Trailing-slash redirects ---


@pytest.mark.parametrize(
    ("path", "location"),
    [
        ("/about/", "/about"),
        ("/faq/", "/faq"),
        ("/speedtest/", "/speedtest"),
        ("/connectivity/", "/connectivity"),
        ("/dns-lookup/", "/dns-lookup"),
    ],
)
def test_trailing_slash_redirects(client, path, location):
    response = client.get(path)
    assert response.status_code == 308
    assert response.headers["Location"] == location


# --- Page content ---


def test_connectivity_page_renders(client):
    response = client.get("/connectivity")
    assert response.status_code == 200
    assert b"Run browser-based connectivity tests" in response.data
    assert (
        b'<meta name="keywords" content="connectivity test, network diagnostics'
        in response.data
    )
    structured_data = _structured_data(response)
    assert structured_data[0]["@type"] == "WebApplication"
    assert structured_data[0]["name"] == "UNC Connectivity Tests"
    assert structured_data[0]["url"].endswith("/connectivity")


def test_speedtest_page_renders(client):
    response = client.get("/speedtest")
    assert response.status_code == 200
    assert (
        b'<meta name="keywords" content="internet speed test, network speed test'
        in response.data
    )
    structured_data = _structured_data(response)
    assert structured_data[0]["@type"] == "WebPage"
    assert structured_data[0]["mainEntity"]["@type"] == "WebApplication"
    assert structured_data[0]["mainEntity"]["provider"]["name"] == "Ookla"


def test_dns_lookup_page_renders_when_enabled(app, client):
    app.config["DNS_LOOKUP_ENABLED"] = True
    response = client.get("/dns-lookup")
    assert response.status_code == 200
    assert b"<title>DNS Lookup Tool" in response.data
    assert b"Look up A, AAAA, CNAME, MX, TXT, NS, SOA, and PTR records" in response.data
    assert (
        b'<meta name="keywords" content="DNS lookup, DNS record lookup' in response.data
    )
    assert b"Answer comparison" in response.data
    assert b"What this DNS lookup tool checks" in response.data
    assert b'id="dns-about"' in response.data
    assert b"Supported DNS record types" in response.data
    assert b"Campus and public DNS comparison" in response.data
    assert b'"@type": "WebApplication"' in response.data
    assert b'"name": "UNC DNS Lookup Tool"' in response.data
    assert b"dns-select-icon" in response.data
    assert b'id="dns-share"' in response.data
    assert b"Copy query link" in response.data
    assert b"Copy results as text" in response.data
    assert b"Copy result image" in response.data
    assert b"Download PNG" in response.data
    assert b"ClipboardItem" in response.data
    assert b"createResultCanvas" in response.data
    assert b"dnsAbout.hidden = true" in response.data
    assert b"dnsAbout.hidden = false" in response.data
    assert b"URLSearchParams" in response.data
    assert b"DNS Lookup" in response.data


@pytest.mark.parametrize(
    ("path", "keywords"),
    [
        ("/faq", b"IP address FAQ, campus network help"),
        ("/about", b"UNC IP address tool, UNC network diagnostics"),
    ],
)
def test_informational_pages_use_specific_meta_keywords(client, path, keywords):
    response = client.get(path)
    assert response.status_code == 200
    assert b'<meta name="keywords" content="' + keywords in response.data


def test_faq_documents_hostinfo_rate_limit(client):
    response = client.get("/faq")

    assert response.status_code == 200
    assert b"The endpoint is rate-limited" in response.data
    assert b"Retry-After" in response.data
    assert b"HTTP <code>429</code>" in response.data

    faq_data = next(
        block for block in _structured_data(response) if block["@type"] == "FAQPage"
    )
    api_question = next(
        question
        for question in faq_data["mainEntity"]
        if question["name"] == "Is an API available?"
    )
    assert "Retry-After" in api_question["acceptedAnswer"]["text"]


def test_pages_include_social_image_alt_text(client):
    response = client.get("/about")
    assert response.status_code == 200
    expected = b"What Is My IP? logo: a laptop with a question mark"
    assert b'<meta property="og:image:alt" content="' + expected in response.data
    assert b'<meta name="twitter:image:alt" content="' + expected in response.data


def test_hostinfo_script_handles_rate_limit_retries(client):
    response = client.get("/static/js/whatismyip.js")

    assert response.status_code == 200
    assert b"HOSTINFO_MAX_AUTO_RETRIES = 2" in response.data
    assert b"getResponseHeader('Retry-After')" in response.data
    assert b"Too many refreshes. Retrying connection details" in response.data
    assert b"options.xhr.status !== 429" in response.data


def test_dns_lookup_page_returns_404_when_disabled(app, client):
    app.config["DNS_LOOKUP_ENABLED"] = False
    assert client.get("/dns-lookup").status_code == 404


def test_dns_lookup_page_can_be_restricted_to_campus(app, client, monkeypatch):
    app.config["DNS_LOOKUP_ENABLED"] = True
    app.config["DNS_LOOKUP_PAGE_CAMPUS_ONLY"] = True
    monkeypatch.setattr("whatismyip.routes.pages.is_campus_ip", lambda address: False)
    assert client.get("/dns-lookup").status_code == 403


# --- Static file serving ---


def test_robots_txt_is_served(client):
    response = client.get("/robots.txt")
    assert response.status_code == 200


def test_sitemap_xml_is_served(client):
    response = client.get("/sitemap.xml")
    assert response.status_code == 200


# --- IndexNow key file ---


def test_indexnow_key_returns_200_when_key_matches(app, client):
    app.config["INDEXNOW_KEY"] = "abc123"
    response = client.get("/abc123.txt")
    assert response.status_code == 200
    assert response.data == b"abc123"


def test_indexnow_key_returns_404_when_no_key_configured(client):
    response = client.get("/anything.txt")
    assert response.status_code == 404


def test_indexnow_key_returns_404_when_filename_does_not_match(app, client):
    app.config["INDEXNOW_KEY"] = "abc123"
    response = client.get("/wrongkey.txt")
    assert response.status_code == 404


# --- Error handlers ---


def test_404_handler_renders_template(client):
    response = client.get("/this-path-does-not-exist-at-all")
    assert response.status_code == 404
    assert b"404" in response.data
    assert b'<meta name="robots" content="noindex, nofollow">' in response.data
    assert b"The requested page could not be found" in response.data
    assert b'<link rel="canonical"' not in response.data


def test_500_handler_renders_template(client):
    response = client.get("/trigger-500")
    assert response.status_code == 500
    assert b"500" in response.data
    assert b'<meta name="robots" content="noindex, nofollow">' in response.data
    assert b"encountered an internal server error" in response.data
    assert b'<link rel="canonical"' not in response.data
