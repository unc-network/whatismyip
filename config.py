"""
Basic configuration file
"""

import os


class Config:  # pylint: disable=too-few-public-methods
    """
    Basic flask config
    """

    DEBUG = False
    TESTING = False

    SECRET_KEY = os.getenv(
        "FLASK_SECRET_KEY",
        # safe value used for development when FLASK_SECRET_KEY might not be set
        "9e4@&tw46$l31)zrqe3wi+-slqm(ruvz&se0^%9#6(_w3ui!c0",
    )

    SERVER_URL = "http://127.0.0.1:5000"
    IPV4_SERVER_URL = "http://127.0.0.1:5000"
    IPV6_SERVER_URL = "http://127.0.0.1:5000"

    # Infoblox data
    IB_SERVER = "http://127.0.0.1"
    IB_USERNAME = "admin"
    IB_PASSWORD = "infoblox"


class ProductionConfig(Config):  # pylint: disable=too-few-public-methods
    """
    Production flask config
    """

    LOG_LEVEL = "INFO"


class DevelopmentConfig(Config):  # pylint: disable=too-few-public-methods
    """
    Development flask config
    """

    DEBUG = True


class TestingConfig(Config):  # pylint: disable=too-few-public-methods
    """
    Testing flask config
    """

    TESTING = True
