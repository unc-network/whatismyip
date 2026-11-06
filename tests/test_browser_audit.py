import hashlib
import json
from types import SimpleNamespace

import pytest
import requests

from scripts import audit_browser_libraries as audit


def test_inventory_matches_vendored_assets():
    packages = json.loads((audit.REPO_ROOT / "browser-libraries.json").read_text())[
        "packages"
    ]
    audit.verify_assets(packages, audit.REPO_ROOT)


def test_modified_asset_fails_verification(tmp_path):
    asset = tmp_path / "library.js"
    asset.write_bytes(b"modified")
    packages = [
        {
            "name": "example",
            "files": {"library.js": hashlib.sha256(b"original").hexdigest()},
        }
    ]
    with pytest.raises(ValueError, match="hash mismatch"):
        audit.verify_assets(packages, tmp_path)


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ([{}], []),
        (
            [{"vulns": [{"id": "GHSA-example"}]}],
            ["jquery@4.0.0: https://osv.dev/vulnerability/GHSA-example"],
        ),
    ],
)
def test_advisory_query_uses_exact_npm_version(monkeypatch, results, expected):
    def post(url, *, json, timeout):
        assert url == audit.OSV_URL
        assert json == {
            "queries": [
                {"package": {"name": "jquery", "ecosystem": "npm"}, "version": "4.0.0"}
            ]
        }
        return SimpleNamespace(
            raise_for_status=lambda: None, json=lambda: {"results": results}
        )

    monkeypatch.setattr(audit.requests, "post", post)
    assert audit.find_advisories([{"name": "jquery", "version": "4.0.0"}]) == expected


@pytest.mark.parametrize("results", [[], [None], [{"vulns": None}]])
def test_incomplete_or_invalid_advisory_query_fails(monkeypatch, results):
    monkeypatch.setattr(
        audit.requests,
        "post",
        lambda *args, **kwargs: SimpleNamespace(
            raise_for_status=lambda: None, json=lambda: {"results": results}
        ),
    )
    with pytest.raises((ValueError, AttributeError)):
        audit.find_advisories([{"name": "jquery", "version": "4.0.0"}])


def test_audit_fails_when_advisory_service_is_unavailable(monkeypatch):
    def unavailable(*args, **kwargs):
        raise requests.ConnectionError("OSV unavailable")

    monkeypatch.setattr(audit.requests, "post", unavailable)
    monkeypatch.setattr(audit.sys, "argv", ["audit_browser_libraries.py"])
    assert audit.main() == 1
