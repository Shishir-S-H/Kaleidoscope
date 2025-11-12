#!/bin/bash

# Production Setup/Restore Script
# This script sets up or restores the production environment from a backup
# Usage: ./setup-production.sh [backup_timestamp]
#   If backup_timestamp is provided, restores from that backup
#   Otherwise, sets up a fresh environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SSH_HOST="root@165.232.179.167"
REMOTE_DIR="~/Kaleidoscope"
LOCAL_BACKUP_DIR="production-configs"
BACKUP_TIMESTAMP="${1:-}"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if SSH connection works
print_step "Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${SSH_HOST}" exit 2>/dev/null; then
    print_warning "SSH key authentication not available. You may be prompted for password."
fi

# Function to copy file to remote
copy_file() {
    local local_file=$1
    local remote_file=$2
    local description=$3
    
    if [ -f "${local_file}" ]; then
        print_status "Copying ${description}..."
        scp "${local_file}" "${SSH_HOST}:${REMOTE_DIR}/${remote_file}" 2>/dev/null
        print_status "✓ ${description} copied"
        return 0
    else
        print_warning "✗ ${description} not found locally (skipping)"
        return 1
    fi
}

# Function to copy directory to remote
copy_directory() {
    local local_dir=$1
    local remote_dir=$2
    local description=$3
    
    if [ -d "${local_dir}" ] && [ "$(ls -A ${local_dir} 2>/dev/null)" ]; then
        print_status "Copying ${description}..."
        ssh "${SSH_HOST}" "mkdir -p ${REMOTE_DIR}/${remote_dir}" 2>/dev/null
        scp -r "${local_dir}/"* "${SSH_HOST}:${REMOTE_DIR}/${remote_dir}/" 2>/dev/null || true
        print_status "✓ ${description} copied"
        return 0
    else
        print_warning "✗ ${description} not found locally (skipping)"
        return 1
    fi
}

# Restore from backup if timestamp provided
if [ ! -z "${BACKUP_TIMESTAMP}" ]; then
    BACKUP_PATH="${LOCAL_BACKUP_DIR}/${BACKUP_TIMESTAMP}"
    
    if [ ! -d "${BACKUP_PATH}" ]; then
        print_error "Backup directory not found: ${BACKUP_PATH}"
        print_error "Available backups:"
        ls -1 "${LOCAL_BACKUP_DIR}" 2>/dev/null || echo "  (none)"
        exit 1
    fi
    
    print_step "Restoring from backup: ${BACKUP_TIMESTAMP}"
    
    # Create remote directory
    print_step "Creating remote directory structure..."
    ssh "${SSH_HOST}" "mkdir -p ${REMOTE_DIR}/nginx" 2>/dev/null
    print_status "Remote directory created"
    
    # Restore .env file
    copy_file "${BACKUP_PATH}/.env" ".env" "Environment variables file"
    
    # Restore nginx configuration
    if [ -f "${BACKUP_PATH}/nginx/nginx.conf" ]; then
        copy_file "${BACKUP_PATH}/nginx/nginx.conf" "nginx/nginx.conf" "Nginx configuration"
    elif [ -f "${BACKUP_PATH}/nginx.conf" ]; then
        copy_file "${BACKUP_PATH}/nginx.conf" "nginx/nginx.conf" "Nginx configuration"
    fi
    
    # Restore docker-compose file
    if [ -f "${BACKUP_PATH}/docker-compose.prod.yml" ]; then
        copy_file "${BACKUP_PATH}/docker-compose.prod.yml" "docker-compose.prod.yml" "Docker Compose file"
    fi
    
    # Restore certbot certificates (if available)
    if [ -d "${BACKUP_PATH}/certbot" ] && [ "$(ls -A ${BACKUP_PATH}/certbot 2>/dev/null)" ]; then
        print_step "Restoring Certbot certificates..."
        # Note: Certbot certificates are typically in Docker volumes
        # This would need to be handled separately or during container startup
        print_warning "Certbot certificates should be restored manually to Docker volumes"
        print_warning "Or let Certbot regenerate them on first run"
    fi
    
    print_status "✓ Backup restored"
