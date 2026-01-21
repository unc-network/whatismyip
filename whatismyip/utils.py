"""
Utility functions
"""

import time
import ipaddress
import requests
import urllib3

# from ipwhois import IPWhois

from flask import current_app as app


def is_campus_ip(ip_address):
    """
    Check if the IP address is in a campus block. If so, further testing can take place.
    """

    prefixes = [
        "152.2.",
        "152.19.",
        "152.23.",
        "172.16.",
        "172.17.",
        "172.18.",
        "172.19.",
        "172.20.",
        "172.21.",
        "172.22.",
        "172.23.",
        "172.24.",
        "172.25.",
        "172.26.",
        "172.27.",
        "172.28.",
        "172.29.",
        "172.30.",
        "172.31.",
        "198.85.230.",
        "198.85.231.",
        "204.84.",
        "204.85.",
        "2610:28:3090:",
        "2610:28:3091:",
        "2610:2701:4000:",
        "2606:f640:",
    ]

    for prefix in prefixes:
        if ip_address.startswith(prefix):
            return True
    return False


# def getISP( ip ):
# 	# Lookup ISP information

# 	ipaddr = ipaddress.ip_address(ip)
# 	app.logger.debug("getISP {}".format(ip))

# 	if not ipaddr.is_private:
# 		obj = IPWhois( ip )
# 		ret = obj.lookup_rdap()
# 		print("Found {}".format(ret))
# 		return ret

# 	return {}


def get_forwarded_address(forwarded_for):
    """A proxy will populate the X-Forwarded-For header, so find the client"""
    proxy_detected = None
    fwd_list = forwarded_for.split(",")
    if len(fwd_list) > 2:
        # multiple proxy detected, only trust the last 2 for campus
        # the last for cloudapps and second to last for client
        client_address = fwd_list[-2].strip()
        proxy_detected = ",".join(fwd_list[:-2])
    else:
        # normal: the last for cloudapps and second to last for client
        client_address = fwd_list[0].strip()
    return client_address, proxy_detected


def get_network(ip_address):
    """Find the network for this address in IPAM."""
    start_time = time.time()
    app.logger.debug(f"get_network {ip_address}")

    # make sure we have a valid ip address
    try:
        ipaddr = ipaddress.ip_address(ip_address)
    except ValueError:
        app.logger.warn(f"{ip_address} is not a valid ip address")
        return {}

    if is_campus_ip(ip_address):
        # Do the lookup only if we think this is a campus address
        ib_server = app.config["IB_SERVER"]
        ib_username = app.config["IB_USERNAME"]
        ib_password = app.config["IB_PASSWORD"]
        url = f"https://{ib_server}/wapi/v2.10.5/"

        app.logger.info("Checking for address info")
        session = requests.Session()
        # requests.packages.urllib3.disable_warnings()
        urllib3.disable_warnings(category=urllib3.exceptions.InsecureRequestWarning)
        params = {
            "_return_fields": "comment,network,network_view,members,extattrs,vlans.id,options",
            "_inheritance": True,
            "contains_address": ip_address,
        }
        if ipaddr.version == 6:
            object_type = "ipv6network"
        else:
            object_type = "network"
        # print("Using {} with {}".format(url,params))
        # response = session.get("{}network".format(url), params=params, auth=(ib_username, ib_password), verify=False)  # pylint: disable=line-too-long
        response = session.get(
            f"{url}{object_type}",
            params=params,
            auth=(ib_username, ib_password),
            verify=False,
        )  # pylint: disable=line-too-long
        app.logger.debug(f"{response}")
        if response.status_code != 200:
            app.logger.warning(f"query failed {response}")
        else:
            network_list = response.json()
            app.logger.debug(f"network details: {network_list}")

        if len(network_list) == 1:
            execution_time = time.time() - start_time
            app.logger.debug(f"get_network complete in {execution_time} seconds")
            return network_list[0]
        # else:
        #     execution_time = time.time() - start_time
        #     app.logger.debug(f"get_network complete in {execution_time} seconds")
        #     return {}
        execution_time = time.time() - start_time
        app.logger.debug(f"get_network complete in {execution_time} seconds")
        return {}

    # else:
    #     execution_time = time.time() - start_time
    #     app.logger.debug(f"get_network complete in {execution_time} seconds")
    #     return {}
    execution_time = time.time() - start_time
    app.logger.debug(f"get_network complete in {execution_time} seconds")
    return {}


