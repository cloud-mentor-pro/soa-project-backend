#!/bin/bash
# Script to generate .env file with AWS credentials, DB password, and DB URL based on environment (dev or prod)

# Default values
echo "DEBUG: Setting default values"
PROFILE_NAME="default"
OUTPUT_FILE=".env"
HELP=false
ENVIRONMENT=""
DB_PASSWORD="postgres"  # Default for dev
DB_URL="db"  # Default for dev
STATIC_S3_BUCKET=""

# Colors for output
echo "DEBUG: Defining colors"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to show help
show_help() {
    echo "DEBUG: Showing help"
    echo -e "${GREEN}AWS Credentials Converter${NC}"
    echo "=================================================="
    echo ""
    echo "Usage:"
    echo "  ./start.sh <environment> [-p <profile>] [-o <file>] [-h]"
    echo ""
    echo "Arguments:"
    echo "  <environment>    Environment to use (dev or prod)"
    echo ""
    echo "Options:"
    echo "  -p, --profile    AWS profile name (default: 'default', used in dev mode)"
    echo "  -o, --output     Output file name (default: '.env')"
    echo "  -h, --help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./start.sh dev"
    echo "  ./start.sh prod"
    echo "  ./start.sh dev -p my-profile -o dev.env"
    echo ""
}

# Function to print colored output
print_success() {
    echo "DEBUG: Printing success message: $1"
    echo -e "${GREEN}$1${NC}"
}

print_error() {
    echo "DEBUG: Printing error message: $1"
    echo -e "${RED}$1${NC}"
}

print_warning() {
    echo "DEBUG: Printing warning message: $1"
    echo -e "${YELLOW}$1${NC}"
}

print_info() {
    echo "DEBUG: Printing info message: $1"
    echo -e "${CYAN}$1${NC}"
}

# Parse command line arguments
echo "DEBUG: Checking number of arguments"
if [ $# -eq 0 ]; then
    print_error "Environment parameter (dev or prod) is required"
    show_help
    exit 1
fi

echo "DEBUG: Setting ENVIRONMENT to $1"
ENVIRONMENT="$1"
shift

# Validate environment
echo "DEBUG: Validating environment: $ENVIRONMENT"
if [ "$ENVIRONMENT" != "dev" ] && [ "$ENVIRONMENT" != "prod" ]; then
    print_error "Invalid environment: $ENVIRONMENT. Must be 'dev' or 'prod'"
    show_help
    exit 1
fi

echo "DEBUG: Parsing remaining arguments"
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--profile)
            echo "DEBUG: Setting PROFILE_NAME to $2"
            PROFILE_NAME="$2"
            shift 2
            ;;
        -o|--output)
            echo "DEBUG: Setting OUTPUT_FILE to $2"
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -h|--help)
            echo "DEBUG: Setting HELP to true"
            HELP=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Show help if requested
echo "DEBUG: Checking if HELP is true"
if [ "$HELP" = true ]; then
    show_help
    exit 0
fi

echo -e "${GREEN}AWS Credentials Converter for $ENVIRONMENT${NC}"
echo "=============================="
echo ""

# Initialize credential variables
echo "DEBUG: Initializing credential variables"
# AWS_ACCESS_KEY_ID=""
# AWS_SECRET_ACCESS_KEY=""
# AWS_SESSION_TOKEN=""
AWS_REGION=""

