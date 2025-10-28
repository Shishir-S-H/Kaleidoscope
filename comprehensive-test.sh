#!/bin/bash
# Comprehensive Test Script for Kaleidoscope AI Services

echo "🔍 Kaleidoscope AI Services - Comprehensive Test"
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Step 1: Service Health Check${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep kaleidoscope

echo ""
echo -e "${BLUE}Step 2: Check Recent Logs for Errors${NC}"
docker-compose logs --tail=50 | grep -E "ERROR|error" | head -10 || echo "No errors found"

echo ""
echo -e "${BLUE}Step 3: Test Image Download from Wikimedia${NC}"
docker exec kaleidoscope-image_tagger-1 sh -c "apt-get update -qq >/dev/null 2>&1 && apt-get install -y curl -qq >/dev/null 2>&1 && curl -sSI 'https://upload.wikimedia.org/wikipedia/commons/3/3f/Fronalpstock_big.jpg' | head -5" || echo "Wikimedia download test skipped"

echo ""
echo -e "${BLUE}Step 4: Sending Test Images${NC}"
docker exec kaleidoscope-redis-1 redis-cli XADD post-image-processing "*" mediaId 99999 postId 99999 mediaUrl "https://placekitten.com/640/360" uploaderId 101
echo "Test image sent (mediaId: 99999), waiting 45 seconds for processing..."
sleep 45

echo ""
echo -e "${BLUE}Step 5: Checking ML Insights Results${NC}"
docker exec kaleidoscope-redis-1 redis-cli XREAD STREAMS ml-insights-results 0 | grep -A12 "99999" || echo "No results found for mediaId 99999"

echo ""
echo -e "${BLUE}Step 6: Checking Face Detection Results${NC}"
docker exec kaleidoscope-redis-1 redis-cli XREAD STREAMS face-detection-results 0 | grep -A12 "99999" || echo "No face detection results for mediaId 99999"

echo ""
echo -e "${BLUE}Step 7: Trigger Post Aggregation${NC}"
docker exec kaleidoscope-redis-1 redis-cli XADD post-aggregation-trigger "*" postId 99999 action aggregate
sleep 5

echo ""
echo -e "${BLUE}Step 8: Check Post Aggregation Results${NC}"
docker exec kaleidoscope-redis-1 redis-cli XREAD STREAMS post-insights-enriched 0 | grep -A12 "99999"

echo ""
echo -e "${BLUE}Step 9: Stream Statistics${NC}"
echo "ML Insights Stream:"
docker exec kaleidoscope-redis-1 redis-cli XINFO STREAM ml-insights-results | grep -E "length|entries"
echo ""
echo "Face Detection Stream:"
docker exec kaleidoscope-redis-1 redis-cli XINFO STREAM face-detection-results | grep -E "length|entries"
echo ""
echo "Post Insights Enriched Stream:"
docker exec kaleidoscope-redis-1 redis-cli XINFO STREAM post-insights-enriched | grep -E "length|entries"

echo ""
echo -e "${GREEN}✅ Comprehensive Test Complete${NC}"
echo ""
echo "Connection details for backend team:"
echo "- Redis: 165.232.179.167:6379"
echo "- Elasticsearch: http://165.232.179.167:9200"

