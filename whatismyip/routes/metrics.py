"""Metrics blueprint — aggregate usage dashboard."""

from flask import Blueprint, Response, current_app, render_template, request

from whatismyip.db import get_metrics_dashboard, log_page_view

bp = Blueprint("metrics", __name__)


@bp.route("/metrics")
def metrics() -> Response | tuple[str, int, dict[str, str]]:
    """Display aggregate usage metrics."""
    username = current_app.config.get("METRICS_USERNAME", "")
    password = current_app.config.get("METRICS_PASSWORD", "")
    if username and password:
        auth = request.authorization
        if not auth or auth.username != username or auth.password != password:
            return (
                "Unauthorized",
                401,
                {"WWW-Authenticate": 'Basic realm="Metrics"'},
            )
    log_page_view("Metrics")
    return render_template(
        "metrics.html",
        metrics=get_metrics_dashboard(),
    )
