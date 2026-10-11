import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_debugtoolbar import DebugToolbarExtension
from flask_cors import CORS
from flask_migrate import Migrate
from project.logger import get_logger
from project.middleware import setup_request_logging

from dotenv import load_dotenv

toolbar = DebugToolbarExtension()
migrate = Migrate()
bcrypt = Bcrypt()
db = SQLAlchemy()  # Init db global, attach sau khi create_app
load_dotenv()


def create_app():
    app = Flask(__name__)

    # enable CORS
    CORS(app, resources={r"/*": {"origins": "*"}})

    # Default config nếu env không set, tránh fai
    app_settings = os.getenv("APP_SETTINGS", "project.config.DevelopmentConfig")
    app.config.from_object(app_settings)

    # Setup logging
    logger = get_logger("flask_app", app.config.get("LOG_LEVEL"))
    logger.info(f"Starting application with config: {app_settings}")
    logger.info(f"Starting application with Log Level: {app.config.get('LOG_LEVEL')}")
    # Store logger in app context for easy access
    app.logger_instance = logger

    # Attach db vào app ở đây, an toàn hơn
    db.init_app(app)
    toolbar.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)

    logger.info("Database and extensions initialized")

    # Register blueprint với prefix /users

    # Users
    from project.api.users import users_blueprint

    app.register_blueprint(users_blueprint, url_prefix="/api/users")
    logger.info("Users blueprint registered")

    from project.api.auth import auth_blueprint

    app.register_blueprint(auth_blueprint, url_prefix="/api/auth")
    logger.info("Auth blueprint registered")

    from project.api.exercises import exercises_blueprint

    app.register_blueprint(exercises_blueprint, url_prefix="/api/exercises")
    logger.info("Exercises blueprint registered")

    from project.api.scores import scores_blueprint

    app.register_blueprint(scores_blueprint, url_prefix="/api/scores")
    logger.info("Scores blueprint registered")

    # Setup request logging middleware
    setup_request_logging(app)
    logger.info("Request logging middleware setup completed")

    # shell context for flask cli
    app.shell_context_processor({"app": app, "db": db})

    logger.info("Application setup completed successfully")
    return app
