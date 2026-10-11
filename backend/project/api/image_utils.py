import os
import uuid
from datetime import datetime, timezone
from io import BytesIO
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from PIL import Image
from flask import current_app
from project.logger import get_logger

logger = get_logger("image_utils")

# Valid image formats
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def get_s3_client():
    """
    Create and return S3 client
    Uses IAM role credentials automatically when running on EC2
    """
    try:
        # Only get region from environment
        aws_region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
        
        # Create S3 client without explicit credentials
        # boto3 will automatically use IAM role from EC2 instance profile
        s3_client = boto3.client('s3', region_name=aws_region)
        
        return s3_client
    except Exception as e:
        logger.error(f"Error creating S3 client: {str(e)}")
        raise


def validate_image_file(file_data, filename):
    """
    Validate image file format and size
    Returns: (is_valid, error_message, file_extension)
    """
    try:
        if not filename:
            return False, "No filename provided", None
            
        # Check file extension
        file_extension = filename.lower().split('.')[-1]
        if file_extension not in ALLOWED_EXTENSIONS:
            return False, f"Invalid file format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}", None
            
        # Check file size
        if len(file_data) > MAX_FILE_SIZE:
            return False, f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB", None
            
        # Try to open and validate the image
        try:
            image = Image.open(BytesIO(file_data))
            image.verify()  # Verify it's a valid image
            logger.info(f"Image validation successful: {filename}, size: {len(file_data)} bytes")
            return True, None, file_extension
        except Exception as e:
            logger.error(f"Invalid image file {filename}: {str(e)}")
            return False, "Invalid image file", None
            
    except Exception as e:
        logger.error(f"Error validating image file: {str(e)}")
        return False, f"Validation error: {str(e)}", None


def upload_image_to_s3(file_data, user_id, file_extension):
    """
    Upload image to S3 bucket
    Returns: (success, s3_url_or_error_message, presigned_url)
    """
    try:
        # Get S3 bucket name from environment
        bucket_name = os.environ.get('STATIC_S3_BUCKET')
        
        if not bucket_name:
            logger.error("Missing S3 bucket name configuration")
            return False, "S3 bucket not configured", None
            
        # Create S3 client (uses IAM role automatically)
        s3_client = get_s3_client()
        
        # Generate unique filename
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        s3_key = f"profile_images/user_{user_id}/{timestamp}_{unique_id}.{file_extension}"
        
        # Upload file to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=file_data,
            ContentType=f'image/{file_extension}',
            CacheControl='max-age=86400'  # 24 hours cache
        )
        
        # Generate presigned URL for the uploaded image (valid for 1 hour)
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': s3_key},
            ExpiresIn=3600  # 1 hour
        )
        
        # Store the S3 URI in database for future presigned URL generation
        s3_key_url = f"s3://{bucket_name}/{s3_key}"
        
        logger.info(f"Image uploaded successfully to S3: {s3_key}")
        return True, s3_key_url, presigned_url
        
    except NoCredentialsError:
        error_msg = "AWS credentials not available. Ensure EC2 instance has proper IAM role."
        logger.error(error_msg)
        return False, error_msg, None
    except ClientError as e:
        error_msg = f"S3 upload failed: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, None
    except Exception as e:
        error_msg = f"Upload error: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, None


def generate_presigned_url_from_s3_key(s3_key_url):
    """
    Generate presigned URL from stored S3 key URL
    Returns: (success, presigned_url_or_error_message)
    """
    try:
        # Parse S3 key URL: s3://bucket/key
        if not s3_key_url.startswith('s3://'):
            return False, "Invalid S3 key format"
        
        # Remove s3:// prefix and split bucket/key
        s3_path = s3_key_url[5:]  # Remove 's3://'
        bucket_name, s3_key = s3_path.split('/', 1)
        
        # Create S3 client (uses IAM role automatically)
        s3_client = get_s3_client()
        
        # Generate presigned URL (valid for 1 hour)
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': s3_key},
            ExpiresIn=3600  # 1 hour
        )
        
        logger.info(f"Presigned URL generated for S3 key: {s3_key}")
        return True, presigned_url
        
    except NoCredentialsError:
        error_msg = "AWS credentials not available. Ensure EC2 instance has proper IAM role."
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Error generating presigned URL: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def get_latest_profile_image_url(user_id):
    """
    Get the latest profile image URL for a user from S3
    Returns: (success, presigned_url_or_error_message)
    """
    try:
        # Get S3 bucket name from environment
        bucket_name = os.environ.get('STATIC_S3_BUCKET')
        
        if not bucket_name:
            logger.error("Missing S3 bucket name configuration")
            return False, "S3 bucket not configured"
            
        # Create S3 client (uses IAM role automatically)
        s3_client = get_s3_client()
        
        # List objects in user's profile images folder
        prefix = f"profile_images/user_{user_id}/"
        
        try:
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=prefix,
                MaxKeys=1000
            )
            
            if 'Contents' not in response or not response['Contents']:
                logger.info(f"No profile images found for user {user_id}")
                return False, "No profile image found"
            
            # Sort by LastModified to get the latest image
            latest_object = max(response['Contents'], key=lambda x: x['LastModified'])
            latest_key = latest_object['Key']
            
            # Generate presigned URL for the latest image (valid for 1 hour)
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': latest_key},
                ExpiresIn=3600  # 1 hour
            )
            
            logger.info(f"Latest profile image URL generated for user {user_id}")
            return True, presigned_url
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return False, "No profile image found"
            else:
                raise e
                
    except NoCredentialsError:
        error_msg = "AWS credentials not available. Ensure EC2 instance has proper IAM role."
        logger.error(error_msg)
        return False, error_msg
    except ClientError as e:
        error_msg = f"S3 access failed: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Error getting profile image: {str(e)}"
        logger.error(error_msg)
        return False, error_msg