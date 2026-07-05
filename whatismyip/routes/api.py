"""API blueprint — /hostinfo and /dns-result endpoints."""

import ipaddress
import os
import time

import dns.exception
from dns import resolver, reversename
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    make_response,
    request,
)
from user_agents import parse

from whatismyip.db import log_metrics_event
from whatismyip.infoblox import get_address_objects, get_network
from whatismyip.utils import (
    get_client_address,
    get_ip_location,
    get_nac_info,
    is_campus_ip,
)

bp = Blueprint("api", __name__)

_SIMULATE_HOSTINFO = {
    4: {
        "forwarded_for": "",
        "remote_address": "192.0.2.50",
        "remote_port": "44321",
        "request_method": "GET",
        "server_protocol": "HTTP/1.1",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "proxy_detected": None,
        "client_address": "192.0.2.50",
        "is_campus": True,
        "user_device": {
            "browser": "Chrome",
            "browser_version": "125.0.0",
            "os": "Mac OS X",
            "os_version": "10.15.7",
            "device_family": None,
            "device_brand": None,
            "device_model": None,
            "is_mobile": False,
            "is_tablet": False,
            "is_pc": True,
            "is_bot": False,
        },
        "ptr": "demo-device.net.unc.edu",
        "iplocation": {
            "country_code2": "US",
            "country_name": "United States",
            "ip": "192.0.2.50",
            "ip_number": None,
            "ip_version": 4,
            "isp": "University of North Carolina at Chapel Hill",
            "org": "University of North Carolina at Chapel Hill",
            "asn": "AS36105",
            "region": "North Carolina",
            "response_code": None,
            "response_message": None,
            "city": "Chapel Hill",
            "lat": 35.9049,
            "lon": -79.0469,
            "mobile": False,
            "proxy": False,
            "hosting": False,
        },
        "network": {
            "cidr": "10.23.0.0/16",
            "comment": "Main Campus Eduroam NAT, NAT pool 152.23.158.224/28",
            "ip_version": "4",
            "netmask": "255.255.0.0",
            "prefixlen": "16",
            "contact": None,
            "contact_name": None,
            "contact_email": None,
            "contact_dept": "ITS",
            "cost_center": None,
            "purpose": "Wireless",
            "router_device": "WIFIPAN-WIRELESS-VR",
            "dhcp_servers": [],
            "dhcp_routers": "10.23.0.1",
            "dhcp_dns_servers": ["172.22.255.100", "172.22.255.101"],
            "dhcp_domain_name": "wireless-1x.unc.edu",
            "dhcp_lease_time": None,
            "dhcp_ntp_servers": [],
            "vlan_id": "3101",
            "vlan_name": "Net-Eduroam-Main",
        },
        "address_details": {
            "mac": "00:00:5e:00:53:01",
            "names": ["demo-device.net.unc.edu"],
            "types": ["A"],
            "usage": ["Static"],
            "contact": None,
            "contact_name": None,
            "contact_email": None,
            "contact_dept": None,
            "comment": "Demo device",
        },
        "nac": {
            "endSystem": {
                "lastSeenTime": 1751734800000,
                "macAddress": "00:00:5e:00:53:01",
                "ipAddress": "192.0.2.50",
                "nacApplianceGroupName": "Wireless Meraki",
                "nacProfileName": "Default NAC Profile",
                "nacApplianceIP": "172.29.145.91",
                "policy": "Filter-Id='Enterasys:version=1:policy=Wireless-Meraki'",
                "reason": "Default-Wireless-Meraki",
                "switchIP": "152.23.141.249",
                "switchPortId": "CC-6E-2A-D6-2E-40:eduroam",
                "switchPort": "1",
                "extendedState": "NO_ERROR",
                "connection_type": "wireless",
                "wireless_ap_name": "ITS-0162-AP-Demo",
                "wireless_ap_mac": "CC-6E-2A-D6-2E-40",
                "wireless_ap_tier": "ITS",
                "wireless_ap_bldg_id": "0162",
                "wireless_ssid": "eduroam",
                "wireless_controller": "152.23.141.249",
            },
            "nit_building": {
                "full_name": "Phillips Hall",
                "official_name": "Phillips Hall",
                "building_id": "0162",
                "address": "120 E Cameron Ave Chapel Hill, NC 27514",
                "latitude": 35.9049,
                "longitude": -79.0469,
            },
            "meraki_ap": {
                "name": "ITS-0162-AP-Demo",
                "serial": "Q5BD-SDFT-MDL8",
                "model": "CW9172H",
                "address": "120 E Cameron Ave, Chapel Hill, NC 27514",
                "lat": 35.9049,
                "lon": -79.0469,
                "network_id": "N_401946266742816948",
            },
            "meraki_client": {
                "manufacturer": "Apple",
                "description": "Demo-MacBook-Pro",
                "os": "macOS 15.5",
                "user": "demo@unc.edu",
                "status": "Online",
                "ssid": "eduroam",
                "vlan": "3101",
                "wireless_capabilities": "802.11ax - 2.4 and 5 GHz",
            },
            "meraki_signal": {
                "rssi": -62,
                "snr": 31,
            },
        },
    },
    6: {
        "forwarded_for": "",
        "remote_address": "2001:db8::50",
        "remote_port": "55012",
        "request_method": "GET",
        "server_protocol": "HTTP/1.1",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "proxy_detected": None,
        "client_address": "2001:db8::50",
        "is_campus": True,
        "user_device": {
            "browser": "Chrome",
            "browser_version": "125.0.0",
            "os": "Mac OS X",
            "os_version": "10.15.7",
            "device_family": None,
            "device_brand": None,
            "device_model": None,
            "is_mobile": False,
            "is_tablet": False,
            "is_pc": True,
            "is_bot": False,
        },
        "ptr": "demo-device.net.unc.edu",
        "iplocation": {
            "country_code2": "US",
            "country_name": "United States",
            "ip": "2001:db8::50",
            "ip_number": None,
            "ip_version": 6,
            "isp": "University of North Carolina at Chapel Hill",
            "org": "University of North Carolina at Chapel Hill",
            "asn": "AS36105",
            "region": "North Carolina",
            "response_code": None,
            "response_message": None,
            "city": "Chapel Hill",
            "lat": 35.9049,
            "lon": -79.0469,
            "mobile": False,
            "proxy": False,
            "hosting": False,
        },
        "network": {
            "cidr": "2001:db8::/32",
            "comment": "Demo IPv6 network",
            "ip_version": "6",
            "netmask": None,
            "prefixlen": "32",
            "contact": None,
            "contact_name": None,
            "contact_email": None,
            "contact_dept": "ITS",
            "cost_center": None,
            "purpose": "Wired",
            "router_device": None,
            "dhcp_servers": [],
            "dhcp_routers": None,
            "dhcp_dns_servers": [],
            "dhcp_domain_name": None,
            "dhcp_lease_time": None,
            "dhcp_ntp_servers": [],
            "vlan_id": "100",
            "vlan_name": "ITS-Demo-Users",
        },
        "address_details": {
            "mac": None,
            "names": ["demo-device.net.unc.edu"],
            "types": ["AAAA"],
            "usage": ["Static"],
            "contact": None,
            "contact_name": None,
            "contact_email": None,
            "contact_dept": None,
            "comment": None,
        },
        "nac": {},
    },
}


