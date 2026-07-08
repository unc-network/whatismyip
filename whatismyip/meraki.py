"""Cisco Meraki Dashboard API integration for wireless AP and client enrichment."""

import time
from typing import Any

import requests
from flask import current_app as app

_BASE_URL = "https://api.meraki.com/api/v1"
_TIMEOUT = 5


def _get(path: str, params: dict | None = None) -> Any:
    api_key = app.config.get("MERAKI_API_KEY", "")
    if not api_key:
        return None
    try:
        response = requests.get(
            f"{_BASE_URL}{path}",
            headers={"X-Cisco-Meraki-API-Key": api_key},
            params=params,
            timeout=_TIMEOUT,
            allow_redirects=True,
        )
        if response.status_code == 200:
            return response.json()
        app.logger.warning(f"Meraki API {path} returned {response.status_code}")
        return None
    except Exception as e:
        app.logger.warning(f"Meraki API request failed: {e}")
        return None


def get_meraki_ap(ap_mac: str) -> dict[str, Any] | None:
    """
    Look up a Meraki AP by MAC address.
    Returns name, serial, model, address, lat, lon, network_id on success.
    """
    org_id = app.config.get("MERAKI_ORG_ID", "")
    if not org_id:
        return None
    start = time.time()
    result = _get(f"/organizations/{org_id}/devices", params={"macs[]": ap_mac})
    app.logger.debug(f"Meraki AP lookup in {time.time() - start:.3f}s")
    if not isinstance(result, list) or not result:
        app.logger.debug(f"Meraki: no AP found for MAC {ap_mac}")
        return None
    device = result[0]
    return {
        "name": device.get("name") or None,
        "serial": device.get("serial") or None,
        "model": device.get("model") or None,
        "address": device.get("address") or None,
        "lat": device.get("lat") or None,
        "lon": device.get("lng") or None,
        "network_id": device.get("networkId") or None,
    }


def get_meraki_client(client_mac: str) -> dict[str, Any] | None:
    """
    Search for a wireless client by MAC address within the last hour.
    Returns manufacturer, description, status, ssid, vlan, last_seen on success.
    """
    org_id = app.config.get("MERAKI_ORG_ID", "")
    if not org_id:
        return None
    start = time.time()
    result = _get(
        f"/organizations/{org_id}/clients/search",
        params={"mac": client_mac, "timespan": 86400},
    )
    app.logger.debug(f"Meraki client lookup in {time.time() - start:.3f}s")
    if not result:
        return None
    records = result.get("records", [])
    if not records:
        app.logger.debug(f"Meraki: no client found for MAC {client_mac}")
        return None
    # manufacturer is top-level; client fields are flat in each record (no nested "client" key)
    rec = records[0]
    network_id = rec.get("network", {}).get("id") or None
    client_id = result.get("clientId") or None
    return {
        "manufacturer": result.get("manufacturer") or None,
        "mac": result.get("mac") or None,
        "description": rec.get("description") or None,
        "os": rec.get("os") or None,
        "user": rec.get("user") or None,
        "status": rec.get("status") or None,
        "ssid": rec.get("ssid") or None,
        "vlan": rec.get("vlan") or None,
        "last_seen": rec.get("lastSeen") or None,
        "wireless_capabilities": rec.get("wirelessCapabilities") or None,
        "network_id": network_id,
        "client_id": client_id,
    }


def get_meraki_signal_quality(network_id: str, client_id: str) -> dict[str, Any] | None:
    """
    Fetch recent RSSI and SNR for a wireless client using a 1-hour aggregate bucket.
    """
    start = time.time()
    result = _get(
        f"/networks/{network_id}/wireless/signalQualityHistory",
        params={"clientId": client_id, "timespan": 3600, "resolution": 3600},
    )
    app.logger.debug(f"Meraki signal quality lookup in {time.time() - start:.3f}s")
    if not isinstance(result, list) or not result:
        return None
    latest = result[-1]
    app.logger.debug(f"Meraki signal quality: {latest}")
    rssi = latest.get("rssi")
    snr = latest.get("snr")
    if rssi is None and snr is None:
        return None
    return {"rssi": rssi, "snr": snr}
