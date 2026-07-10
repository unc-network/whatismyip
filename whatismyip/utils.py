"""
Utility functions
"""

import ipaddress
import json
import re
import time
from typing import Any

import requests

# from ipwhois import IPWhois
from flask import current_app as app

from whatismyip.extreme import XMC_NBI


def is_campus_ip(ip_address: str) -> bool:
    """
    Check if the IP address falls within a configured campus network.
    Networks are loaded from data/config.toml at startup via app.config["CAMPUS_NETWORKS"].
    """
    networks = app.config.get("CAMPUS_NETWORKS", [])
    try:
        ip = ipaddress.ip_address(ip_address)
    except ValueError:
        return False
    return any(ip in net for net in networks)


def get_client_address(
    remote_address: str | None, forwarded_for: str | None
) -> str | None:
    """
    In general the X-Forwarded-For header is a comma separated list of IP
    addresses but the header format is not formally standardized.  We will
    only trust the last two addresses for security concerns.

    Example value: "2610:28:3091:1000:2::a,172.22.158.131"
    """
    client_address = None

    if forwarded_for:
        # Remove spaces, split on commas, and get the second to last address
        fwd_list = forwarded_for.replace(" ", "").split(",")
        if len(fwd_list) >= 2:
            client_address = fwd_list[-2]
        else:
            client_address = fwd_list[0]
    else:
        client_address = remote_address
    return client_address


# Simple TTL cache for geolocation results: ip → (monotonic_time, result)
# Caps ip-api.com calls to at most 1 per unique IP per TTL window.
_location_cache: dict[str, tuple[float, dict | None]] = {}
_LOCATION_CACHE_TTL = 300   # seconds — ip-api.com data doesn't change that fast
_LOCATION_CACHE_MAX = 1000  # entries — ~1 MB overhead at most


def get_ip_location(ip_address: str) -> dict[str, Any] | None:
    """
    Get geo-location data for the IP
    """
    # make sure we have a valid ip address
    try:
        ipaddr = ipaddress.ip_address(ip_address)
    except ValueError:
        app.logger.error(f"{ip_address} is not a valid ip address for location lookup")
        return None

    if not ipaddr.is_global:
        # Do not attempt this lookup on non-global IP addresses
        app.logger.debug(f"{ip_address} is not a global IP address")
        return None

    # Return cached result if still fresh
    cached = _location_cache.get(ip_address)
    if cached is not None:
        ts, data = cached
        if time.monotonic() - ts < _LOCATION_CACHE_TTL:
            app.logger.debug(f"ip_location cache hit for {ip_address}")
            return data

    # Hit the remote API to get location information about this IP address.
    # We have a few different APIs to work with.

    # Free for non-commercial use, no API key required.
    # Limits to 45 requests per minute. SSL is not available on free tier.
    # Also provides DNS test https://ip-api.com/docs/dns
    # Returns: lat, lon, city, country, isp, region, timezone, etc.
    api_url = f"http://ip-api.com/json/{ip_address}"

    # Available for FREE but provides Country and ISP information only — no lat/lon.
    # api_url = f"https://api.iplocation.net/?ip={ip_address}"

    # Free for 30,000 IP lookups per month, no API key required.  SSL is available.
    # api_url = f"https://ipapi.co/{ip_address}/json/"

    session = requests.Session()
    try:
        response = session.get(api_url, timeout=3)
    except requests.ReadTimeout as e:
        app.logger.error(f"Location API failed {e}")
        return None

    if response.status_code == 429:
        ttl = response.headers.get("X-Ttl", "?")
        app.logger.warning(
            f"ip-api.com rate limit hit — geolocation unavailable for {ip_address} "
            f"(window resets in {ttl}s)"
        )
        return None

    if response.status_code != 200:
        app.logger.warning(f"ip_location query failed {response}")
        return None

    raw = response.json()
    app.logger.debug(f"ip_location details: {raw}")
    # Normalize to a consistent structure regardless of which API is active.
    # ip-api.com uses "country"/"countryCode"; the fallback API uses "country_name"/"country_code2".
    result: dict | None = {
        "ip": raw.get("query") or raw.get("ip"),
        "ip_version": raw.get("ip_version", 4),
        "country_name": raw.get("country_name") or raw.get("country"),
        "country_code2": raw.get("country_code2") or raw.get("countryCode"),
        "city": raw.get("city"),
        "region": raw.get("regionName"),
        "isp": raw.get("isp"),
        "org": raw.get("org"),
        "asn": raw.get("as"),
        "mobile": raw.get("mobile"),
        "proxy": raw.get("proxy"),
        "hosting": raw.get("hosting"),
        "lat": raw.get("lat"),
        "lon": raw.get("lon"),
    }

    # Store in cache; evict oldest entry (insertion-order) when at capacity
    if len(_location_cache) >= _LOCATION_CACHE_MAX:
        del _location_cache[next(iter(_location_cache))]
    _location_cache[ip_address] = (time.monotonic(), result)
    return result


