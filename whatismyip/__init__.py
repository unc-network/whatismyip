"""What Is My IP — Flask application factory."""

import os

from dotenv import load_dotenv
from flask import Flask, abort
from flask_compress import Compress
from flask_cors import CORS

from whatismyip.db import _DEFAULT_METRICS_DB_PATH, ensure_metrics_store
from whatismyip.site_config import load_site_config

__version__ = "1.12.0"

_APP_ROOT = os.path.join(os.path.dirname(__file__), "..")
load_dotenv(os.path.join(_APP_ROOT, ".env"))


def create_app(test_config: dict | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object("config.Config")
    app.config.from_prefixed_env()
    app.logger.propagate = False
    app.config.setdefault("METRICS_DB_PATH", _DEFAULT_METRICS_DB_PATH)

    if test_config:
        app.config.update(test_config)

    Compress(app)

    CORS(
        app,
        resources={
            "/hostinfo": {
                "origins": [
                    app.config["SERVER_URL"],
                    app.config["IPV4_SERVER_URL"],
                    app.config["IPV6_SERVER_URL"],
                ]
            }
        },
    )

    load_site_config(app)

    @app.context_processor
    def inject_globals():
        return dict(
            site_url=app.config["SERVER_URL"],
            ipv4_url=app.config["IPV4_SERVER_URL"],
            ipv6_url=app.config["IPV6_SERVER_URL"],
            bing_verification_token=app.config.get("BING_VERIFICATION_TOKEN", ""),
            dns_lookup_enabled=app.config.get("DNS_LOOKUP_ENABLED", False),
            app_version=__version__,
        )

    from whatismyip.routes.api import bp as api_bp
    from whatismyip.routes.main import bp as main_bp
    from whatismyip.routes.metrics import bp as metrics_bp
    from whatismyip.routes.pages import bp as pages_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(metrics_bp)

    if app.config.get("TESTING"):

        @app.route("/trigger-500")
        def trigger_500():
            abort(500)

    # Prepare the metrics store during startup rather than on the first request that
    # needs it. The one-time index migration can run for a while against PVC-backed
    # storage, and absorbing that in a request means a user waits on it — long enough
    # to exceed the OpenShift route's 30 s timeout and return 504. Doing it here moves
    # the cost into the deployment window, before the readiness probe passes and the
    # route starts sending traffic. Failure is not fatal: the lazy path in the write
    # and dashboard functions still retries, so a transient storage problem delays
    # metrics rather than preventing the application from serving.
    with app.app_context():
        try:
            ensure_metrics_store()
        except Exception as error:
            app.logger.warning("Metrics store preparation deferred: %s", error)

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    create_app().run(host="0.0.0.0", port=port, debug=True)  # nosec  # fmt: skip
