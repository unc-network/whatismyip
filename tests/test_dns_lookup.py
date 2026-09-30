"""Tests for direct DNS queries and answer comparison."""

import dns.message
import dns.rcode
import dns.rrset

from whatismyip.dns_lookup import (
    _answer_records,
    _build_cname_chains,
    _query_resolver,
    compare_answers,
)

TARGET = {"id": "public", "label": "Internet DNS", "address": "8.8.8.8"}


def test_query_resolver_returns_records_and_remaining_ttl(monkeypatch):
    response = dns.message.make_response(dns.message.make_query("example.com.", "A"))
    response.answer.append(
        dns.rrset.from_text("example.com.", 245, "IN", "A", "192.0.2.10")
    )
    monkeypatch.setattr("whatismyip.dns_lookup.dns.query.udp", lambda *a, **k: response)

    result = _query_resolver("example.com.", "A", TARGET, 3.0)

    assert result["status"] == "success"
    assert result["rcode"] == "NOERROR"
    assert result["answers"] == [
        {"name": "example.com.", "type": "A", "ttl": 245, "data": "192.0.2.10"}
    ]


def test_query_resolver_returns_negative_cache_ttl(monkeypatch):
    response = dns.message.make_response(
        dns.message.make_query("missing.example.", "A")
    )
    response.set_rcode(dns.rcode.NXDOMAIN)
    response.authority.append(
        dns.rrset.from_text(
            "example.",
            600,
            "IN",
            "SOA",
            "ns1.example. hostmaster.example. 1 3600 600 86400 120",
        )
    )
    monkeypatch.setattr("whatismyip.dns_lookup.dns.query.udp", lambda *a, **k: response)

    result = _query_resolver("missing.example.", "A", TARGET, 3.0)

    assert result["status"] == "nxdomain"
    assert result["negative_ttl"] == 120


def test_query_resolver_hides_internal_exception_details(monkeypatch):
    logged_warnings = []

    def fail_query(*args, **kwargs):
        raise OSError("private network detail")

    def capture_warning(message, *args, **kwargs):
        logged_warnings.append((message, args, kwargs))

    monkeypatch.setattr("whatismyip.dns_lookup.dns.query.udp", fail_query)
    monkeypatch.setattr("whatismyip.dns_lookup._LOGGER.warning", capture_warning)

    result = _query_resolver("example.com.", "A", TARGET, 3.0)

    assert result["status"] == "error"
    assert result["error"] == "The DNS query failed."
    assert "private network detail" not in result["error"]
    assert len(logged_warnings) == 1
    assert "private network detail" in str(logged_warnings[0][1][1])
    assert logged_warnings[0][2]["exc_info"] is True


def test_answer_records_are_capped():
    response = dns.message.make_response(dns.message.make_query("example.com.", "A"))
    for index in range(101):
        response.answer.append(
            dns.rrset.from_text(
                f"host-{index}.example.com.", 300, "IN", "A", "192.0.2.10"
            )
        )

    records, truncated = _answer_records(response)

    assert len(records) == 100
    assert truncated is True


def test_build_cname_chains_orders_aliases_and_terminal_records():
    answers = [
        {
            "name": "edge.example.net.",
            "type": "A",
            "ttl": 30,
            "data": "192.0.2.10",
        },
        {
            "name": "service.example.net.",
            "type": "CNAME",
            "ttl": 120,
            "data": "edge.example.net.",
        },
        {
            "name": "www.example.edu.",
            "type": "CNAME",
            "ttl": 300,
            "data": "service.example.net.",
        },
    ]

    chains = _build_cname_chains("WWW.Example.EDU.", answers)

    assert chains == [
        {
            "steps": [
                {
                    "name": "www.example.edu.",
                    "target": "service.example.net.",
                    "ttl": 300,
                },
                {
                    "name": "service.example.net.",
                    "target": "edge.example.net.",
                    "ttl": 120,
                },
            ],
            "terminal_name": "edge.example.net.",
            "terminal_records": [{"type": "A", "data": "192.0.2.10", "ttl": 30}],
            "loop_detected": False,
        }
    ]


def test_compare_answers_aligns_records_and_ignores_ttl_differences():
    results = [
        {
            "id": "internal",
            "status": "success",
            "rcode": "NOERROR",
            "answers": [
                {"name": "example.", "type": "A", "ttl": 300, "data": "192.0.2.10"}
            ],
        },
        {
            "id": "public",
            "status": "success",
            "rcode": "NOERROR",
            "answers": [
                {"name": "example.", "type": "A", "ttl": 125, "data": "192.0.2.10"}
            ],
        },
    ]

    comparison = compare_answers(results)

    assert comparison["same_answers"] is True
    assert comparison["rows"][0]["internal_ttl"] == 300
    assert comparison["rows"][0]["public_ttl"] == 125


def test_compare_answers_does_not_claim_truncated_results_match():
    results = [
        {
            "id": "internal",
            "status": "success",
            "rcode": "NOERROR",
            "answers_truncated": True,
            "answers": [
                {"name": "example.", "type": "A", "ttl": 300, "data": "192.0.2.10"}
            ],
        },
        {
            "id": "public",
            "status": "success",
            "rcode": "NOERROR",
            "answers_truncated": False,
            "answers": [
                {"name": "example.", "type": "A", "ttl": 300, "data": "192.0.2.10"}
            ],
        },
    ]

    comparison = compare_answers(results)

    assert comparison["answers_truncated"] is True
    assert comparison["comparable"] is False
    assert comparison["same_answers"] is None
