import logging
from types import SimpleNamespace

from whatismyip.extreme import XMC_NBI


def test_query_reports_calling_method_without_eval(monkeypatch):
    monkeypatch.setattr("whatismyip.extreme.logger", logging.getLogger(__name__))
    client = XMC_NBI.__new__(XMC_NBI)
    client.session = SimpleNamespace(
        post=lambda url, *, json: "response", close=lambda: None
    )
    client.nbiUrl = "https://example.invalid/nbi/graphql"
    client.expire = float("inf")
    monkeypatch.setattr(
        client, "_decode_response", lambda response, caller: (response, caller)
    )

    def query_device():
        return client._call("query { devices }")

    assert query_device() == ("response", "query_device")