# Function to fetch credentials for dev environment
fetch_dev_credentials() {
    echo "DEBUG: Checking if AWS CLI is installed"
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI not found. Please install AWS CLI first."
        print_info "Installation guide: https://aws.amazon.com/cli/"
        exit 1
    fi

    echo "DEBUG: Getting AWS version"
    AWS_VERSION=$(aws --version 2>/dev/null)
    print_success "AWS CLI found: $AWS_VERSION"

    # Check if credentials file exists
    echo "DEBUG: Setting CREDENTIALS_PATH"
    CREDENTIALS_PATH="$HOME/.aws/credentials"
    echo "DEBUG: Checking if credentials file exists at $CREDENTIALS_PATH"
    if [ ! -f "$CREDENTIALS_PATH" ]; then
        print_error "AWS credentials file not found at: $CREDENTIALS_PATH"
        print_warning "Please run 'aws configure' first to set up your credentials."
        exit 1
    fi

    print_success "AWS credentials file found"

    # Check if profile exists in credentials
    echo "DEBUG: Checking if profile $PROFILE_NAME exists"
    if ! grep -q "\[$PROFILE_NAME\]" "$CREDENTIALS_PATH"; then
        print_error "Profile '$PROFILE_NAME' not found in credentials file"
        print_info "Available profiles:"
        grep -o '\[[^]]*\]' "$CREDENTIALS_PATH" | sed 's/\[//g' | sed 's/\]//g' | while read -r profile; do
            echo -e "  ${CYAN}- $profile${NC}"
        done
        exit 1
    fi

    print_success "Profile '$PROFILE_NAME' found"

    # Extract credentials for the specified profile
    # echo "DEBUG: Extracting AWS_ACCESS_KEY_ID"
    # AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id --profile "$PROFILE_NAME" 2>/dev/null)
    # echo "DEBUG: Extracting AWS_SECRET_ACCESS_KEY"
    # AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key --profile "$PROFILE_NAME" 2>/dev/null)
    echo "DEBUG: Extracting AWS_REGION"
    AWS_REGION=$(aws configure get region --profile "$PROFILE_NAME" 2>/dev/null)

    # echo "DEBUG: Checking if keys are extracted"
    # if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    #     print_error "Failed to extract access key or secret key from profile"
    #     exit 1
    # fi

    echo "DEBUG: Checking if region is set"
    if [ -z "$AWS_REGION" ]; then
        echo "DEBUG: Setting default region"
        AWS_REGION="us-east-1"  # Default region
    fi
}

# Function to fetch credentials for prod environment (EC2 IMDSv2)
fetch_prod_credentials() {
    echo "DEBUG: Checking if jq is installed"
    if ! command -v jq &> /dev/null; then
        print_error "jq not found. Please install jq to parse JSON."
        print_info "Installation guide: https://stedolan.github.io/jq/download/"
        exit 1
    fi

    echo "DEBUG: Obtaining IMDSv2 token"
    TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    echo "DEBUG: Checking if TOKEN is set $TOKEN"
    if [ -z "$TOKEN" ]; then
        print_error "Failed to obtain IMDSv2 token. Ensure the script is running on an EC2 instance."
        exit 1
    fi

    echo "DEBUG: Retrieving ROLE_NAME"
    ROLE_NAME=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/iam/security-credentials/)
    echo "DEBUG: Checking if ROLE_NAME is set $ROLE_NAME"
    if [ -z "$ROLE_NAME" ]; then
        print_error "Failed to retrieve IAM role name from IMDSv2."
        exit 1
    fi

    echo "DEBUG: Retrieving CREDS_JSON"
    CREDS_JSON=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/iam/security-credentials/$ROLE_NAME)
    echo "DEBUG: Checking if CREDS_JSON is set"
    if [ -z "$CREDS_JSON" ]; then
        print_error "Failed to retrieve credentials from IMDSv2."
        exit 1
    fi

    # echo "DEBUG: Extracting AWS_ACCESS_KEY_ID from JSON"
    # AWS_ACCESS_KEY_ID=$(echo "$CREDS_JSON" | jq -r '.AccessKeyId')
    # echo "DEBUG: Extracting AWS_SECRET_ACCESS_KEY from JSON $AWS_ACCESS_KEY_ID"
    # AWS_SECRET_ACCESS_KEY=$(echo "$CREDS_JSON" | jq -r '.SecretAccessKey')
    # echo "DEBUG: Extracting AWS_SESSION_TOKEN from JSON $AWS_SECRET_ACCESS_KEY"
    # AWS_SESSION_TOKEN=$(echo "$CREDS_JSON" | jq -r '.SessionToken')
    # echo "DEBUG: Retrieving AWS_REGION $AWS_SESSION_TOKEN"
    AWS_REGION=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region)

    # echo "DEBUG: Checking if credentials are parsed"
    # if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ] || [ -z "$AWS_SESSION_TOKEN" ]; then
    #     print_error "Failed to parse credentials from IMDSv2 response."
    #     exit 1
    # fi

    echo "DEBUG: Checking if region is set"
    if [ -z "$AWS_REGION" ]; then
        echo "DEBUG: Setting default region"
        AWS_REGION="us-east-1"  # Default region
    fi

    # Fetch DB password and URL from Secrets Manager/Parameter Store for prod
    fetch_db_password
    fetch_db_url
}

