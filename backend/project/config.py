import os
import logging
from dotenv import load_dotenv


basedir = os.path.abspath(os.path.dirname(__file__))  
parent_dir = os.path.dirname(os.path.dirname(basedir)) 
dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path)


# services/users/project/config.py
class BaseConfig:
    """Base configuration"""

    TESTING = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get("SECRET_KEY")
    DEBUG_TB_ENABLED = False
    DEBUG_TB_INTERCEPT_REDIRECTS = False
    BCRYPT_LOG_ROUNDS = 13
    TOKEN_EXPIRATION_DAYS = 30
    TOKEN_EXPIRATION_SECONDS = 0
    
    # Logging configuration
    LOG_LEVEL = logging.INFO
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT', 'false').lower() == 'true'


class DevelopmentConfig(BaseConfig):
    """Development configuration"""

    TESTING = True

    db_user = os.environ.get("DB_USER")
    db_password = os.environ.get("DB_PASSWORD")
    db_url = f"{os.environ.get('DB_URL')}:{os.environ.get('DB_PORT')}/{os.environ.get('DB_NAME')}"  # e.g., "db:5432/dev"

    SQLALCHEMY_DATABASE_URI = f"postgresql://{db_user}:{db_password}@{db_url}"
    DEBUG_TB_ENABLED = True
    BCRYPT_LOG_ROUNDS = 4
    LOG_LEVEL = logging.DEBUG


class TestingConfig(BaseConfig):
    """Testing configuration"""

    TESTING = True
    db_user = os.environ.get("DB_USER")
    db_password = os.environ.get("DB_PASSWORD")
    db_url = f"{os.environ.get('DB_URL')}:{os.environ.get('DB_PORT')}/{os.environ.get('DB_NAME')}"  # e.g., "db:5432/dev"

    SQLALCHEMY_DATABASE_URI = f"postgresql://{db_user}:{db_password}@{db_url}"
    BCRYPT_LOG_ROUNDS = 4
    TOKEN_EXPIRATION_DAYS = 0
    TOKEN_EXPIRATION_SECONDS = 3
    LOG_LEVEL = logging.WARNING


class ProductionConfig(BaseConfig):
    """Production configuration"""

    db_user = os.environ.get("DB_USER")
    db_password = os.environ.get("DB_PASSWORD")
    db_url = f"{os.environ.get('DB_URL')}:{os.environ.get('DB_PORT')}/{os.environ.get('DB_NAME')}"  # e.g., "db:5432/dev"

    SQLALCHEMY_DATABASE_URI = f"postgresql://{db_user}:{db_password}@{db_url}"
    LOG_LEVEL = logging.ERROR
    LOG_TO_STDOUT = True
