#!/usr/bin/env python3
"""
Test script to verify S3 configuration and connectivity
"""

import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

def test_s3_configuration():
    """Test S3 configuration and connectivity"""
    
    print("Testing S3 Configuration")
    print("=" * 40)
    
    # Check environment variables
    print("1. Checking environment variables...")
    
    required_vars = [
        'STATIC_S3_BUCKET',
        'AWS_ACCESS_KEY_ID', 
        'AWS_SECRET_ACCESS_KEY',
        'AWS_REGION'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
            print(f"   ❌ {var}: Not set")
        else:
            # Mask sensitive values
            if 'KEY' in var or 'SECRET' in var:
                masked_value = value[:4] + '*' * (len(value) - 8) + value[-4:]
                print(f"   ✅ {var}: {masked_value}")
            else:
                print(f"   ✅ {var}: {value}")
    
    if missing_vars:
        print(f"\n❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these variables in your .env file or environment")
        return False
    
    print("\n2. Testing S3 client creation...")
    
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        print("   ✅ S3 client created successfully")
    except NoCredentialsError:
        print("   ❌ AWS credentials not found")
        return False
    except Exception as e:
        print(f"   ❌ Error creating S3 client: {str(e)}")
        return False
    
    print("\n3. Testing S3 bucket access...")
    
    bucket_name = os.getenv('STATIC_S3_BUCKET')
    
    try:
        # Test bucket existence and access
        response = s3_client.head_bucket(Bucket=bucket_name)
        print(f"   ✅ Bucket '{bucket_name}' exists and is accessible")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"   ❌ Bucket '{bucket_name}' does not exist")
            print(f"   💡 Create the bucket in AWS S3 console")
        elif error_code == '403':
            print(f"   ❌ Access denied to bucket '{bucket_name}'")
            print(f"   💡 Check IAM permissions for S3 access")
        else:
            print(f"   ❌ Error accessing bucket: {str(e)}")
        return False
    except Exception as e:
        print(f"   ❌ Unexpected error: {str(e)}")
        return False
    
    print("\n4. Testing S3 permissions...")
    
    try:
        # Test list objects permission
        response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
        print("   ✅ List objects permission: OK")
    except ClientError as e:
        print(f"   ❌ List objects permission denied: {str(e)}")
        return False
    
    try:
        # Test put object permission (with a test object)
        test_key = "test-connection.txt"
        test_content = "S3 connection test"
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=test_key,
            Body=test_content.encode('utf-8'),
            ContentType='text/plain'
        )
        print("   ✅ Put object permission: OK")
        
        # Clean up test object
        s3_client.delete_object(Bucket=bucket_name, Key=test_key)
        print("   ✅ Delete object permission: OK")
        
    except ClientError as e:
        print(f"   ❌ Put/Delete object permission denied: {str(e)}")
        return False
    
    print("\n5. Testing presigned URL generation...")
    
    try:
        # Generate a presigned URL for a test object
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': 'test-presigned-url.txt'},
            ExpiresIn=3600
        )
        print("   ✅ Presigned URL generation: OK")
        print(f"   📝 Sample URL: {presigned_url[:50]}...")
    except Exception as e:
        print(f"   ❌ Presigned URL generation failed: {str(e)}")
        return False
    
    print("\n" + "=" * 40)
    print("✅ S3 configuration test completed successfully!")
    print("🚀 Profile image feature is ready to use!")
    
    return True

def test_image_utils_import():
    """Test if image_utils can be imported successfully"""
    
    print("\n6. Testing image utilities import...")
    
    try:
        from project.api.image_utils import (
            validate_image_file, 
            upload_image_to_s3, 
            get_latest_profile_image_url
        )
        print("   ✅ Image utilities imported successfully")
        return True
    except ImportError as e:
        print(f"   ❌ Failed to import image utilities: {str(e)}")
        print("   💡 Make sure all dependencies are installed:")
        print("      pip install boto3 Pillow python-magic")
        return False
    except Exception as e:
        print(f"   ❌ Unexpected error importing image utilities: {str(e)}")
        return False

if __name__ == "__main__":
    print("S3 Configuration Test for Profile Image Feature")
    print("=" * 50)
    
    # Test image utils import first
    utils_ok = test_image_utils_import()
    
    if utils_ok:
        # Test S3 configuration
        s3_ok = test_s3_configuration()
        
        if s3_ok:
            print("\n🎉 All tests passed! Profile image feature is ready.")
        else:
            print("\n❌ S3 configuration test failed. Please fix the issues above.")
    else:
        print("\n❌ Image utilities test failed. Please install dependencies.")