def get_nac_info(ip_address: str, mac: str | None = None) -> dict[str, Any] | None:
    """
    Collect information about this device from NAC (Extreme Networks XMC).
    Collect EndSystem data about the current connection and the EndSystemInfo about the device's configuration.
    """
    start_time = time.time()
    app.logger.debug(f"get_nac_info ip {ip_address} and mac {mac}")
    data: dict[str, Any] = {
        "endSystem": None,
        "endSystemInfo": None,
    }

    if not is_campus_ip(ip_address):
        app.logger.debug(
            f"{ip_address} is not a campus IP address, skipping NAC lookup"
        )
        execution_time = time.time() - start_time
        app.logger.debug(f"get_nac_info complete in {execution_time} seconds")
        return data

    app.logger.debug("Connecting to XiQ to get end system info")
    session = XMC_NBI(
        app.config["XMC_SERVER"],
        app.config["XMC_CLIENT_ID"],
        app.config["XMC_SECRET"],
        test=False,
    )
    if session.error:
        app.logger.error(f"ERROR: '{session.message}'")
        raise RuntimeError(f"NAC session failed: {session.message}")
    app.logger.debug("XMC session created")

    # Try MAC first if IPAM provided one — NAC is MAC-centric and IP mappings may lag.
    # Fall back to IP lookup if no MAC was available or the MAC lookup returned nothing.
    # Normalize MAC to uppercase — IPAM returns lowercase but XMC expects uppercase hex.
    end_system_data = None
    if mac:
        mac = mac.upper()
        app.logger.debug(f"Looking up end system info for mac {mac}")
        end_system_data = session.getEndSystemByMac(mac)
        if session.error:
            app.logger.error(f"ERROR: getEndSystemByMac failed '{session.message}'")
        app.logger.debug(f"NAC end system by mac: {end_system_data}")
        data["endSystem"] = end_system_data

    if not end_system_data:
        app.logger.debug(f"Looking up end system info for ip {ip_address}")
        end_system_data = session.getEndSystemByIp(ip_address)
        if session.error:
            app.logger.error(f"ERROR: getEndSystemByIP failed '{session.message}'")
        app.logger.debug(f"NAC end system by ip: {end_system_data}")
        data["endSystem"] = end_system_data

    if not end_system_data:
        app.logger.warning(
            f"NAC lookup exhausted for campus address {ip_address}"
            + (f" (MAC {mac})" if mac else " (no MAC from IPAM)")
            + " — no end system record found by MAC or IP"
        )

    # Lookup additional end system info using the MAC address from either the IP or MAC lookup results
    if end_system_data and end_system_data["macAddress"]:
        app.logger.debug(
            f"Looking up end system info from NAC mac {end_system_data['macAddress']}"
        )
        mac_data = session.getMacAddress(end_system_data["macAddress"])
        if session.error:
            app.logger.error(f"ERROR: getMacAddress failed '{session.message}'")
        app.logger.debug(f"nac_mac: {mac_data}")
        data["endSystemInfo"] = mac_data
    elif mac:
        app.logger.debug(f"Looking up end system info from IPAM mac {mac}")
        mac_data = session.getMacAddress(mac)
        if session.error:
            app.logger.error(f"ERROR: getMacAddress failed '{session.message}'")
        app.logger.debug(f"nac_mac: {mac_data}")
        data["endSystemInfo"] = mac_data

    # Do some cleanup on the data to add NIT inventory information
    if data["endSystem"] and "switchPortId" in data["endSystem"]:
        # Named AP format (Extreme): "AP-NAME (MAC):SSID"
        wireless_regex = r"^(?P<ap_name>\S+)\s\((?P<ap_mac>\S+)\):(?P<ssid>\S+)$"
        # MAC-only format (Meraki): "CC-6E-2A-D6-2E-40:SSID" — no AP name, no building ID
        meraki_wireless_regex = (
            r"^(?P<ap_mac>[0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5}):(?P<ssid>.+)$"
        )
        ap_name_regex = r"^(?P<tier>[^-]+)-(?P<bldg_id>\d+)-"
        match = re.match(wireless_regex, data["endSystem"]["switchPortId"])
        meraki_match = re.match(
            meraki_wireless_regex, data["endSystem"]["switchPortId"]
        )
        if match:
            # Named AP wireless — can resolve building from AP name
            data["endSystem"]["connection_type"] = "wireless"
            data["endSystem"]["wireless_controller"] = (
                data["endSystem"]["switchIP"]
                if "switchIP" in data["endSystem"]
                else None
            )
            data["endSystem"]["wireless_ap_name"] = match.group("ap_name")
            data["endSystem"]["wireless_ap_mac"] = match.group("ap_mac")
            data["endSystem"]["wireless_ssid"] = match.group("ssid")
            ap_match = re.match(ap_name_regex, match.group("ap_name"))
            if ap_match:
                data["endSystem"]["wireless_ap_tier"] = ap_match.group("tier")
                data["endSystem"]["wireless_ap_bldg_id"] = ap_match.group("bldg_id")
                data["nit_building"] = get_nit_building_by_id(ap_match.group("bldg_id"))
                app.logger.debug(f"NIT building info: {data['nit_building']}")
        elif meraki_match:
            # MAC-only wireless — enrich via Meraki API if configured
            data["endSystem"]["connection_type"] = "wireless"
            data["endSystem"]["wireless_controller"] = (
                data["endSystem"]["switchIP"]
                if "switchIP" in data["endSystem"]
                else None
            )
            ap_mac = meraki_match.group("ap_mac")
            data["endSystem"]["wireless_ap_mac"] = ap_mac
            data["endSystem"]["wireless_ssid"] = meraki_match.group("ssid")
            data["endSystem"]["wireless_ap_name"] = None
            app.logger.debug(
                f"Meraki wireless: ap_mac={ap_mac} ssid={meraki_match.group('ssid')}"
            )

            if app.config.get("MERAKI_API_KEY") and app.config.get("MERAKI_ORG_ID"):
                try:
                    from whatismyip.meraki import (
                        get_meraki_ap,
                        get_meraki_client,
                        get_meraki_signal_quality,
                    )

                    meraki_ap = get_meraki_ap(ap_mac)
                    if meraki_ap:
                        data["endSystem"]["wireless_ap_name"] = meraki_ap.get("name")
                        data["meraki_ap"] = meraki_ap
                        ap_name = meraki_ap.get("name") or ""
                        ap_match = re.match(ap_name_regex, ap_name)
                        if ap_match:
                            data["endSystem"]["wireless_ap_tier"] = ap_match.group(
                                "tier"
                            )
                            data["endSystem"]["wireless_ap_bldg_id"] = ap_match.group(
                                "bldg_id"
                            )
                            data["nit_building"] = get_nit_building_by_id(
                                ap_match.group("bldg_id")
                            )
                            app.logger.debug(
                                f"NIT building from Meraki AP name: {data['nit_building']}"
                            )
                        app.logger.debug(f"Meraki AP: {meraki_ap}")

                    client_mac = (
                        end_system_data.get("macAddress") if end_system_data else None
                    )
                    if client_mac:
                        meraki_client = get_meraki_client(client_mac)
                        if meraki_client:
                            data["meraki_client"] = meraki_client
                            app.logger.debug(f"Meraki client: {meraki_client}")
                            network_id = meraki_client.get("network_id")
                            client_id = meraki_client.get("client_id")
                            if network_id and client_id:
                                signal = get_meraki_signal_quality(
                                    network_id, client_id
                                )
                                if signal:
                                    data["meraki_signal"] = signal
                except Exception as e:
                    app.logger.warning(
                        f"Meraki enrichment failed, continuing without it: {e}"
                    )
        elif data["endSystem"] and "switchIP" in data["endSystem"]:
            # wired connection
            data["endSystem"]["connection_type"] = "wired"
            data["nit_building"] = get_nit_building(end_system_data["switchIP"])
            app.logger.debug(f"NIT building info: {data['nit_building']}")

    execution_time = time.time() - start_time
    app.logger.debug(f"get_endSystemInfo complete in {execution_time} seconds")
    return data


