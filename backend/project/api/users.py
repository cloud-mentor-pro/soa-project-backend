# services/users/project/api/users.py

from datetime import datetime, timezone
from sqlalchemy import exc, text

from flask import Blueprint, jsonify, request, render_template

from project.api.models import User
from project import db
from project.api.utils import authenticate, is_admin
from project.api.image_utils import validate_image_file, upload_image_to_s3, get_latest_profile_image_url, generate_presigned_url_from_s3_key
from project.logger import get_logger

# Get logger for this module
logger = get_logger('users_api')


users_blueprint = Blueprint("users", __name__, template_folder="./templates")


@users_blueprint.route("/manager", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        db.session.add(User(username=username, email=email, password=password))
        db.session.commit()
    users = User.query.all()
    return render_template("index.html", users=users)


@users_blueprint.route("/ping", methods=["GET"])
def ping_pong():
    """Health check endpoint with database connectivity test"""
    logger.info("Health check requested")
    
    try:
        # Test database connection
        db.session.execute(text('SELECT 1'))
        db.session.commit()
        
        logger.info("Health check successful - database connected")
        return jsonify({
            "status": "success", 
            "message": "pong!",
            "database": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"Health check failed - database error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "pong!",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 503


@users_blueprint.route("/", methods=["GET"])
def get_all_users():
    """Get all users"""
    logger.info("Getting all users")
    try:
        users = User.query.all()
        logger.debug(f"Found {len(users)} users")
        
        # Generate user list with presigned image URLs
        users_data = []
        for user in users:
            user_data = user.to_json()
            # Get presigned URL for profile image if exists
            success, presigned_url_or_error = get_latest_profile_image_url(user.id)
            if success:
                user_data["profile_image_url"] = presigned_url_or_error
            else:
                user_data["profile_image_url"] = None
            users_data.append(user_data)
        
        response_object = {
            "status": "success",
            "data": {"users": users_data},
        }
        logger.info("Successfully retrieved all users")
        return jsonify(response_object), 200
    except Exception as e:
        logger.error(f"Error getting all users: {str(e)}")
        logger.exception("Full traceback:")
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@users_blueprint.route("/<user_id>", methods=["GET"])
def get_single_user(user_id):
    """Get single user details"""
    logger.info(f"Getting user with ID: {user_id}")
    response_object = {"status": "fail", "message": "User does not exist"}
    try:
        user = User.query.filter_by(id=int(user_id)).first()
        if not user:
            logger.warning(f"User with ID {user_id} not found")
            return jsonify(response_object), 404
        else:
            logger.info(f"Successfully found user: {user.username}")
            user_data = user.to_json()
            
            # Get presigned URL for profile image if exists
            success, presigned_url_or_error = get_latest_profile_image_url(user.id)
            if success:
                user_data["profile_image_url"] = presigned_url_or_error
            else:
                user_data["profile_image_url"] = None
            
            response_object = {
                "status": "success",
                "data": user_data,
            }
            return jsonify(response_object), 200
    except ValueError as e:
        logger.error(f"Invalid user ID format: {user_id} - {str(e)}")
        return jsonify(response_object), 404
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {str(e)}")
        logger.exception("Full traceback:")
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@users_blueprint.route("/", methods=["POST"])
@authenticate
def add_user(resp):
    logger.info("Adding new user")
    post_data = request.get_json()
    response_object = {"status": "fail", "message": "Invalid payload."}
    
    if not is_admin(resp):
        logger.warning("Non-admin user attempted to add user")
        response_object["message"] = "You do not have permission to do that."
        return jsonify(response_object), 401
        
    if not post_data:
        logger.warning("Empty payload received for add user")
        return jsonify(response_object), 400
        
    username = post_data.get("username")
    email = post_data.get("email")
    password = post_data.get("password")
    
    logger.debug(f"Attempting to add user: {username} with email: {email}")
    
    try:
        user = User.query.filter_by(email=email).first()
        if not user:
            new_user = User(username=username, email=email, password=password)
            db.session.add(new_user)
            db.session.commit()
            logger.info(f"Successfully added user: {username} ({email})")
            response_object["status"] = "success"
            response_object["message"] = f"{email} was added!"
            response_object["data"] = new_user.to_json()
            return jsonify(response_object), 201
        else:
            logger.warning(f"Attempted to add user with existing email: {email}")
            response_object["message"] = "Sorry. That email already exists."
            return jsonify(response_object), 400
    except exc.IntegrityError as e:
        logger.error(f"Database integrity error adding user {email}: {str(e)}")
        db.session.rollback()
        return jsonify(response_object), 400
    except (exc.IntegrityError, ValueError) as e:
        logger.error(f"Error adding user {email}: {str(e)}")
        logger.exception("Full traceback:")
        db.session.rollback()
        return jsonify(response_object), 400


@users_blueprint.route("/admin_create", methods=["GET","POST"])
@authenticate
def admin_create_user(resp):
    logger.info("Admin creating new user")
    post_data = request.get_json()
    response_object = {"status": "fail", "message": "Invalid payload."}
    
    if not is_admin(resp):
        logger.warning("Non-admin user attempted to admin create user")
        response_object["message"] = "You do not have permission to do that."
        return jsonify(response_object), 401
        
    if not post_data:
        logger.warning("Empty payload received for admin create user")
        return jsonify(response_object), 400
        
    username = post_data.get("username")
    email = post_data.get("email")
    password = post_data.get("password")
    admin_flag = post_data.get("admin", False)
    active_flag = post_data.get("active", True)
    
    logger.debug(f"Attempting to admin create user: {username} with email: {email}, admin: {admin_flag}, active: {active_flag}")
    
    try:
        user = User.query.filter_by(email=email).first()
        if not user:
            new_user = User(username=username, email=email, password=password, admin=admin_flag)
            new_user.active = active_flag
            db.session.add(new_user)
            db.session.commit()
            logger.info(f"Successfully admin created user: {username} ({email}), admin: {admin_flag}, active: {active_flag}")
            response_object["status"] = "success"
            response_object["message"] = f"{email} was added!"
            response_object["data"] = new_user.to_json()
            return jsonify(response_object), 201
        else:
            logger.warning(f"Attempted to admin create user with existing email: {email}")
            response_object["message"] = "Sorry. That email already exists."
            return jsonify(response_object), 400
    except exc.IntegrityError as e:
        logger.error(f"Database integrity error admin creating user {email}: {str(e)}")
        db.session.rollback()
        return jsonify(response_object), 400
    except (exc.IntegrityError, ValueError) as e:
        logger.error(f"Error admin creating user {email}: {str(e)}")
        logger.exception("Full traceback:")
        db.session.rollback()
        return jsonify(response_object), 400


@users_blueprint.route("/<user_id>/profile-image", methods=["POST"])
@authenticate
def upload_profile_image(resp, user_id):
    """Upload profile image for user"""
    logger.info(f"Profile image upload request for user_id: {user_id}")
    
    # Check if user is updating their own profile or is admin
    if int(resp) != int(user_id) and not is_admin(resp):
        logger.warning(f"User {resp} attempted to upload image for user {user_id}")
        response_object = {
            "status": "fail",
            "message": "You do not have permission to update this user's profile image."
        }
        return jsonify(response_object), 403
    
    # Check if user exists
    user = User.query.filter_by(id=int(user_id)).first()
    if not user:
        logger.warning(f"User {user_id} not found for profile image upload")
        response_object = {
            "status": "fail",
            "message": "User not found"
        }
        return jsonify(response_object), 404
    
    # Check if file is present in request
    if 'profile_image' not in request.files:
        logger.warning("No profile_image file in request")
        response_object = {
            "status": "fail",
            "message": "No profile image file provided"
        }
        return jsonify(response_object), 400
    
    file = request.files['profile_image']
    if file.filename == '':
        logger.warning("Empty filename in profile image upload")
        response_object = {
            "status": "fail",
            "message": "No file selected"
        }
        return jsonify(response_object), 400
    
    try:
        # Read file data
        file_data = file.read()
        filename = file.filename
        
        logger.debug(f"Processing profile image: {filename}, size: {len(file_data)} bytes")
        
        # Validate image file
        is_valid, error_message, file_extension = validate_image_file(file_data, filename)
        if not is_valid:
            logger.warning(f"Image validation failed: {error_message}")
            response_object = {
                "status": "fail",
                "message": error_message
            }
            return jsonify(response_object), 400
        
        # Upload to S3
        success, s3_url_or_error, presigned_url_or_error = upload_image_to_s3(file_data, user_id, file_extension)
        if not success:
            logger.error(f"S3 upload failed: {s3_url_or_error}")
            response_object = {
                "status": "fail",
                "message": f"Failed to upload image: {s3_url_or_error}"
            }
            return jsonify(response_object), 500
        
        # Update user profile_image_url with S3 URI
        user.profile_image_url = s3_url_or_error
        db.session.commit()
        
        logger.info(f"Profile image uploaded successfully for user {user_id}")
        response_object = {
            "status": "success",
            "message": "Profile image uploaded successfully",
            "data": {
                "profile_image_url": presigned_url_or_error
            }
        }
        return jsonify(response_object), 200
        
    except Exception as e:
        logger.error(f"Error uploading profile image: {str(e)}")
        logger.exception("Full traceback:")
        db.session.rollback()
        response_object = {
            "status": "error",
            "message": "Internal server error"
        }
        return jsonify(response_object), 500


@users_blueprint.route("/<user_id>/profile-image", methods=["GET"])
@authenticate
def get_profile_image(resp, user_id):
    """Get profile image URL for user"""
    logger.info(f"Profile image request for user_id: {user_id}")
    
    # Check if user is accessing their own profile or is admin
    if int(resp) != int(user_id) and not is_admin(resp):
        logger.warning(f"User {resp} attempted to access profile image for user {user_id}")
        response_object = {
            "status": "fail",
            "message": "You do not have permission to access this user's profile image."
        }
        return jsonify(response_object), 403
    
    # Check if user exists
    user = User.query.filter_by(id=int(user_id)).first()
    if not user:
        logger.warning(f"User {user_id} not found for profile image request")
        response_object = {
            "status": "fail",
            "message": "User not found"
        }
        return jsonify(response_object), 404
    
    try:
        # Get latest profile image URL directly from S3
        success, presigned_url_or_error = get_latest_profile_image_url(user_id)
        if success:
            logger.info(f"Profile image URL generated for user {user_id}")
            response_object = {
                "status": "success",
                "message": "Profile image URL retrieved successfully",
                "data": {
                    "profile_image_url": presigned_url_or_error
                }
            }
            return jsonify(response_object), 200
        else:
            logger.debug(f"No profile image found for user {user_id}: {presigned_url_or_error}")
            response_object = {
                "status": "fail",
                "message": "No profile image found"
            }
            return jsonify(response_object), 404
        
    except Exception as e:
        logger.error(f"Error getting profile image: {str(e)}")
        logger.exception("Full traceback:")
        response_object = {
            "status": "error",
            "message": "Internal server error"
        }
        return jsonify(response_object), 500


@users_blueprint.route("/<user_id>/profile-image", methods=["DELETE"])
@authenticate
def delete_profile_image(resp, user_id):
    """Delete profile image for user"""
    logger.info(f"Profile image deletion request for user_id: {user_id}")
    
    # Check if user is deleting their own profile or is admin
    if int(resp) != int(user_id) and not is_admin(resp):
        logger.warning(f"User {resp} attempted to delete profile image for user {user_id}")
        response_object = {
            "status": "fail",
            "message": "You do not have permission to delete this user's profile image."
        }
        return jsonify(response_object), 403
    
    # Check if user exists
    user = User.query.filter_by(id=int(user_id)).first()
    if not user:
        logger.warning(f"User {user_id} not found for profile image deletion")
        response_object = {
            "status": "fail",
            "message": "User not found"
        }
        return jsonify(response_object), 404
    
    try:
        # Clear profile_image_url
        user.profile_image_url = None
        db.session.commit()
        
        logger.info(f"Profile image URL cleared for user {user_id}")
        response_object = {
            "status": "success",
            "message": "Profile image deleted successfully"
        }
        return jsonify(response_object), 200
        
    except Exception as e:
        logger.error(f"Error deleting profile image: {str(e)}")
        logger.exception("Full traceback:")
        db.session.rollback()
        response_object = {
            "status": "error",
            "message": "Internal server error"
        }
        return jsonify(response_object), 500