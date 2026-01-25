"""
WSGI config for project
"""

# import os
# from dotenv import load_dotenv

import logging
from whatismyip import app as application

# load dotenv in the base root
# APP_ROOT = os.path.join(os.path.dirname(__file__), '..')   # refers to application_top
# dotenv_path = os.path.join(APP_ROOT, '.env')
# load_dotenv(dotenv_path)

if __name__ == "__main__":

    gunicorn_logger = logging.getLogger('gunicorn.error')
    application.logger.handlers = gunicorn_logger.handlers
    application.logger.setLevel(gunicorn_logger.level)

    application.run()
