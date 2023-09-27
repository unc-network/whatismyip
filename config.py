"""
Basic configuration file
"""
import os

class Config():   # pylint: disable=too-few-public-methods
    """
    Basic flask config
    """
    DEBUG = False
    TESTING = False

    SECRET_KEY = os.getenv(
        'FLASK_SECRET_KEY',
        # safe value used for development when FLASK_SECRET_KEY might not be set
        '9e4@&tw46$l31)zrqe3wi+-slqm(ruvz&se0^%9#6(_w3ui!c0'
    )

class ProductionConfig(Config): # pylint: disable=too-few-public-methods
    """
    Production flask config
    """
    pass

class DevelopmentConfig(Config):    # pylint: disable=too-few-public-methods
    """
    Development flask config
    """
    DEBUG = True

class TestingConfig(Config):    # pylint: disable=too-few-public-methods
    """
    Testing flask config
    """
    TESTING = True
