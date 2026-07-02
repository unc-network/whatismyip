"""Pages blueprint — static informational pages, file serving, and error handlers."""

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
)

bp = Blueprint("pages", __name__)


def _cacheable(template: str) -> Response:
    """Render a template with a short public Cache-Control header."""
    resp = make_response(render_template(template))
    resp.cache_control.public = True
    resp.cache_control.max_age = 300
    return resp


@bp.route("/health")
@bp.route("/about")
def about() -> Response:
    """Display a basic webpage with about information."""
    return _cacheable("about.html")


@bp.route("/about/")
def about_redirect() -> Response:
    return redirect("/about", code=308)


@bp.route("/faq")
def faq() -> Response:
    """Display the FAQ page."""
    return _cacheable("faq.html")


@bp.route("/faq/")
def faq_redirect() -> Response:
    return redirect("/faq", code=308)


@bp.route("/speedtest")
def speedtest() -> Response:
    """Display the dedicated speed test page."""
    return _cacheable("speedtest.html")


@bp.route("/speedtest/")
def speedtest_redirect() -> Response:
    return redirect("/speedtest", code=308)


@bp.route("/connectivity")
def connectivity() -> Response:
    """Display the connectivity test page."""
    targets = current_app.config.get("CONNECTIVITY_TARGETS", [])
    resp = make_response(
        render_template("connectivity.html", connectivity_targets=targets)
    )
    resp.cache_control.public = True
    resp.cache_control.max_age = 300
    return resp


@bp.route("/connectivity/")
def connectivity_redirect() -> Response:
    return redirect("/connectivity", code=308)


@bp.route("/favicon.ico")
@bp.route("/robots.txt")
@bp.route("/sitemap.xml")
def static_from_root() -> Response:
    """Serve root-level static files."""
    return send_from_directory(
        current_app.static_folder or current_app.root_path, request.path[1:]
    )


@bp.route("/<path:filename>")
def indexnow_key_file(filename: str) -> Response:
    """Serve the IndexNow key verification file from config.toml."""
    key = current_app.config.get("INDEXNOW_KEY", "")
    if key and filename == f"{key}.txt":
        return key, 200, {"Content-Type": "text/plain; charset=utf-8"}
    abort(404)


@bp.app_errorhandler(404)
def page_not_found(e: Exception) -> tuple[str, int]:
    return render_template("404.html"), 404


@bp.app_errorhandler(500)
def internal_server_error(e: Exception) -> tuple[str, int]:
    return render_template("500.html"), 500