def get_nit_building(switch_ip: str) -> dict[str, Any] | None:
    """
    Get building information from NIT about this device IP (switch, ap, or ups).
    """
    start_time = time.time()
    app.logger.debug(f"get_nit_switch_info {switch_ip}")
    data = {}

    url = f"http://{app.config['NIT_SERVER']}:8081/buildings.cgi"
    params = {
        "authentication": app.config["NIT_AUTH"],
        "ip": switch_ip,
    }
    try:
        response = requests.get(url, params=params, timeout=5)
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        app.logger.warning(f"NIT query failed: {url} {type(e).__name__}")
        execution_time = time.time() - start_time
        app.logger.debug(f"get_nit_switch_info complete in {execution_time} seconds")
        return None
    if response.status_code != 200:
        app.logger.warning(f"NIT query failed {response}")
        execution_time = time.time() - start_time
        app.logger.debug(f"get_nit_switch_info complete in {execution_time} seconds")
        return None
    data = response.json()

    execution_time = time.time() - start_time
    app.logger.debug(f"get_nit_switch_info complete in {execution_time} seconds")
    return data.get("building") or None


def get_nit_building_by_id(building_id: str) -> dict[str, Any] | None:
    """
    Get building information from NIT about this building id
    """
    start_time = time.time()
    app.logger.debug(f"get_nit_switch_info by building id {building_id}")
    data = {}

    url = f"http://{app.config['NIT_SERVER']}:8081/buildings.cgi"
    params = {
        "authentication": app.config["NIT_AUTH"],
        "building_id": building_id,
    }
    try:
        response = requests.get(url, params=params, timeout=5)
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        app.logger.warning(f"NIT query failed: {url} {type(e).__name__}")
        execution_time = time.time() - start_time
        app.logger.debug(f"get_nit_switch_info complete in {execution_time} seconds")
        return None
    if response.status_code != 200:
        app.logger.warning(f"NIT query failed {response}")
        execution_time = time.time() - start_time
        app.logger.debug(f"get_nit_switch_info complete in {execution_time} seconds")
        return None
    data = response.json()

    execution_time = time.time() - start_time
    app.logger.debug(f"get_nit_switch_info complete in {execution_time} seconds")
    return data.get("building") or None


def parse_extreme_vsa(vsa_string: str) -> dict[str, Any]:
    parsed_data = {"Extreme-Dynamic-Config": []}

    # Split the main string by comma, but only if not within nested structures
    # Using a simple split, then cleaning whitespace
    parts = [part.strip() for part in vsa_string.split(",")]

    for part in parts:
        if "=" not in part:
            continue

        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()

        if key == "Extreme-Dynamic-Client-Assignments":
            # Parse nested comma-separated values
            nested_dict = {}
            for item in value.split(","):
                if "=" in item:
                    n_key, n_value = item.split("=", 1)
                    nested_dict[n_key.strip()] = n_value.strip()
            parsed_data[key] = nested_dict

        elif key == "Extreme-Dynamic-Config":
            # Handle multiple configuration entries
            parsed_data["Extreme-Dynamic-Config"].append(value)

        else:
            parsed_data[key] = value

    return json.dumps(parsed_data)