def get_address_objects(ip_address):
    """Find Infoblox records"""
    start_time = time.time()
    app.logger.debug(f"get_address_objects {ip_address}")

    # make sure we have a valid ip address
    try:
        ipaddr = ipaddress.ip_address(ip_address)
    except ValueError:
        app.logger.warn(f"{ip_address} is not a valid ip address")
        return {}

    if is_campus_ip(ip_address):
        # Do the lookup only if we think this is a campus address
        ib_server = app.config["IB_SERVER"]
        ib_username = app.config["IB_USERNAME"]
        ib_password = app.config["IB_PASSWORD"]
        url = f"https://{ib_server}/wapi/v2.10.5/"

        session = requests.Session()
        # requests.packages.urllib3.disable_warnings()
        urllib3.disable_warnings(category=urllib3.exceptions.InsecureRequestWarning)
        params = {
            "network_view": "default",
            "_return_fields+": "discovered_data,extattrs,fingerprint,ms_ad_user_data",
            "ip_address": ip_address,
        }
        if ipaddr.version == 6:
            object_type = "ipv6address"
        else:
            object_type = "ipv4address"
        # response = session.get("{}ipv4address".format(url), params=params, auth=(ib_username, ib_password), verify=False)  # pylint: disable=line-too-long
        response = session.get(
            f"{url}{object_type}",
            params=params,
            auth=(ib_username, ib_password),
            verify=False,
        )  # pylint: disable=line-too-long
        app.logger.debug(f"{response}")
        if response.status_code != 200:
            address_list = None
            app.logger.warn(f"{object_type} query failed {response}")
        else:
            address_list = response.json()
            app.logger.debug(f"{object_type} details: {address_list}")

        if address_list is None:
            execution_time = time.time() - start_time
            app.logger.debug(
                f"getAddressObject NONE complete in {execution_time} seconds"
            )
            return {}
        elif len(address_list) == 1:
            execution_time = time.time() - start_time
            app.logger.debug(f"getAddressObject complete in {execution_time} seconds")
            return address_list[0]
        # else:
        #     execution_time = time.time() - start_time
        #     app.logger.debug(f"getAddressObject complete in {execution_time} seconds")
        #     return {}
        execution_time = time.time() - start_time
        app.logger.debug(f"getAddressObject complete in {execution_time} seconds")
        return {}

    # else:
    #     execution_time = time.time() - start_time
    #     app.logger.debug(f"getAddressObject complete in {execution_time} seconds")
    #     return {}
    execution_time = time.time() - start_time
    app.logger.debug(f"getAddressObject complete in {execution_time} seconds")
    return {}


def get_ip_location(ip_address):
    """
    Get location data for the IP
    Currently using https://iplocation.net
    Other options: https://ipapi.co/
    """
    start_time = time.time()
    app.logger.debug(f"get_ip_location {ip_address}")

    # make sure we have a valid ip address
    try:
        ipaddr = ipaddress.ip_address(ip_address)
    except ValueError:
        app.logger.warn(f"{ip_address} is not a valid ip address")
        return {}

    if not ipaddr.is_private:
        # Do not attempt this with private IP addresses
        api_url = "https://api.iplocation.net/?ip="
        session = requests.Session()
        try:
            response = session.get(f"{api_url}{ip_address}", timeout=3)
        except requests.ReadTimeout:
            # Something went wrong, return no data
            app.logger.warn("unable to query location api")
            return {}

        if response.status_code != 200:
            app.logger.warn(f"iplocation query failed {response}")
            execution_time = time.time() - start_time
            app.logger.debug(f"get_ip_location complete in {execution_time} seconds")
            return {}

        iplocation = response.json()
        app.logger.debug(f"iplocation details: {iplocation}")
        execution_time = time.time() - start_time
        app.logger.debug(f"get_ip_location complete in {execution_time} seconds")
        return iplocation

    execution_time = time.time() - start_time
    app.logger.debug(f"get_ip_location complete in {execution_time} seconds")
    return {}
