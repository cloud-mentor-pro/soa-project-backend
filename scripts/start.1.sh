#!/bin/bash
# Script to start application with environment-specific configuration

# Default values
PROFILE_NAME="default"
OUTPUT_FILE=".env"
HELP=false
ENVIRONMENT=""
DB_PASSWORD="postgres"
DB_URL="db"
STATIC_S3_BUCKET=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Function to print colored output
print_success() {
    echo -e "${GREEN}$1${NC}"
}

print_error() {
    echo -e "${RED}$1${NC}"
}

print_info() {
    echo -e "${CYAN}$1${NC}"
}

# Function to show help
show_help() {
    echo -e "${GREEN}Application Starter${NC}"
    echo "Usage: ./start.sh <environment> [-p <profile>] [-h]"
    echo ""
    echo "Arguments:"
    echo "  <environment>    Environment to use (dev or prod)"
    echo ""
    echo "Options:"
    echo "  -p, --profile    AWS profile name (default: 'default', used in dev mode)"
    echo "  -h, --help       Show this help message"
}

# Parse arguments
if [ $# -eq 0 ]; then
    print_error "Environment parameter (dev or prod) is required"
    show_help
    exit 1
fi

ENVIRONMENT="$1"
shift

if [ "$ENVIRONMENT" != "dev" ] && [ "$ENVIRONMENT" != "prod" ]; then
    print_error "Invalid environment: $ENVIRONMENT. Must be 'dev' or 'prod'"
    show_help
    exit 1
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--profile)
            PROFILE_NAME="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

print_info "Starting application in $ENVIRONMENT mode..."

# Function to fetch DB password from Secrets Manager
fetch_db_password() {
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI not found"
        exit 1
    fi

    SECRET_NAME=$(aws ssm get-parameter --name "soa-param-codeland-db-secret-name" --query "Parameter.Value" --output text)
    if [ -z "$SECRET_NAME" ]; then
        print_error "Failed to retrieve secret name from Parameter Store"
        exit 1
    fi
    print_success "Secret name retrieved: $SECRET_NAME"

    SECRET_VALUE=$(aws secretsmanager get-secret-value --secret-id "$SECRET_NAME" --query "SecretString" --output text)
    if [ -z "$SECRET_VALUE" ]; then
        print_error "Failed to retrieve secret value"
        exit 1
    fi

    DB_PASSWORD=$(echo "$SECRET_VALUE" | jq -r '.password')
    if [ -z "$DB_PASSWORD" ]; then
        print_error "Failed to parse password from secret"
        exit 1
    fi
    print_success "Database password retrieved"
}

# Function to fetch DB URL
fetch_db_url() {
    DB_URL=$(aws ssm get-parameter --name "soa-param-codeland-db-url" --query "Parameter.Value" --output text)
    if [ -z "$DB_URL" ]; then
        print_error "Failed to retrieve DB URL"
        exit 1
    fi
    print_success "Database URL retrieved: $DB_URL"
}

# Function to fetch S3 bucket name
fetch_static_s3_bucket() {
    local aws_cmd="aws ssm get-parameter --name \"soa-param-codeland-static-bucket-name\" --query \"Parameter.Value\" --output text"
    
    if [ "$ENVIRONMENT" = "dev" ]; then
        aws_cmd="$aws_cmd --profile \"$PROFILE_NAME\""
    fi

    STATIC_S3_BUCKET=$(eval $aws_cmd)
    if [ -z "$STATIC_S3_BUCKET" ]; then
        print_error "Failed to retrieve S3 bucket name"
        exit 1
    fi
    print_success "S3 bucket name retrieved: $STATIC_S3_BUCKET"
}

# Fetch configuration based on environment
if [ "$ENVIRONMENT" = "prod" ]; then
    print_info "Fetching production configuration..."
    
    # Get AWS region from EC2 metadata
    TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    AWS_REGION=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
    
    if [ -z "$AWS_REGION" ]; then
        AWS_REGION="us-east-1"
    fi
    
    fetch_db_password
    fetch_db_url
    fetch_static_s3_bucket
    
    # Create .env file for production (WITHOUT AWS credentials)
    cat > "$OUTPUT_FILE" << EOF
