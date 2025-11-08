#!/bin/bash
# Comprehensive Test Script for Kaleidoscope AI Services

echo "🔍 Kaleidoscope AI Services - Comprehensive Test"
echo "================================================"
echo ""

# Load passwords from environment or use defaults
REDIS_PASSWORD=${REDIS_PASSWORD:-kaleidoscope1-reddis}
ELASTICSEARCH_PASSWORD=${ELASTICSEARCH_PASSWORD:-kaleidoscope1-elastic}

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Step 1: Service Health Check${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "redis|elasticsearch|content_moderation|image_tagger|scene_recognition|image_captioning|face_recognition|post_aggregator|es_sync"

echo ""
echo -e "${BLUE}Step 2: Check Recent Logs for Errors${NC}"
docker-compose -f docker-compose.prod.yml logs --tail=50 | grep -E "ERROR|error" | head -10 || echo "No errors found"

echo ""
echo -e "${BLUE}Step 2.5: Ensure Elasticsearch is Running${NC}"
docker-compose -f docker-compose.prod.yml up -d elasticsearch >/dev/null 2>&1 || true
echo "Waiting for Elasticsearch to respond..."
for i in {1..12}; do
  if curl -sSf -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200 >/dev/null 2>&1; then
    echo "Elasticsearch is up"
    break
  fi
  sleep 5
done

echo ""
echo -e "${BLUE}Step 2.6: Ensure es_sync consumer group exists${NC}"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE es-sync-queue es-sync-group $ MKSTREAM >/dev/null 2>&1 || true
docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO GROUPS es-sync-queue || true

echo ""
echo -e "${BLUE}Step 2.7: Ensure AI service consumer groups exist${NC}"
echo "Creating consumer groups for AI services on post-image-processing stream..."
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing content-moderation-group 0 MKSTREAM >/dev/null 2>&1 || true
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing image-tagger-group 0 MKSTREAM >/dev/null 2>&1 || true
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing scene-recognition-group 0 MKSTREAM >/dev/null 2>&1 || true
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing image-captioning-group 0 MKSTREAM >/dev/null 2>&1 || true
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing face-recognition-group 0 MKSTREAM >/dev/null 2>&1 || true
echo "Consumer groups created/verified"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO GROUPS post-image-processing || true

echo ""
echo -e "${BLUE}Step 2.8: Baseline Resource Usage${NC}"
echo "=== System Resources (Before Load) ==="
echo "Memory Usage:"
free -h
echo ""
echo "Disk Usage:"
df -h | grep -E "/$|/var"
echo ""
echo "Docker Container Resource Usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | grep -E "redis|elasticsearch|content_moderation|image_tagger|scene_recognition|image_captioning|face_recognition|post_aggregator|es_sync" || true

echo ""
echo -e "${BLUE}Step 3: Test Image Download (reliable source)${NC}"
docker exec image_tagger sh -c "apt-get update -qq >/dev/null 2>&1 && apt-get install -y curl -qq >/dev/null 2>&1 && curl -sSI 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png' | head -5" || echo "Download test skipped"

echo ""
echo -e "${BLUE}Step 4: Sending Test Images${NC}"
# Reliable images (using GitHub and a different reliable source)
docker exec redis redis-cli -a ${REDIS_PASSWORD} XADD post-image-processing "*" mediaId 77777 postId 77777 mediaUrl "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png" uploaderId 101 correlationId "test-77777"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XADD post-image-processing "*" mediaId 66666 postId 66666 mediaUrl "https://picsum.photos/seed/picsum/400/300" uploaderId 101 correlationId "test-66666"
echo "Test images sent (mediaId: 77777, 66666), waiting 60 seconds for processing..."

echo ""
echo -e "${BLUE}Step 4.5: Resource Usage During Processing${NC}"
echo "=== Resource Monitoring (During Load) ==="
for i in {1..12}; do
  echo "Check $i/12 - $(date '+%H:%M:%S')"
  echo "Memory: $(free -h | grep Mem | awk '{print $3"/"$2}')"
  echo "Docker Memory:"
  docker stats --no-stream --format "{{.Container}}: {{.MemUsage}}" | grep -E "redis|elasticsearch|content_moderation|image_tagger|scene_recognition|image_captioning|face_recognition|post_aggregator|es_sync" | head -5
  echo "---"
  sleep 5
done

echo ""
echo -e "${BLUE}Step 5: Checking ML Insights Results${NC}"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XREAD STREAMS ml-insights-results 0 | grep -A12 -E "77777|66666" || echo "No results found for mediaId 77777/66666"

echo ""
echo -e "${BLUE}Step 6: Checking Face Detection Results${NC}"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XREAD STREAMS face-detection-results 0 | grep -A12 -E "77777|66666" || echo "No face detection results for mediaId 77777/66666"

echo ""
echo -e "${BLUE}Step 7: Trigger Post Aggregation${NC}"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XADD post-aggregation-trigger "*" postId 77777 action aggregate correlationId "test-77777"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XADD post-aggregation-trigger "*" postId 66666 action aggregate correlationId "test-66666"
sleep 5

echo ""
echo -e "${BLUE}Step 8: Check Post Aggregation Results${NC}"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XREAD STREAMS post-insights-enriched 0 | grep -A12 -E "77777|66666"

echo ""
echo -e "${BLUE}Step 9: Stream Statistics${NC}"
echo "ML Insights Stream:"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO STREAM ml-insights-results | grep -E "length|entries"
echo ""
echo "Face Detection Stream:"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO STREAM face-detection-results | grep -E "length|entries"
echo ""
echo "Post Insights Enriched Stream:"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO STREAM post-insights-enriched | grep -E "length|entries"

echo ""
echo -e "${BLUE}Step 10: Aggregator Logs & Re-trigger Aggregation${NC}"
echo "Aggregator logs (recent, filtered by postIds 77777/66666):"
docker-compose -f docker-compose.prod.yml logs --tail=200 post_aggregator | grep -E "77777|66666" -n || true

echo "Re-trigger aggregation for both posts:"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XADD post-aggregation-trigger "*" postId 77777 action aggregate correlationId "test-77777"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XADD post-aggregation-trigger "*" postId 66666 action aggregate correlationId "test-66666"
sleep 3

echo "Blocking read (up to 20s) for enriched results:"
docker exec -it redis redis-cli -a ${REDIS_PASSWORD} XREAD BLOCK 20000 STREAMS post-insights-enriched $ || true

echo "Full read of enriched stream (for verification):"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XREAD STREAMS post-insights-enriched 0 | grep -A12 -E "77777|66666" || true

echo ""
echo -e "${BLUE}Step 10.1: Ensure Aggregator Group on Insights Stream${NC}"
echo "Confirm insights exist for posts:"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XREAD STREAMS ml-insights-results 0 | grep -A8 -E "77777|66666" || true

echo "Check aggregator environment (STREAM/GROUP vars):"
docker-compose -f docker-compose.prod.yml exec post_aggregator env | grep -E "STREAM|GROUP|REDIS" || true

echo "Create consumer group on ml-insights-results if missing:"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE ml-insights-results post-aggregator-group 0 MKSTREAM >/dev/null 2>&1 || true
docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO GROUPS ml-insights-results || true

echo "Restart post_aggregator to join group:"
docker-compose -f docker-compose.prod.yml restart post_aggregator
sleep 3

echo "Re-trigger aggregation and block read for enriched results:"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XADD post-aggregation-trigger "*" postId 77777 action aggregate correlationId "test-77777"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XADD post-aggregation-trigger "*" postId 66666 action aggregate correlationId "test-66666"
docker exec -it redis redis-cli -a ${REDIS_PASSWORD} XREAD BLOCK 20000 STREAMS post-insights-enriched $ || true

echo ""
echo -e "${BLUE}Step 11: Trigger Stream Status${NC}"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO STREAM post-aggregation-trigger | grep -E "length|entries|groups|last-generated-id" || true

echo ""
echo -e "${BLUE}Step 12: Elasticsearch & es_sync Health${NC}"
curl -s -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200 | head -20 || true
docker-compose -f docker-compose.prod.yml logs --tail=100 es_sync | tail -50 || true

echo ""
echo -e "${BLUE}Step 13: Final Resource Usage Analysis${NC}"
echo "=== System Resources (After Load) ==="
echo "Memory Usage:"
free -h
echo ""
echo "Disk Usage:"
df -h | grep -E "/$|/var"
echo ""
echo "Docker Container Resource Usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | grep -E "redis|elasticsearch|content_moderation|image_tagger|scene_recognition|image_captioning|face_recognition|post_aggregator|es_sync" || true

echo ""
echo -e "${BLUE}Step 14: Resource Usage Summary${NC}"
echo "=== Peak Load Analysis ==="
echo "System Memory:"
echo "- Total: $(free -h | grep Mem | awk '{print $2}')"
echo "- Used: $(free -h | grep Mem | awk '{print $3}')"
echo "- Available: $(free -h | grep Mem | awk '{print $7}')"
echo "- Usage %: $(free | grep Mem | awk '{printf "%.1f%%", $3/$2 * 100.0}')"
echo ""
echo "Docker Memory Usage:"
docker stats --no-stream --format "{{.Container}}: {{.MemUsage}} ({{.MemPerc}})" | grep -E "redis|elasticsearch|content_moderation|image_tagger|scene_recognition|image_captioning|face_recognition|post_aggregator|es_sync" | sort -k3 -hr || true
echo ""
echo "Disk Space:"
df -h | grep -E "/$|/var" | awk '{print $1 ": " $3 "/" $2 " (" $5 " used)"}'

echo ""
echo -e "${GREEN}✅ Comprehensive Test Complete${NC}"
echo ""
echo "Connection details for backend team:"
echo "- Redis: 165.232.179.167:6379"
echo "- Elasticsearch: http://165.232.179.167:9200"