else
    print_step "Setting up fresh production environment..."
    
    # Create remote directory
    print_step "Creating remote directory structure..."
    ssh "${SSH_HOST}" "mkdir -p ${REMOTE_DIR}/nginx" 2>/dev/null
    print_status "Remote directory created"
    
    # Copy docker-compose file from local
    if [ -f "docker-compose.prod.yml" ]; then
        copy_file "docker-compose.prod.yml" "docker-compose.prod.yml" "Docker Compose file"
    else
        print_error "docker-compose.prod.yml not found in current directory!"
        print_error "Please run this script from the kaleidoscope-ai directory"
        exit 1
    fi
    
    # Check if .env exists locally
    if [ -f ".env" ]; then
        print_warning ".env file found locally. Copy it? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            copy_file ".env" ".env" "Environment variables file"
        else
            print_warning "Skipping .env copy. Please create it manually on the server."
        fi
    else
        print_warning ".env file not found locally."
        print_warning "Please create it on the server with required environment variables."
    fi
    
    # Check if nginx.conf exists locally
    if [ -f "nginx/nginx.conf" ]; then
        copy_file "nginx/nginx.conf" "nginx/nginx.conf" "Nginx configuration"
    else
        print_warning "nginx/nginx.conf not found locally."
        print_warning "Please create it on the server or restore from backup."
    fi
fi

# Verify required files exist on server
print_step "Verifying required files on server..."
REQUIRED_FILES=("docker-compose.prod.yml" ".env" "nginx/nginx.conf")
MISSING_FILES=()

for file in "${REQUIRED_FILES[@]}"; do
    if ssh "${SSH_HOST}" "test -f ${REMOTE_DIR}/${file}" 2>/dev/null; then
        print_status "✓ ${file} exists"
    else
        print_warning "✗ ${file} missing"
        MISSING_FILES+=("${file}")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    print_error "Some required files are missing:"
    for file in "${MISSING_FILES[@]}"; do
        echo "  - ${file}"
    done
    print_error "Please create these files before starting services."
    exit 1
fi

# Pull latest images
print_step "Pulling latest Docker images..."
print_status "This may take a few minutes..."

# Pull backend image
BACKEND_IMAGE="ajayprabhu2004/kaleidoscope:backend-latest"
print_status "Pulling ${BACKEND_IMAGE}..."
ssh "${SSH_HOST}" "docker pull ${BACKEND_IMAGE}" || print_warning "Failed to pull backend image"

# Pull AI service images
AI_SERVICES=(
    "content_moderation"
    "image_tagger"
    "scene_recognition"
    "image_captioning"
    "face_recognition"
    "post_aggregator"
    "es_sync"
)

for service in "${AI_SERVICES[@]}"; do
    AI_IMAGE="shishir01/kaleidoscope-${service}:latest"
    print_status "Pulling ${AI_IMAGE}..."
    ssh "${SSH_HOST}" "docker pull ${AI_IMAGE}" || print_warning "Failed to pull ${service} image"
done

# Start services
print_step "Starting services..."
if ssh "${SSH_HOST}" "cd ${REMOTE_DIR} && docker-compose -f docker-compose.prod.yml up -d"; then
    print_status "✓ Services started successfully"
else
    print_error "✗ Failed to start services"
    exit 1
fi

# Wait for services to initialize
print_step "Waiting for services to initialize..."
sleep 15

# Check service status
print_step "Service status:"
ssh "${SSH_HOST}" "cd ${REMOTE_DIR} && docker-compose -f docker-compose.prod.yml ps"

# Summary
echo ""
print_status "=========================================="
print_status "Setup Complete"
print_status "=========================================="
echo ""
print_status "Production environment is ready!"
echo ""
print_status "Next steps:"
echo "  1. Verify all services are running:"
echo "     ssh ${SSH_HOST} 'cd ${REMOTE_DIR} && docker-compose -f docker-compose.prod.yml ps'"
echo ""
echo "  2. Check service logs:"
echo "     ssh ${SSH_HOST} 'cd ${REMOTE_DIR} && docker-compose -f docker-compose.prod.yml logs -f'"
echo ""
echo "  3. Test backend health:"
echo "     ssh ${SSH_HOST} 'curl http://localhost:8080/actuator/health'"
echo ""
if [ -z "${BACKUP_TIMESTAMP}" ]; then
    print_warning "Note: If SSL certificates are needed, run Certbot manually:"
    echo "     ssh ${SSH_HOST} 'cd ${REMOTE_DIR} && docker-compose -f docker-compose.prod.yml run --rm certbot certonly --webroot -w /var/www/certbot -d your-domain.com'"
fi
echo ""
print_status "Setup complete! ✓"

