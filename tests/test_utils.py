import pytest
import requests
from flask import Flask

import whatismyip.utils as utils


class _LocationResponse:
    status_code = 200
    headers = {}

    def __init__(self, address="8.8.8.8"):
        self.address = address

    def json(self):
        return {
            "status": "success",
            "query": self.address,
            "country": "United States",
            "countryCode": "US",
            "city": "Mountain View",
            "regionName": "California",
            "isp": "Example ISP",
            "org": "Example Org",
            "as": "AS64500 Example",
            "lat": 37.4,
            "lon": -122.1,
        }


@pytest.fixture
def app():
    application = Flask(__name__)
    application.config.update(
        GEOLOCATION_CACHE_TTL=3600.0,
        GEOLOCATION_FAILURE_CACHE_TTL=60.0,
        GEOLOCATION_CONNECT_TIMEOUT=1.0,
        GEOLOCATION_READ_TIMEOUT=2.0,
        GEOLOCATION_CIRCUIT_FAILURES=3,
        GEOLOCATION_CIRCUIT_WINDOW=30.0,
        GEOLOCATION_CIRCUIT_COOLDOWN=60.0,
        GEOLOCATION_CIRCUIT_MAX_COOLDOWN=300.0,
    )
    return application


@pytest.fixture(autouse=True)
def reset_location_state():
    utils._reset_location_state()
    yield
    utils._reset_location_state()


def test_ip_location_success_cache_uses_configured_ttl(app, monkeypatch):
    clock = [1000.0]
    calls = []
    monkeypatch.setattr(utils.time, "monotonic", lambda: clock[0])

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return _LocationResponse()

    monkeypatch.setattr(utils.requests, "get", fake_get)

    with app.app_context():
        first = utils.get_ip_location("8.8.8.8")
        clock[0] += 3599.0
        cached = utils.get_ip_location("8.8.8.8")
        clock[0] += 2.0
        refreshed = utils.get_ip_location("8.8.8.8")

    assert first == cached == refreshed
    assert len(calls) == 2
    assert calls[0][1] == (1.0, 2.0)


def test_ip_location_failure_is_cached_briefly(app, monkeypatch):
    clock = [1000.0]
    calls = []
    monkeypatch.setattr(utils.time, "monotonic", lambda: clock[0])

    def timeout(*args, **kwargs):
        calls.append((args, kwargs))
        raise requests.ConnectTimeout("upstream unavailable")

    monkeypatch.setattr(utils.requests, "get", timeout)

    with app.app_context():
        assert utils.get_ip_location("8.8.8.8") is None
        assert utils.get_ip_location("8.8.8.8") is None
        assert len(calls) == 1

        clock[0] += 61.0
        assert utils.get_ip_location("8.8.8.8") is None

    assert len(calls) == 2


def test_ip_location_circuit_breaker_skips_calls_then_recovers(app, monkeypatch):
    clock = [1000.0]
    calls = []
    app.config["GEOLOCATION_CIRCUIT_FAILURES"] = 2
    monkeypatch.setattr(utils.time, "monotonic", lambda: clock[0])

    def fail_then_recover(url, timeout):
        calls.append(url)
        if len(calls) <= 2:
            raise requests.ConnectTimeout("upstream unavailable")
        return _LocationResponse(url.rsplit("/", 1)[-1])

    monkeypatch.setattr(utils.requests, "get", fail_then_recover)

    with app.app_context():
        assert utils.get_ip_location("8.8.8.8") is None
        assert utils.get_ip_location("1.1.1.1") is None

        # A different, uncached address is still suppressed while the circuit is open.
        assert utils.get_ip_location("9.9.9.9") is None
        assert len(calls) == 2

        clock[0] += 61.0
        recovered = utils.get_ip_location("9.9.9.9")
        assert recovered["ip"] == "9.9.9.9"

        # Recovery closes the circuit for normal traffic.
        assert utils.get_ip_location("208.67.222.222") is not None

    assert len(calls) == 4


def test_ip_location_rate_limit_opens_circuit_without_ttl_header(app, monkeypatch):
    clock = [1000.0]
    calls = []
    monkeypatch.setattr(utils.time, "monotonic", lambda: clock[0])

    class _RateLimitedResponse:
        status_code = 429
        headers = {}

    def rate_limited(url, timeout):
        calls.append(url)
        return _RateLimitedResponse()

    monkeypatch.setattr(utils.requests, "get", rate_limited)

    with app.app_context():
        assert utils.get_ip_location("8.8.8.8") is None
        assert utils.get_ip_location("1.1.1.1") is None

    assert len(calls) == 1


def test_ip_location_failed_recovery_probe_doubles_cooldown(app, monkeypatch):
    clock = [1000.0]
    calls = []
    app.config["GEOLOCATION_CIRCUIT_FAILURES"] = 1
    monkeypatch.setattr(utils.time, "monotonic", lambda: clock[0])

    def timeout(url, timeout):
        calls.append(url)
        raise requests.ConnectTimeout("upstream unavailable")

    monkeypatch.setattr(utils.requests, "get", timeout)

    with app.app_context():
        assert utils.get_ip_location("8.8.8.8") is None
        clock[0] += 61.0
        assert utils.get_ip_location("1.1.1.1") is None

        # The failed recovery probe reopens the circuit for 120 seconds.
        clock[0] += 61.0
        assert utils.get_ip_location("9.9.9.9") is None

    assert len(calls) == 2