DB_USER=postgres
DB_PASSWORD=$DB_PASSWORD
DB_HOST=$DB_URL
DB_PORT=5432
DB_NAME=dev
DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@${DB_URL}:5432/dev
SECRET_KEY=my_precious
FLASK_APP=project/__init__.py
FLASK_DEBUG=0
APP_SETTINGS=project.config.ProductionConfig
PORT=80
STATIC_S3_BUCKET=$STATIC_S3_BUCKET
AWS_DEFAULT_REGION=$AWS_REGION
EOF

    print_success "Production configuration complete"
    print_info "Using IAM role for AWS credentials (not storing in .env)"
    
else
    # Development mode - use AWS profile
    print_info "Using development configuration with profile: $PROFILE_NAME"
    
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI not found"
        exit 1
    fi
    
    AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id --profile "$PROFILE_NAME")
    AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key --profile "$PROFILE_NAME")
    AWS_REGION=$(aws configure get region --profile "$PROFILE_NAME")
    
    if [ -z "$AWS_REGION" ]; then
        AWS_REGION="us-east-1"
    fi
    
    fetch_static_s3_bucket
    
    # Create .env for development (WITH AWS credentials)
    cat > "$OUTPUT_FILE" << EOF
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432
DB_NAME=dev
DATABASE_URL=postgresql://postgres:postgres@db:5432/dev
SECRET_KEY=my_precious
FLASK_APP=project/__init__.py
FLASK_DEBUG=1
APP_SETTINGS=project.config.DevelopmentConfig
PORT=80
STATIC_S3_BUCKET=$STATIC_S3_BUCKET
AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
AWS_DEFAULT_REGION=$AWS_REGION
EOF
fi

print_success "Configuration file created: $OUTPUT_FILE"

# Export environment variables for the application
export DB_USER=postgres
export DB_PASSWORD="$DB_PASSWORD"
export DB_HOST="$DB_URL"
export DB_PORT=5432
export DB_NAME=dev
export DATABASE_URL="postgresql://postgres:${DB_PASSWORD}@${DB_URL}:5432/dev"
export SECRET_KEY=my_precious
export FLASK_APP=project/__init__.py
export PORT=80
export STATIC_S3_BUCKET="$STATIC_S3_BUCKET"
export AWS_DEFAULT_REGION="$AWS_REGION"

if [ "$ENVIRONMENT" = "prod" ]; then
    export FLASK_DEBUG=0
    export APP_SETTINGS=project.config.ProductionConfig
    
    # CRITICAL: Unset AWS credentials to force boto3 to use IAM role
    unset AWS_ACCESS_KEY_ID
    unset AWS_SECRET_ACCESS_KEY
    unset AWS_SESSION_TOKEN
    
    print_info "Environment: Production"
    print_info "Using IAM role: EC2 instance profile"
else
    export FLASK_DEBUG=1
    export APP_SETTINGS=project.config.DevelopmentConfig
    export AWS_ACCESS_KEY_ID
    export AWS_SECRET_ACCESS_KEY
    
    print_info "Environment: Development"
    print_info "Using AWS profile: $PROFILE_NAME"
fi

print_info "Database: postgresql://postgres:****@${DB_URL}:5432/dev"
print_info "Database: postgresql://postgres:****@${DATABASE_URL}:5432/dev"
print_info "S3 Bucket: $STATIC_S3_BUCKET"
print_info "Region: $AWS_REGION"

# Start the server
print_success "Starting Gunicorn server..."
source /root/app/venv/bin/activate
cd /root/app/backend

exec gunicorn -b 0.0.0.0:$PORT manage:app \
  --workers 4 \
  --timeout 120 \
  --access-logfile /var/log/gunicorn/gunicorn_access.log \
  --error-logfile /var/log/gunicorn/gunicorn_error.log \
  --log-level info