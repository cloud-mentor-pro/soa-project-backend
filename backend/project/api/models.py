# services/users/project/api/models.py
from datetime import datetime, timezone, timedelta
import jwt

from flask import current_app

from project import db, bcrypt
from project.logger import get_logger
from sqlalchemy.types import JSON

# Get logger for this module
logger = get_logger("models")


class Score(db.Model):
    __tablename__ = "scores"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False)
    exercise_id = db.Column(db.Integer, nullable=False)
    answer = db.Column(db.Text, nullable=True)
    results = db.Column(JSON, nullable=True)
    user_results = db.Column(JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def __init__(
        self, user_id, exercise_id, answer=None, results=None, user_results=None
    ):
        logger.debug(
            f"Creating Score: user_id={user_id}, exercise_id={exercise_id}, answer length={len(answer) if answer else None}, results={results}, user_results={user_results}"
        )
        self.user_id = user_id
        self.exercise_id = exercise_id
        self.answer = answer
        self.results = results
        self.user_results = user_results

    def to_json(self):
        logger.debug(f"Converting Score {self.id} to JSON")
        return {
            "id": self.id,
            "user_id": self.user_id,
            "exercise_id": self.exercise_id,
            "answer": self.answer,
            "results": self.results,
            "user_results": self.user_results,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def update_score(self, answer, results, user_results):
        """Update score with logging"""
        logger.info(
            f"Updating score {self.id} for user {self.user_id}, exercise {self.exercise_id}: results {self.results} -> {results}"
        )
        old_results = self.results
        self.answer = answer
        self.results = results
        self.user_results = user_results

        try:
            db.session.commit()
            logger.info(f"Score {self.id} updated successfully")
        except Exception as e:
            logger.error(f"Failed to update score {self.id}: {str(e)}")
            logger.exception("Full traceback:")
            db.session.rollback()
            raise e


class Exercise(db.Model):
    __tablename__ = "exercises"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.String, nullable=False)
    difficulty = db.Column(db.Integer, nullable=False)
    test_cases = db.Column(JSON, nullable=False)
    solutions = db.Column(JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def __init__(self, title, body, difficulty, test_cases, solutions):
        logger.debug(
            f"Creating Exercise: title={title}, body length={len(body)}, difficulty={difficulty}, test_cases count={len(test_cases) if test_cases else 0}"
        )
        self.title = title
        self.body = body
        self.difficulty = difficulty
        self.test_cases = test_cases
        self.solutions = solutions

    def to_json(self):
        logger.debug(f"Converting Exercise {self.id} to JSON")
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "difficulty": self.difficulty,
            "test_cases": self.test_cases,
            "solutions": self.solutions,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def create_exercise(cls, title, body, difficulty, test_cases, solutions):
        """Create exercise with logging"""
        logger.info(f"Creating new exercise with title: {title}")

        try:
            exercise = cls(
                title=title,
                body=body,
                difficulty=difficulty,
                test_cases=test_cases,
                solutions=solutions,
            )
            db.session.add(exercise)
            db.session.commit()
            logger.info(f"Exercise {exercise.id} created successfully")
            return exercise
        except Exception as e:
            logger.error(f"Failed to create exercise: {str(e)}")
            logger.exception("Full traceback:")
            db.session.rollback()
            raise e


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(128), unique=True, nullable=False)
    email = db.Column(db.String(128), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    admin = db.Column(db.Boolean, default=False, nullable=False)
    profile_image_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def __init__(self, username, email, password, admin=False, active=True):
        logger.debug(f"Creating User: username={username}, email={email}")
        self.username = username
        self.email = email
        self.admin = admin
        self.active = active

        try:
            # Hash password
            logger.debug("Hashing user password")
            self.password = bcrypt.generate_password_hash(
                password, current_app.config.get("BCRYPT_LOG_ROUNDS")
            ).decode()
            logger.debug("Password hashed successfully")
        except Exception as e:
            logger.error(f"Failed to hash password for user {username}: {str(e)}")
            raise e

    def to_json(self):
        logger.debug(f"Converting User {self.id} ({self.username}) to JSON")
        
        # Convert S3 URI to presigned URL if profile image exists
        profile_image_url = None
        if self.profile_image_url:
            from project.api.image_utils import generate_presigned_url_from_s3_key
            success, presigned_url_or_error = generate_presigned_url_from_s3_key(self.profile_image_url)
            if success:
                profile_image_url = presigned_url_or_error
        
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "active": self.active,
            "admin": self.admin,
            "profile_image_url": profile_image_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def encode_auth_token(self, user_id):
        """Generates the auth token"""
        logger.debug(
            f"Encoding auth token for user_id: {user_id} (type: {type(user_id)})"
        )

        try:
            expiration_days = current_app.config.get("TOKEN_EXPIRATION_DAYS")
            expiration_seconds = current_app.config.get("TOKEN_EXPIRATION_SECONDS")

            payload = {
                "exp": datetime.now(timezone.utc)
                + timedelta(days=expiration_days, seconds=expiration_seconds),
                "iat": datetime.now(timezone.utc),
                "sub": str(user_id),  # Convert to string for JWT compatibility
            }

            token = jwt.encode(
                payload, current_app.config.get("SECRET_KEY"), algorithm="HS256"
            )

            logger.debug(f"Auth token encoded successfully for user_id: {user_id}")
            logger.debug(
                f"Token expires in {expiration_days} days and {expiration_seconds} seconds"
            )
            return token

        except Exception as e:
            logger.error(f"Failed to encode auth token for user_id {user_id}: {str(e)}")
            logger.exception("Full traceback:")
            return e

    @staticmethod
    def decode_auth_token(auth_token):
        """
        Decodes the auth token - :param auth_token: - :return: integer|string
        """
        logger.debug("Decoding auth token")

        try:
            payload = jwt.decode(
                auth_token,
                current_app.config.get("SECRET_KEY"),
                algorithms=["HS256"],
            )
            user_id_str = payload["sub"]
            logger.debug(
                f"Token payload sub: {user_id_str} (type: {type(user_id_str)})"
            )

            # Convert string back to integer
            user_id = int(user_id_str)
            logger.debug(
                f"Auth token decoded successfully for user_id: {user_id} (type: {type(user_id)})"
            )
            return user_id

        except jwt.ExpiredSignatureError:
            logger.warning("Auth token expired")
            return "Signature expired. Please log in again."

        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid auth token: {str(e)}")
            return "Invalid token. Please log in again."

        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid user_id format in token: {str(e)}")
            return "Invalid token. Please log in again."

        except Exception as e:
            logger.error(f"Unexpected error decoding auth token: {str(e)}")
            logger.exception("Full traceback:")
            return "Invalid token. Please log in again."

    def deactivate_user(self):
        """Deactivate user with logging"""
        logger.info(f"Deactivating user {self.username} ({self.email})")

        try:
            self.active = False
            db.session.commit()
            logger.info(f"User {self.username} deactivated successfully")
        except Exception as e:
            logger.error(f"Failed to deactivate user {self.username}: {str(e)}")
            logger.exception("Full traceback:")
            db.session.rollback()
            raise e

    def activate_user(self):
        """Activate user with logging"""
        logger.info(f"Activating user {self.username} ({self.email})")

        try:
            self.active = True
            db.session.commit()
            logger.info(f"User {self.username} activated successfully")
        except Exception as e:
            logger.error(f"Failed to activate user {self.username}: {str(e)}")
            logger.exception("Full traceback:")
            db.session.rollback()
            raise e

    def make_admin(self):
        """Grant admin privileges with logging"""
        logger.info(f"Granting admin privileges to user {self.username} ({self.email})")

        try:
            self.admin = True
            db.session.commit()
            logger.info(f"User {self.username} granted admin privileges successfully")
        except Exception as e:
            logger.error(
                f"Failed to grant admin privileges to user {self.username}: {str(e)}"
            )
            logger.exception("Full traceback:")
            db.session.rollback()
            raise e

    def revoke_admin(self):
        """Revoke admin privileges with logging"""
        logger.info(
            f"Revoking admin privileges from user {self.username} ({self.email})"
        )

        try:
            self.admin = False
            db.session.commit()
            logger.info(
                f"Admin privileges revoked from user {self.username} successfully"
            )
        except Exception as e:
            logger.error(
                f"Failed to revoke admin privileges from user {self.username}: {str(e)}"
            )
            logger.exception("Full traceback:")
            db.session.rollback()
            raise e

    @classmethod
    def create_user(cls, username, email, password):
        """Create user with logging"""
        logger.info(f"Creating new user: {username} ({email})")

        try:
            user = cls(username=username, email=email, password=password)
            db.session.add(user)
            db.session.commit()
            logger.info(f"User {username} created successfully with ID: {user.id}")
            return user
        except Exception as e:
            logger.error(f"Failed to create user {username} ({email}): {str(e)}")
            logger.exception("Full traceback:")
            db.session.rollback()
            raise e

    @classmethod
    def find_by_email(cls, email):
        """Find user by email with logging"""
        logger.debug(f"Finding user by email: {email}")

        try:
            user = cls.query.filter_by(email=email).first()
            if user:
                logger.debug(f"User found: {user.username} ({email})")
            else:
                logger.debug(f"No user found with email: {email}")
            return user
        except Exception as e:
            logger.error(f"Error finding user by email {email}: {str(e)}")
            logger.exception("Full traceback:")
            return None

    @classmethod
    def find_by_username(cls, username):
        """Find user by username with logging"""
        logger.debug(f"Finding user by username: {username}")

        try:
            user = cls.query.filter_by(username=username).first()
            if user:
                logger.debug(f"User found: {username} ({user.email})")
            else:
                logger.debug(f"No user found with username: {username}")
            return user
        except Exception as e:
            logger.error(f"Error finding user by username {username}: {str(e)}")
            logger.exception("Full traceback:")
            return None