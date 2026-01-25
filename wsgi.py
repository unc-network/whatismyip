"""
WSGI config for project
"""

# import os
# from dotenv import load_dotenv

# import logging
# from flask import Flask
from whatismyip import app as application

# load dotenv in the base root
# APP_ROOT = os.path.join(os.path.dirname(__file__), '..')   # refers to application_top
# dotenv_path = os.path.join(APP_ROOT, '.env')
# load_dotenv(dotenv_path)

# app = Flask(__name__)

# if __name__ != '__main__':
#     gunicorn_logger = logging.getLogger('gunicorn.error')
#     app.logger.handlers = gunicorn_logger.handlers
#     app.logger.setLevel(gunicorn_logger.level)

if __name__ == "__main__":
    application.run()
