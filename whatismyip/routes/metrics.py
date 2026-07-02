"""Metrics blueprint — aggregate usage dashboard."""

from flask import Blueprint, current_app, render_template, request

from whatismyip.db import get_metrics_dashboard

bp = Blueprint("metrics", __name__)


@bp.route("/metrics")
def metrics():
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
    return render_template(
        "metrics.html",
        metrics=get_metrics_dashboard(),
    )
