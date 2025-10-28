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
echo -e "${BLUE}Step 2.5: Ensure Elasticsearch is Running${NC}"
docker-compose up -d elasticsearch >/dev/null 2>&1 || true
echo "Waiting for Elasticsearch to respond..."
for i in {1..12}; do
  if curl -sSf http://localhost:9200 >/dev/null 2>&1; then
    echo "Elasticsearch is up"
    break
  fi
  sleep 5
done

echo ""
echo -e "${BLUE}Step 2.6: Ensure es_sync consumer group exists${NC}"
docker exec kaleidoscope-redis-1 redis-cli XGROUP CREATE es-sync-queue es-sync-group $ MKSTREAM >/dev/null 2>&1 || true
docker exec kaleidoscope-redis-1 redis-cli XINFO GROUPS es-sync-queue || true

echo ""
echo -e "${BLUE}Step 3: Test Image Download (reliable source)${NC}"
docker exec kaleidoscope-image_tagger-1 sh -c "apt-get update -qq >/dev/null 2>&1 && apt-get install -y curl -qq >/dev/null 2>&1 && curl -sSI 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png' | head -5" || echo "Download test skipped"

echo ""
echo -e "${BLUE}Step 4: Sending Test Images${NC}"
# Reliable images
docker exec kaleidoscope-redis-1 redis-cli XADD post-image-processing "*" mediaId 77777 postId 77777 mediaUrl "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png" uploaderId 101
docker exec kaleidoscope-redis-1 redis-cli XADD post-image-processing "*" mediaId 66666 postId 66666 mediaUrl "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/React-icon.svg/512px-React-icon.svg.png" uploaderId 101
echo "Test images sent (mediaId: 77777, 66666), waiting 60 seconds for processing..."
sleep 60

echo ""
echo -e "${BLUE}Step 5: Checking ML Insights Results${NC}"
docker exec kaleidoscope-redis-1 redis-cli XREAD STREAMS ml-insights-results 0 | grep -A12 -E "77777|66666" || echo "No results found for mediaId 77777/66666"

echo ""
echo -e "${BLUE}Step 6: Checking Face Detection Results${NC}"
docker exec kaleidoscope-redis-1 redis-cli XREAD STREAMS face-detection-results 0 | grep -A12 -E "77777|66666" || echo "No face detection results for mediaId 77777/66666"

echo ""
echo -e "${BLUE}Step 7: Trigger Post Aggregation${NC}"
docker exec kaleidoscope-redis-1 redis-cli XADD post-aggregation-trigger "*" postId 77777 action aggregate
docker exec kaleidoscope-redis-1 redis-cli XADD post-aggregation-trigger "*" postId 66666 action aggregate
sleep 5

echo ""
echo -e "${BLUE}Step 8: Check Post Aggregation Results${NC}"
docker exec kaleidoscope-redis-1 redis-cli XREAD STREAMS post-insights-enriched 0 | grep -A12 -E "77777|66666"

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
echo -e "${BLUE}Step 10: Aggregator Logs & Re-trigger Aggregation${NC}"
echo "Aggregator logs (recent, filtered by postIds 77777/66666):"
docker-compose logs --tail=200 post_aggregator | grep -E "77777|66666" -n || true

echo "Re-trigger aggregation for both posts:"
docker exec kaleidoscope-redis-1 redis-cli XADD post-aggregation-trigger "*" postId 77777 action aggregate
docker exec kaleidoscope-redis-1 redis-cli XADD post-aggregation-trigger "*" postId 66666 action aggregate
sleep 3

echo "Blocking read (up to 20s) for enriched results:"
docker exec -it kaleidoscope-redis-1 redis-cli XREAD BLOCK 20000 STREAMS post-insights-enriched $ || true

echo "Full read of enriched stream (for verification):"
docker exec kaleidoscope-redis-1 redis-cli XREAD STREAMS post-insights-enriched 0 | grep -A12 -E "77777|66666" || true

echo ""
echo -e "${BLUE}Step 11: Trigger Stream Status${NC}"
docker exec kaleidoscope-redis-1 redis-cli XINFO STREAM post-aggregation-trigger | grep -E "length|entries|groups|last-generated-id" || true

echo ""
echo -e "${BLUE}Step 12: Elasticsearch & es_sync Health${NC}"
curl -s http://localhost:9200 | head -20 || true
docker-compose logs --tail=100 es_sync | tail -50 || true

echo ""
echo -e "${GREEN}✅ Comprehensive Test Complete${NC}"
echo ""
echo "Connection details for backend team:"
echo "- Redis: 165.232.179.167:6379"
echo "- Elasticsearch: http://165.232.179.167:9200"

