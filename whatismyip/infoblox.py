"""Infoblox WAPI integration."""

import ipaddress
import time
from typing import Any

import requests
from flask import current_app as app


def get_network(ip_address: str) -> dict[str, Any] | None:
    """Find the network for this address in IPAM."""
    start_time = time.time()
    app.logger.debug(f"get_network {ip_address}")

    try:
        ipaddr = ipaddress.ip_address(ip_address)
    except ValueError:
        app.logger.warning(f"{ip_address} is not a valid ip address")
        return None

    ib_server = app.config["IB_SERVER"]
    ib_username = app.config["IB_USERNAME"]
    ib_password = app.config["IB_PASSWORD"]
    url = f"https://{ib_server}/wapi/v2.10.5/"

    app.logger.debug("Checking for address info")
    session = requests.Session()
    params = {
        "_return_fields": "comment,network,network_view,members,extattrs,vlans.id,options",
        "_inheritance": True,
        "contains_address": ip_address,
    }
    object_type = "ipv6network" if ipaddr.version == 6 else "network"
    response = session.get(
        f"{url}{object_type}",
        params=params,
        auth=(ib_username, ib_password),
    )
    app.logger.debug(f"{response}")
    if response.status_code != 200:
        app.logger.warning(f"query failed {response}")
        app.logger.debug(f"get_network complete in {time.time() - start_time} seconds")
        return None

    network_list = response.json()
    app.logger.debug(f"network details: {network_list}")
    app.logger.debug(f"get_network complete in {time.time() - start_time} seconds")
    return network_list[0] if len(network_list) == 1 else None


def get_address_objects(ip_address: str) -> dict[str, Any] | None:
    """Find Infoblox host/address records for this IP."""
    start_time = time.time()
    app.logger.debug(f"get_address_objects {ip_address}")

    try:
        ipaddr = ipaddress.ip_address(ip_address)
    except ValueError:
        app.logger.warning(f"{ip_address} is not a valid ip address")
        return None

    ib_server = app.config["IB_SERVER"]
    ib_username = app.config["IB_USERNAME"]
    ib_password = app.config["IB_PASSWORD"]
    url = f"https://{ib_server}/wapi/v2.10.5/"

    session = requests.Session()
    params = {
        "network_view": "default",
        "_return_fields+": "discovered_data,extattrs,fingerprint,ms_ad_user_data",
        "ip_address": ip_address,
    }
    object_type = "ipv6address" if ipaddr.version == 6 else "ipv4address"
    response = session.get(
        f"{url}{object_type}",
        params=params,
        auth=(ib_username, ib_password),
    )
    app.logger.debug(f"{response}")
    if response.status_code != 200:
        app.logger.warning(f"{object_type} query failed {response}")
        app.logger.debug(
            f"get_address_objects complete in {time.time() - start_time} seconds"
        )
        return None

    address_list = response.json()
    app.logger.debug(f"{object_type} details: {address_list}")
    app.logger.debug(
        f"get_address_objects complete in {time.time() - start_time} seconds"
    )
    return address_list[0] if len(address_list) == 1 else None