# Function to fetch DB password from Secrets Manager for prod
fetch_db_password() {
    echo "DEBUG: Checking if AWS CLI is installed in fetch_db_password"
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI not found. Please install AWS CLI first."
        print_info "Installation guide: https://aws.amazon.com/cli/"
        exit 1
    fi

    echo "DEBUG: Exporting AWS credentials"
    # export AWS_ACCESS_KEY_ID
    # export AWS_SECRET_ACCESS_KEY
    # export AWS_SESSION_TOKEN
    # export AWS_REGION

    echo "DEBUG: Fetching SECRET_NAME from Parameter Store"
    SECRET_NAME=$(aws ssm get-parameter --name "soa-param-codeland-db-secret-name" --query "Parameter.Value" --output text)
    echo "DEBUG: Checking if SECRET_NAME is set"
    if [ -z "$SECRET_NAME" ]; then
        print_error "Failed to retrieve secret name from Parameter Store."
        exit 1
    fi

    print_success "Secret name retrieved: $SECRET_NAME"

    echo "DEBUG: Fetching SECRET_VALUE from Secrets Manager"
    SECRET_VALUE=$(aws secretsmanager get-secret-value --secret-id "$SECRET_NAME" --query "SecretString" --output text)
    echo "DEBUG: Checking if SECRET_VALUE is set"
    if [ -z "$SECRET_VALUE" ]; then
        print_error "Failed to retrieve secret value from Secrets Manager."
        exit 1
    fi

    echo "DEBUG: Parsing DB_PASSWORD from SECRET_VALUE"
    DB_PASSWORD=$(echo "$SECRET_VALUE" | jq -r '.password')
    echo "DEBUG: Checking if DB_PASSWORD is set"
    if [ -z "$DB_PASSWORD" ]; then
        print_error "Failed to parse password from secret value."
        exit 1
    fi

    print_success "Database password retrieved successfully"
}

# Function to fetch DB URL from Parameter Store for prod
fetch_db_url() {
    echo "DEBUG: Fetching DB_URL from Parameter Store"
    DB_URL=$(aws ssm get-parameter --name "soa-param-codeland-db-url" --query "Parameter.Value" --output text)
    echo "DEBUG: Checking if DB_URL is set"
    if [ -z "$DB_URL" ]; then
        print_error "Failed to retrieve DB URL from Parameter Store."
        exit 1
    fi

    print_success "Database URL retrieved: $DB_URL"
}

# Function to fetch static S3 bucket name from Parameter Store
fetch_static_s3_bucket() {
    echo "DEBUG: Checking if AWS CLI is installed in fetch_static_s3_bucket"
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI not found. Please install AWS CLI first."
        print_info "Installation guide: https://aws.amazon.com/cli/"
        exit 1
    fi

    local aws_cmd="aws ssm get-parameter --name \"soa-param-codeland-static-bucket-name\" --query \"Parameter.Value\" --output text"

    if [ "$ENVIRONMENT" = "dev" ]; then
        aws_cmd="$aws_cmd --profile \"$PROFILE_NAME\""
    fi

    echo "DEBUG: Fetching STATIC_S3_BUCKET from Parameter Store"
    STATIC_S3_BUCKET=$(eval $aws_cmd)
    echo "DEBUG: Checking if STATIC_S3_BUCKET is set"
    if [ -z "$STATIC_S3_BUCKET" ]; then
        print_error "Failed to retrieve static S3 bucket name from Parameter Store."
        exit 1
    fi

    print_success "Static S3 bucket name retrieved: $STATIC_S3_BUCKET"
}

