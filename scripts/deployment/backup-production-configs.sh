#!/bin/bash

# Backup Production Configuration Script
# This script connects to the production server and backs up all configuration files
# Usage: ./backup-production-configs.sh

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
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="${LOCAL_BACKUP_DIR}/${TIMESTAMP}"

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

# Check if SSH key is available or prompt for password
print_step "Checking SSH connection..."
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${SSH_HOST}" exit 2>/dev/null; then
    print_warning "SSH key authentication not available. You may be prompted for password."
fi

# Create local backup directory
print_step "Creating local backup directory..."
mkdir -p "${BACKUP_PATH}"
print_status "Backup directory created: ${BACKUP_PATH}"

# Function to backup a file
backup_file() {
    local remote_file=$1
    local local_file=$2
    local description=$3
    
    print_step "Backing up ${description}..."
    if ssh "${SSH_HOST}" "test -f ${REMOTE_DIR}/${remote_file}" 2>/dev/null; then
        scp "${SSH_HOST}:${REMOTE_DIR}/${remote_file}" "${BACKUP_PATH}/${local_file}" 2>/dev/null
        print_status "✓ ${description} backed up"
        return 0
    elif ssh "${SSH_HOST}" "test -f ${remote_file}" 2>/dev/null; then
        scp "${SSH_HOST}:${remote_file}" "${BACKUP_PATH}/${local_file}" 2>/dev/null
        print_status "✓ ${description} backed up (from root)"
        return 0
    else
        print_warning "✗ ${description} not found (skipping)"
        return 1
    fi
}

# Function to backup a directory
backup_directory() {
    local remote_dir=$1
    local local_dir=$2
    local description=$3
    
    print_step "Backing up ${description}..."
    if ssh "${SSH_HOST}" "test -d ${REMOTE_DIR}/${remote_dir}" 2>/dev/null; then
        mkdir -p "${BACKUP_PATH}/${local_dir}"
        scp -r "${SSH_HOST}:${REMOTE_DIR}/${remote_dir}/"* "${BACKUP_PATH}/${local_dir}/" 2>/dev/null || true
        print_status "✓ ${description} backed up"
        return 0
    elif ssh "${SSH_HOST}" "test -d ${remote_dir}" 2>/dev/null; then
        mkdir -p "${BACKUP_PATH}/${local_dir}"
        scp -r "${SSH_HOST}:${remote_dir}/"* "${BACKUP_PATH}/${local_dir}/" 2>/dev/null || true
        print_status "✓ ${description} backed up (from root)"
        return 0
    else
        print_warning "✗ ${description} not found (skipping)"
        return 1
    fi
}

# Backup .env file
backup_file ".env" ".env" "Environment variables file"

# Backup nginx configuration
backup_file "nginx/nginx.conf" "nginx.conf" "Nginx configuration"
if [ -f "${BACKUP_PATH}/nginx.conf" ]; then
    mkdir -p "${BACKUP_PATH}/nginx"
    mv "${BACKUP_PATH}/nginx.conf" "${BACKUP_PATH}/nginx/nginx.conf"
fi

# Backup certbot configuration (from Docker volume or system)
print_step "Backing up Certbot SSL certificates..."
if ssh "${SSH_HOST}" "docker volume inspect certbot-etc 2>/dev/null | grep -q Mountpoint" 2>/dev/null; then
    # Get volume mount point
    VOLUME_PATH=$(ssh "${SSH_HOST}" "docker volume inspect certbot-etc 2>/dev/null | grep -oP '\"Mountpoint\": \"\K[^\"]+' | head -1")
    if [ ! -z "$VOLUME_PATH" ]; then
        mkdir -p "${BACKUP_PATH}/certbot"
        ssh "${SSH_HOST}" "sudo tar czf - -C ${VOLUME_PATH} ." 2>/dev/null | tar xzf - -C "${BACKUP_PATH}/certbot/" 2>/dev/null || true
        print_status "✓ Certbot certificates backed up from Docker volume"
    fi
elif ssh "${SSH_HOST}" "test -d /etc/letsencrypt" 2>/dev/null; then
    mkdir -p "${BACKUP_PATH}/certbot"
    ssh "${SSH_HOST}" "sudo tar czf - -C /etc/letsencrypt ." 2>/dev/null | tar xzf - -C "${BACKUP_PATH}/certbot/" 2>/dev/null || true
    print_status "✓ Certbot certificates backed up from /etc/letsencrypt"
else
    print_warning "✗ Certbot certificates not found (skipping)"
fi

# Backup docker-compose file if it exists
backup_file "docker-compose.prod.yml" "docker-compose.prod.yml" "Docker Compose file"
backup_file "docker-compose.yml" "docker-compose.yml" "Docker Compose file (alternative)"

# Get list of all files in the directory for reference
print_step "Creating file listing..."
ssh "${SSH_HOST}" "cd ${REMOTE_DIR} && ls -la" > "${BACKUP_PATH}/file_listing.txt" 2>/dev/null || true
print_status "✓ File listing saved"

# Create backup manifest
print_step "Creating backup manifest..."
cat > "${BACKUP_PATH}/BACKUP_MANIFEST.txt" << EOF
Kaleidoscope Production Configuration Backup
============================================
Backup Date: $(date)
Server: ${SSH_HOST}
Remote Directory: ${REMOTE_DIR}
Backup Location: ${BACKUP_PATH}

Files Backed Up:
$(ls -lh "${BACKUP_PATH}" | tail -n +2 | awk '{print $9, "(" $5 ")"}')

To restore this backup, use:
  ./scripts/deployment/setup-production.sh ${TIMESTAMP}
EOF

print_status "✓ Backup manifest created"

# Create a summary
print_step "Backup Summary"
echo "=================="
echo -e "${GREEN}Backup completed successfully!${NC}"
echo ""
echo "Backup location: ${BACKUP_PATH}"
echo ""
echo "Contents:"
ls -lh "${BACKUP_PATH}" | tail -n +2
echo ""
print_status "To restore this backup, run:"
echo "  ./scripts/deployment/setup-production.sh ${TIMESTAMP}"
echo ""
print_status "Backup complete! ✓"

