#!/bin/bash

# Kaleidoscope AI Services Monitoring Script
# Run this script to check service health

echo "🔍 Kaleidoscope AI Services Health Check"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to check service
check_service() {
    local service_name=$1
    local command=$2
    
    if eval $command > /dev/null 2>&1; then
        echo -e "${GREEN}✅ $service_name${NC}"
        return 0
    else
        echo -e "${RED}❌ $service_name${NC}"
        return 1
    fi
}

# Check Redis
echo "📊 Checking Redis..."
check_service "Redis" "docker exec kaleidoscope-redis-1 redis-cli ping"

# Check Elasticsearch
echo "📊 Checking Elasticsearch..."
check_service "Elasticsearch" "curl -s http://localhost:9200 > /dev/null"

# Check AI Services (they don't have HTTP endpoints, so check if containers are running)
echo "📊 Checking AI Services..."
check_service "Content Moderation" "docker ps | grep content_moderation"
check_service "Image Tagger" "docker ps | grep image_tagger"
check_service "Scene Recognition" "docker ps | grep scene_recognition"
check_service "Image Captioning" "docker ps | grep image_captioning"
check_service "Face Recognition" "docker ps | grep face_recognition"
check_service "Post Aggregator" "docker ps | grep post_aggregator"
check_service "ES Sync" "docker ps | grep es_sync"

echo ""
echo "📈 System Resources:"
echo "==================="

# Check memory usage
echo "💾 Memory Usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep kaleidoscope

echo ""
echo "🔗 Connection Details:"
echo "====================="
echo "Redis: 165.232.179.167:6379"
echo "Elasticsearch: http://165.232.179.167:9200"
echo ""

echo "📋 Quick Commands:"
echo "=================="
echo "View logs: docker-compose -f docker-compose.yml logs -f"
echo "Restart services: docker-compose -f docker-compose.yml restart"
echo "Stop services: docker-compose -f docker-compose.yml down"
echo "Start services: docker-compose -f docker-compose.yml up -d"
