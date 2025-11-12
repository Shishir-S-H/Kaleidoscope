#!/bin/bash

# Production Deployment Script
# This script pulls the latest Docker images and restarts services on production
# Usage: ./deploy-production.sh

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
DOCKER_REGISTRY_BACKEND="ajayprabhu2004"
DOCKER_REGISTRY_AI="shishir01"
APP_VERSION="${APP_VERSION:-latest}"

# AI Services list
AI_SERVICES=(
    "content_moderation"
    "image_tagger"
    "scene_recognition"
    "image_captioning"
    "face_recognition"
    "post_aggregator"
    "es_sync"
)

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

# Verify remote directory exists
print_step "Verifying remote directory..."
if ! ssh "${SSH_HOST}" "test -d ${REMOTE_DIR}" 2>/dev/null; then
    print_error "Remote directory ${REMOTE_DIR} does not exist!"
    exit 1
fi
print_status "Remote directory verified"

# Pull latest backend image
print_step "Pulling latest backend image..."
BACKEND_IMAGE="${DOCKER_REGISTRY_BACKEND}/kaleidoscope:backend-${APP_VERSION}"
print_status "Pulling ${BACKEND_IMAGE}..."
if ssh "${SSH_HOST}" "cd ${REMOTE_DIR} && docker pull ${BACKEND_IMAGE}"; then
    print_status "✓ Backend image pulled successfully"
else
    print_error "✗ Failed to pull backend image"
    exit 1
fi

# Pull latest AI service images
print_step "Pulling latest AI service images..."
for service in "${AI_SERVICES[@]}"; do
    AI_IMAGE="${DOCKER_REGISTRY_AI}/kaleidoscope-${service}:latest"
    print_status "Pulling ${AI_IMAGE}..."
    if ssh "${SSH_HOST}" "cd ${REMOTE_DIR} && docker pull ${AI_IMAGE}"; then
        print_status "✓ ${service} image pulled successfully"
    else
        print_warning "✗ Failed to pull ${service} image (continuing...)"
    fi
done

# Verify docker-compose file exists
print_step "Verifying docker-compose file..."
if ! ssh "${SSH_HOST}" "test -f ${REMOTE_DIR}/docker-compose.prod.yml" 2>/dev/null; then
    print_error "docker-compose.prod.yml not found in ${REMOTE_DIR}!"
    print_error "Please ensure the unified docker-compose.prod.yml is present on the server."
    exit 1
fi
print_status "docker-compose.prod.yml found"

# Stop existing services gracefully
print_step "Stopping existing services..."
ssh "${SSH_HOST}" "cd ${REMOTE_DIR} && docker-compose -f docker-compose.prod.yml down" || true
print_status "Services stopped"

# Start services with new images
print_step "Starting services with latest images..."
if ssh "${SSH_HOST}" "cd ${REMOTE_DIR} && docker-compose -f docker-compose.prod.yml up -d"; then
    print_status "✓ Services started successfully"
else
    print_error "✗ Failed to start services"
    exit 1
fi

# Wait for services to initialize
print_step "Waiting for services to initialize..."
sleep 10

# Check service status
print_step "Checking service status..."
ssh "${SSH_HOST}" "cd ${REMOTE_DIR} && docker-compose -f docker-compose.prod.yml ps"

# Health checks
print_step "Performing health checks..."

# Check Redis
if ssh "${SSH_HOST}" "docker exec redis redis-cli -a \$(grep REDIS_PASSWORD ${REMOTE_DIR}/.env | cut -d'=' -f2) ping 2>/dev/null | grep -q PONG" 2>/dev/null; then
    print_status "✓ Redis is healthy"
else
    print_warning "⚠ Redis health check failed"
fi

# Check Elasticsearch
if ssh "${SSH_HOST}" "curl -f -u elastic:\$(grep ELASTICSEARCH_PASSWORD ${REMOTE_DIR}/.env | cut -d'=' -f2) http://localhost:9200/_cluster/health 2>/dev/null | grep -q green" 2>/dev/null; then
    print_status "✓ Elasticsearch is healthy"
else
    print_warning "⚠ Elasticsearch health check failed"
fi

# Check Backend
if ssh "${SSH_HOST}" "docker exec \$(docker ps -q -f name=kaleidoscope-app) curl -f http://localhost:8080/actuator/health 2>/dev/null | grep -q UP" 2>/dev/null; then
    print_status "✓ Backend is healthy"
else
    print_warning "⚠ Backend health check failed (may still be starting)"
fi

# Display running containers
print_step "Running containers:"
ssh "${SSH_HOST}" "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' | grep -E 'kaleidoscope|redis|elasticsearch|nginx'"

# Summary
echo ""
print_status "=========================================="
print_status "Deployment Summary"
print_status "=========================================="
echo ""
print_status "Backend Image: ${BACKEND_IMAGE}"
print_status "AI Services: ${#AI_SERVICES[@]} services updated"
echo ""
print_status "To view logs, run:"
echo "  ssh ${SSH_HOST} 'cd ${REMOTE_DIR} && docker-compose -f docker-compose.prod.yml logs -f'"
echo ""
print_status "To check service status:"
echo "  ssh ${SSH_HOST} 'cd ${REMOTE_DIR} && docker-compose -f docker-compose.prod.yml ps'"
echo ""
print_status "Deployment complete! ✓"