@bp.route("/hostinfo")
def hostinfo() -> Response:
    """Return JSON structure with IP address information."""
    simulate = request.args.get("simulate")
    if simulate:
        ip_ver = int(simulate) if simulate in ("4", "6") else 4
        sim_data = dict(_SIMULATE_HOSTINFO[ip_ver])
        sim_data["server_time"] = int(time.time() * 1000)
        return jsonify(sim_data)

    forwarded_for = request.environ.get("HTTP_X_FORWARDED_FOR", None)
    remote_address = request.environ.get("REMOTE_ADDR", None)

    data = {
        "forwarded_for": request.environ.get("HTTP_X_FORWARDED_FOR", ""),
        "remote_address": request.environ.get("REMOTE_ADDR", ""),
        "remote_port": request.environ.get("REMOTE_PORT", ""),
        "request_method": request.environ.get("REQUEST_METHOD", ""),
        "server_protocol": request.environ.get("SERVER_PROTOCOL", ""),
        "user_agent": request.environ.get("HTTP_USER_AGENT", ""),
        "network": "",
        "proxy_detected": None,
    }

    tmp_forwarded_for = os.getenv("FORWARDED_FOR", forwarded_for)
    client_address = get_client_address(remote_address, tmp_forwarded_for)

    _general = os.getenv("CLIENT_ADDRESS")
    _v4 = os.getenv("CLIENT_ADDRESS_V4")
    _v6 = os.getenv("CLIENT_ADDRESS_V6")
    if _general:
        data["client_address"] = _general
    elif _v4 or _v6:
        try:
            conn_ip = ipaddress.ip_address(client_address)
            if conn_ip.version == 6 and conn_ip.ipv4_mapped:
                conn_ver = 4
            else:
                conn_ver = conn_ip.version
            if conn_ver == 6 and _v6:
                data["client_address"] = _v6
            elif conn_ver == 4 and _v4:
                data["client_address"] = _v4
            else:
                data["client_address"] = client_address
        except ValueError:
            data["client_address"] = client_address
    else:
        data["client_address"] = client_address

    current_app.logger.info(
        f"Hostinfo view from {data['client_address']} with forwarded_for {tmp_forwarded_for}"
    )

    if not data["client_address"]:
        abort(400)
    ip = ipaddress.ip_address(str(data["client_address"]))

    data["is_campus"] = is_campus_ip(data["client_address"])

    ua = parse(data["user_agent"])
    data["user_device"] = {
        "browser": ua.browser.family,
        "browser_version": ua.browser.version_string,
        "os": ua.os.family,
        "os_version": ua.os.version_string,
        "device_family": ua.device.family if ua.device.family != "Other" else None,
        "device_brand": ua.device.brand,
        "device_model": ua.device.model,
        "is_mobile": ua.is_mobile,
        "is_tablet": ua.is_tablet,
        "is_pc": ua.is_pc,
        "is_bot": ua.is_bot,
    }

    reverse_addr = reversename.from_address(data["client_address"])
    try:
        dns_response = resolver.query(reverse_addr, "PTR")
        for val in dns_response:
            current_app.logger.debug(f"PTR {val.to_text()}")
            data["ptr"] = val.to_text()
    except dns.exception.DNSException:
        current_app.logger.debug("reverse DNS lookup failed")

    if ip.is_global:
        try:
            iplocation = get_ip_location(data["client_address"])
        except Exception as error:
            current_app.logger.warning(f"IP location lookup failed: {error}")
            iplocation = None
        if not iplocation:
            iplocation = {
                "country_code2": None,
                "country_name": "Unknown",
                "ip": str(ip),
                "ip_number": None,
                "ip_version": ip.version,
                "isp": "Unknown",
                "response_code": None,
                "response_message": None,
                "city": None,
                "lat": None,
                "lon": None,
            }
    else:
        site_name = current_app.config.get("SITE_NAME", "")
        iplocation = {
            "country_code2": current_app.config.get("SITE_COUNTRY_CODE", ""),
            "country_name": current_app.config.get("SITE_COUNTRY_NAME", ""),
            "ip": str(ip),
            "ip_number": None,
            "ip_version": ip.version,
            "isp": site_name,
            "org": site_name,
            "asn": None,
            "region": current_app.config.get("SITE_REGION") or None,
            "response_code": None,
            "response_message": None,
            "city": current_app.config.get("SITE_CITY", ""),
            "lat": current_app.config.get("SITE_LAT", 0.0),
            "lon": current_app.config.get("SITE_LON", 0.0),
            "mobile": False,
            "proxy": False,
            "hosting": False,
        }
    data["iplocation"] = iplocation

    network = None
    if data["is_campus"]:
        try:
            network = get_network(data["client_address"])
        except Exception as error:
            current_app.logger.warning(f"Network lookup failed: {error}")

    net_details = {
        "cidr": None,
        "comment": "",
        "ip_version": None,
        "netmask": None,
        "prefixlen": None,
        "contact": None,
        "contact_name": None,
        "contact_email": None,
        "contact_dept": None,
        "cost_center": None,
        "purpose": None,
        "router_device": None,
        "dhcp_servers": [],
        "dhcp_routers": None,
        "dhcp_dns_servers": [],
        "dhcp_domain_name": None,
        "dhcp_lease_time": None,
        "dhcp_ntp_servers": [],
        "vlan_id": None,
        "vlan_name": None,
    }
    if network:
        net_details["cidr"] = network.get("network", None)
        net_details["comment"] = network.get("comment", "")

        if net_details["cidr"]:
            ip_net = ipaddress.ip_network(str(net_details["cidr"]))
            net_details["ip_version"] = str(ip_net.version)
            net_details["netmask"] = str(ip_net.netmask)
            net_details["prefixlen"] = str(ip_net.prefixlen)

        net_details["contact"] = (
            network.get("extattrs", {}).get("Admin Onyen", {}).get("value", None)
        )
        net_details["contact_name"] = (
            network.get("extattrs", {}).get("Administrator", {}).get("value", None)
        )
        net_details["contact_email"] = (
            network.get("extattrs", {}).get("Admin Email", {}).get("value", None)
        )
        net_details["contact_dept"] = (
            network.get("extattrs", {}).get("Department", {}).get("value", None)
        )
        net_details["cost_center"] = (
            network.get("extattrs", {}).get("Cost Center", {}).get("value", None)
        )
        net_details["purpose"] = (
            network.get("extattrs", {}).get("Purpose", {}).get("value", None)
        )
        net_details["router_device"] = (
            network.get("extattrs", {}).get("Router Device", {}).get("value", None)
        )

        for member in network.get("members", []):
            if net_details["ip_version"] == "4":
                net_details["dhcp_servers"].append(member["ipv4addr"])
            else:
                net_details["dhcp_servers"].append(member["ipv6addr"])

        options = network.get("options", [])
        for option in options:
            values = option.get("values", [])
            for value in values:
                if value.get("name", "") == "routers":
                    net_details["dhcp_routers"] = value.get("value", None)
                if value.get("name", "") == "domain-name-servers":
                    server_list = value.get("value", "")
                    net_details["dhcp_dns_servers"] = server_list.split(",")
                if value.get("name", "") == "domain-name":
                    net_details["dhcp_domain_name"] = value.get("value", None)
                if value.get("name", "") == "dhcp-lease-time":
                    net_details["dhcp_lease_time"] = value.get("value", None)
                if value.get("name", "") == "ntp-servers":
                    server_list = value.get("value", "")
                    net_details["dhcp_ntp_servers"] = server_list.split(",")

        vlan_list = network.get("vlans", None)
        if vlan_list:
            net_details["vlan_id"] = vlan_list[0].get("id", None)
            net_details["vlan_name"] = vlan_list[0].get("name", None)

    data["network"] = net_details

    if data["is_campus"]:
        if network is None:
            current_app.logger.error(
                f"On-campus IP {data['client_address']} has no matching network in IPAM"
            )
        elif not net_details["purpose"]:
            current_app.logger.warning(
                f"On-campus IP {data['client_address']} matched network "
                f"{net_details['cidr']} with no Purpose defined"
            )

    addr_details = {
        "comment": "",
        "status": None,
        "mac": None,
        "username": None,
        "dhcp_lease_state": None,
        "names": [],
        "types": [],
        "usage": [],
        "contact": None,
        "contact_name": None,
        "contact_email": None,
        "contact_dept": None,
    }
    addr_details["ip_version"] = ip.version
    addr_details["is_private"] = ip.is_private
    addr_details["is_global"] = ip.is_global
    addr_details["is_link_local"] = ip.is_link_local

    address_records = None
    if data["is_campus"]:
        try:
            address_records = get_address_objects(data["client_address"])
        except Exception as error:
            current_app.logger.warning(f"Address lookup failed: {error}")

    if address_records:
        addr_details["comment"] = address_records.get("comment", "")
        addr_details["status"] = address_records.get("status", None)
        addr_details["mac"] = address_records.get("mac_address", None)
        addr_details["username"] = address_records.get("username", None)
        addr_details["dhcp_lease_state"] = address_records.get("lease_state", None)
        addr_details["names"] = address_records.get("names", [])
        addr_details["types"] = address_records.get("types", [])
        addr_details["usage"] = address_records.get("usage", [])
        addr_details["contact"] = (
            address_records.get("extattrs", {})
            .get("Admin Onyen", {})
            .get("value", None)
        )
        addr_details["contact_name"] = (
            address_records.get("extattrs", {})
            .get("Administrator", {})
            .get("value", None)
        )
        addr_details["contact_email"] = (
            address_records.get("extattrs", {})
            .get("Admin Email", {})
            .get("value", None)
        )
        addr_details["contact_dept"] = (
            address_records.get("extattrs", {}).get("Department", {}).get("value", None)
        )

    data["address_details"] = addr_details

    data["nac"] = {}
    if data["is_campus"] and ip.version == 4:
        try:
            nac_data = get_nac_info(data["client_address"], mac=addr_details["mac"])
        except Exception as error:
            current_app.logger.warning(f"NAC info lookup failed: {error}")
            nac_data = None

        if nac_data:
            data["nac"] = nac_data

    log_metrics_event(
        "hostinfo",
        ip_version=ip.version,
        isp=iplocation.get("isp"),
        org=iplocation.get("org"),
        asn=iplocation.get("asn"),
        city=iplocation.get("city"),
        region=iplocation.get("region"),
        country=iplocation.get("country_name") or iplocation.get("country"),
        country_code=iplocation.get("country_code2"),
        is_campus=data["is_campus"],
        network_purpose=net_details.get("purpose"),
        mobile=iplocation.get("mobile"),
        proxy=iplocation.get("proxy"),
        hosting=iplocation.get("hosting"),
    )

    data["server_time"] = int(time.time() * 1000)

    return make_response(jsonify(data))


@bp.route("/dns-result", methods=["POST"])
def dns_result() -> Response:
    """Accept client-reported DNS test results for aggregate metrics."""
    if request.args.get("simulate"):
        return jsonify({"ok": True})
    data = request.get_json(silent=True) or {}
    filtering = data.get("filtering")
    if filtering not in ("active", "inactive", "inconclusive"):
        filtering = None
    log_metrics_event(
        "dns_result",
        dns_filtering=filtering,
        dns_ip=data.get("dns_ip") or None,
        dns_geo=data.get("dns_geo") or None,
        edns_ip=data.get("edns_ip") or None,
        edns_geo=data.get("edns_geo") or None,
    )
    return jsonify({"ok": True})
