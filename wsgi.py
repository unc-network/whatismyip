"""WSGI entry point."""

import logging

from whatismyip import create_app

application = create_app()

if __name__ != "__main__":
    gunicorn_logger = logging.getLogger("gunicorn.error")
    application.logger.handlers = gunicorn_logger.handlers
    application.logger.setLevel(gunicorn_logger.level)

if __name__ == "__main__":
    application.run()