# Fetch credentials based on environment
echo "DEBUG: Fetching credentials for environment $ENVIRONMENT"
if [ "$ENVIRONMENT" = "dev" ]; then
    fetch_dev_credentials
elif [ "$ENVIRONMENT" = "prod" ]; then
    fetch_prod_credentials
fi

# Fetch static S3 bucket name
fetch_static_s3_bucket

# print_success "Credentials extracted successfully"
# echo -e "  ${CYAN}Access Key: ${AWS_ACCESS_KEY_ID:0:4}****${AWS_ACCESS_KEY_ID: -4}${NC}"
# echo -e "  ${CYAN}Secret Key: ${AWS_SECRET_ACCESS_KEY:0:4}****${AWS_SECRET_ACCESS_KEY: -4}${NC}"
# if [ -n "$AWS_SESSION_TOKEN" ]; then
#     echo -e "  ${CYAN}Session Token: ${AWS_SESSION_TOKEN:0:4}****${AWS_SESSION_TOKEN: -4}${NC}"
# fi
echo -e "  ${CYAN}Region: $AWS_REGION${NC}"

# Create environment variables content
echo "DEBUG: Creating $OUTPUT_FILE"
cat > "$OUTPUT_FILE" << EOF
DB_USER=postgres
DB_PASSWORD=$DB_PASSWORD
DB_URL=$DB_URL
DB_PORT=5432
DB_NAME=dev
SECRET_KEY=my_precious
FLASK_APP=project/__init__.py
FLASK_DEBUG=1
APP_SETTINGS=project.config.DevelopmentConfig
PORT=80
STATIC_S3_BUCKET=$STATIC_S3_BUCKET
AWS_REGION=$AWS_REGION
EOF
PORT=80
DB_PORT=5432
# Add AWS_SESSION_TOKEN to .env file for prod environment
# echo "DEBUG: Checking if need to add AWS_SESSION_TOKEN"
# if [ "$ENVIRONMENT" = "prod" ] && [ -n "$AWS_SESSION_TOKEN" ]; then
#     echo "DEBUG: Appending AWS_SESSION_TOKEN to $OUTPUT_FILE"
#     echo "AWS_SESSION_TOKEN=$AWS_SESSION_TOKEN" >> "$OUTPUT_FILE"
# fi

echo "DEBUG: Checking if file write was successful"
if [ $? -eq 0 ]; then
    print_success "Environment variables written to: $OUTPUT_FILE"
else
    print_error "Failed to write to file: $OUTPUT_FILE"
    exit 1
fi

# Display summary
echo ""
echo -e "${GREEN}Summary:${NC}"
echo "  Environment: $ENVIRONMENT"
echo "  Profile: $PROFILE_NAME (used in dev mode)"
echo "  Output File: $OUTPUT_FILE"
echo "  S3 Bucket: $STATIC_S3_BUCKET"
echo "  Region: $AWS_REGION"
echo "  DB_PASSWORD=$DB_PASSWORD"
echo "  DB_URL=$DB_URL"
echo "  PORT=$PORT"
echo "  DB_PORT=$DB_PORT"
echo ""

echo -e "${YELLOW}Next steps:${NC}"
echo "1. Review the generated $OUTPUT_FILE file"
echo "2. Update STATIC_S3_BUCKET if needed"
echo "3. Run: docker-compose -f docker-compose-$ENVIRONMENT.yml up --build"
echo "4. Test: python backend/test_s3_config.py"
echo ""

echo -e "${GREEN}AWS credentials conversion completed!${NC}"


# Start the server
echo "DEBUG: Sourcing virtual environment"
source /root/app/venv/bin/activate
echo "DEBUG: Starting Gunicorn server"
echo "Starting Gunicorn server..."
echo "DEBUG: Changing directory to /root/app/backend"
cd /root/app/backend
echo "DEBUG: Executing gunicorn"
exec gunicorn -b 0.0.0.0:$PORT manage:app \
  --workers 4 \
  --timeout 120 \
  --log-level info