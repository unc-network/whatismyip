"""
Basic App
"""

import os
import logging
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    make_response,
    send_from_directory,
)
from flask_cors import CORS
from flask_fontawesome import FontAwesome
from dotenv import load_dotenv
from user_agents import parse
from dns import resolver, reversename
import dns.exception

from whatismyip.utils import *

# from whatismyip import views

# load dotenv in the base root
APP_ROOT = os.path.join(os.path.dirname(__file__), "..")  # refers to application_top
dotenv_path = os.path.join(APP_ROOT, ".env")
load_dotenv(dotenv_path)

app = Flask(__name__)
app.config.from_object("config.Config")
app.config.from_prefixed_env()

# logger = create_logger(app)
# logger.setLevel(logging.INFO)

# Dual stack clients need to access both the v6 and v4 versions of this site.
# Allow the https v6 site to call the https v4 version of the api.
# CORS(app, resources={r"/hostinfo": {"origins": ["https://whatismyip.unc.edu"]}})
CORS(app, resources={r"/hostinfo": {"origins": [app.config["SERVER_URL"]]}})
app.logger.debug(
    f"URL: dual stack {app.config['SERVER_URL']}, ipv4-only {app.config['IPV4_SERVER_URL']}, ipv6-only {app.config['IPV6_SERVER_URL']}"
)

fa = FontAwesome(app)


# Routes
@app.route("/")
def home():
    """Display the base homepage with IP address information."""
    data = {}
    client_address = None

    # get the request headers
    forwarded_for = request.environ.get("HTTP_X_FORWARDED_FOR", None)
    remote_address = request.environ.get("REMOTE_ADDR", None)

    # Check for PROXY usage
    tmp_forwarded_for = os.getenv("FORWARDED_FOR", forwarded_for)
    client_address = get_client_address(remote_address, tmp_forwarded_for)
    data["client_address"] = os.getenv("CLIENT_ADDRESS", client_address)
    app.logger.warning( f"Home view from {client_address} with forwarded_for {tmp_forwarded_for}")

    # Add the ipv4/ipv6 specific test urls
    data["ipv4_url"] = app.config["IPV4_SERVER_URL"]
    data["ipv6_url"] = app.config["IPV6_SERVER_URL"]

    return render_template("home.html", context=data)


@app.route("/hostinfo.php")
@app.route("/hostinfo")
def hostinfo():
    """Return JSON structure with IP address information."""
    data = {}

    # variables to help debug
    headers = dict(request.headers)

    # get the request headers
    forwarded_for = request.environ.get("HTTP_X_FORWARDED_FOR", None)
    remote_address = request.environ.get("REMOTE_ADDR", None)
    remote_port = request.environ.get("REMOTE_PORT", None)
    request_method = request.environ.get("REQUEST_METHOD", None)
    server_protocol = request.environ.get("SERVER_PROTOCOL", None)
    http_user_agent = request.environ.get("HTTP_USER_AGENT", None)

    # build the main data dictionary
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

    # Parse out the actual client ip address from header data
    if data["forwarded_for"]:
        # Proxy was used
        # fwd_list = data['forwarded_for'].split(',')
        # data['address'] = fwd_list[0]   # the original client should be the first ip
        data["address"] = get_forwarded_address( data["forwarded_for"])
    else:
        # No proxy was used
        data["address"] = data["remote_address"]
    # data["address"] = os.getenv("CLIENT_ADDRESS", data['remote_address'])
    # data["proxy_detected"] = os.getenv("PROXY_DETECTED", data['proxy_detected'])
    app.logger.info(
        f"hostinfo view from {data['address']} with forwarded_for {data['forwarded_for']}"
    )

    # calculate the IP address basics at the start
    ip = ipaddress.ip_address(str(data["address"]))

    # collect device information
    # user_agent = parse(http_user_agent)
    data["user_device"] = parse(data["user_agent"]).__str__()

    # collect dns data
    reverse_addr = reversename.from_address(data["address"])
    try:
        dns_response = resolver.query(reverse_addr, "PTR")
        for val in dns_response:
            app.logger.debug(
                f"PTR {val.to_text()}"
            )  # pylint: disable=logging-fstring-interpolation
            data["ptr"] = val.to_text()
    except dns.exception.DNSException:
        app.logger.warning("reverse DNS lookup failed")

    # collect isp info
    if ip.is_global:
        iplocation = get_ip_location(data["address"])

        # ipwhois = getWhoIs( data['client_address'])
        # data['ipwhois'] = ipwhois
    else:
        # non-global addresses get a default location of campus
        iplocation = {
            "country_code2": "US",
            "country_name": "United States of America",
            "ip": str(ip),
            "ip_number": None,
            "ip_version": ip.version,
            "isp": "University of North Carolina at Chapel Hill",
            "response_code": None,
            "response_message": None,
        }
    data["iplocation"] = iplocation

    # collect information about the network for this address
    network = get_network(data["address"])
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
        # collect network data to display
        net_details["cidr"] = network.get("network", None)
        net_details["comment"] = network.get("comment", "")

        # calculate the IP address basics
        ip_net = ipaddress.ip_network(net_details["cidr"])
        net_details["ip_version"] = str(ip_net.version)
        net_details["netmask"] = str(ip_net.netmask)
        net_details["prefixlen"] = str(ip_net.prefixlen)

        # collect specific extattr data
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

        # iterate members to get dhcp servers
        for member in network.get("members", []):
            if net_details["ip_version"] == "4":
                net_details["dhcp_servers"].append(member["ipv4addr"])
            else:
                net_details["dhcp_servers"].append(member["ipv6addr"])

        # iterate dhcp options for specific
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

        # collect vlan data to display
        vlan_list = network.get("vlans", None)
        if vlan_list:
            net_details["vlan_id"] = vlan_list[0].get("id", None)
            net_details["vlan_name"] = vlan_list[0].get("name", None)

    data["network"] = net_details

    # collect details about this address
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
    # calculate the IP address basics
    ip = ipaddress.ip_address(str(data["address"]))
    addr_details["ip_version"] = ip.version
    addr_details["is_private"] = ip.is_private
    addr_details["is_global"] = ip.is_global
    addr_details["is_link_local"] = ip.is_link_local

    # Find any address objects
    address_records = get_address_objects(data["address"])
    if address_records:
        addr_details["comment"] = address_records.get("comment", "")
        addr_details["status"] = address_records.get("status", None)
        addr_details["mac"] = address_records.get("mac_address", None)
        addr_details["username"] = address_records.get("username", None)
        addr_details["dhcp_lease_state"] = address_records.get("lease_state", None)
        addr_details["names"] = address_records.get("names", [])
        addr_details["types"] = address_records.get("types", [])
        addr_details["usage"] = address_records.get("usage", [])

        # collect specific extattr data
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

    # build the json response
    message = jsonify(data)
    response = make_response(message)
    return response


@app.route("/health")
@app.route("/about")
def about():
    """Display a basic webpage with about information."""
    return render_template("about.html")


@app.route("/robots.txt")
@app.route("/sitemap.xml")
def static_from_root():
    """Support basic robots and sitemap files"""
    return send_from_directory(app.static_folder, request.path[1:])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
