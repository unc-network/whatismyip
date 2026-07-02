"""Main blueprint — home page and split-stack redirect hook."""

import os
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    Response,
    current_app,
    make_response,
    redirect,
    render_template,
    request,
)

from whatismyip.utils import get_client_address, is_campus_ip

bp = Blueprint("main", __name__)


def _configured_hostname(url: str) -> str:
    """Return the lowercase hostname component for a configured URL."""
    return (urlsplit(url).hostname or "").lower()


@bp.before_app_request
def redirect_split_stack_hosts_to_primary() -> Response | None:
    """Redirect ipv4/ipv6 hostnames to the primary site, except for /hostinfo."""
    if request.path == "/hostinfo":
        return None

    incoming_host = (request.host.split(":", 1)[0] or "").lower()
    split_stack_hosts = {
        _configured_hostname(current_app.config["IPV4_SERVER_URL"]),
        _configured_hostname(current_app.config["IPV6_SERVER_URL"]),
    }

    if incoming_host in ("127.0.0.1", "localhost"):
        return None

    if incoming_host not in split_stack_hosts:
        return None

    primary = urlsplit(current_app.config["SERVER_URL"])
    target = f"{primary.scheme}://{primary.netloc}{request.path}"
    if request.query_string:
        target = f"{target}?{request.query_string.decode()}"
    return redirect(target, code=308)


@bp.route("/")
def home() -> Response:
    """Display the base homepage with IP address information."""
    data = {}

    forwarded_for = request.environ.get("HTTP_X_FORWARDED_FOR", None)
    remote_address = request.environ.get("REMOTE_ADDR", None)

    tmp_forwarded_for = os.getenv("FORWARDED_FOR", forwarded_for)
    client_address = get_client_address(remote_address, tmp_forwarded_for)
    data["client_address"] = (
        os.getenv("CLIENT_ADDRESS") or os.getenv("CLIENT_ADDRESS_V4") or client_address
    )
    current_app.logger.info(
        f"Home view from {client_address} with forwarded_for {tmp_forwarded_for}"
    )

    data["is_campus"] = is_campus_ip(data["client_address"])
    current_app.logger.debug(
        f"Client address {client_address} is campus IP {data['is_campus']}"
    )

    data["ipv4_url"] = current_app.config["IPV4_SERVER_URL"]
    data["ipv6_url"] = current_app.config["IPV6_SERVER_URL"]
    data["google_maps_api_key"] = current_app.config["GOOGLE_MAPS_API_KEY"]
    data["map_provider"] = current_app.config.get("MAP_PROVIDER", "leaflet")
    data["dns_security_test_url"] = current_app.config.get("DNS_SECURITY_TEST_URL", "")
    data["simulate"] = bool(request.args.get("simulate"))

    resp = make_response(render_template("home.html", context=data))
    if not data["simulate"]:
        resp.cache_control.public = True
        resp.cache_control.max_age = 300
    return resp
