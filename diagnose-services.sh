#!/bin/bash
# Diagnostic Script for Kaleidoscope AI Services

echo "🔍 Kaleidoscope AI Services - Diagnostic Check"
echo "=============================================="
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

echo -e "${BLUE}Step 1: Check Consumer Groups on post-image-processing${NC}"
echo "Consumer groups:"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO GROUPS post-image-processing 2>/dev/null || echo "Stream doesn't exist or has no groups"

echo ""
echo -e "${BLUE}Step 2: Check if messages are still pending${NC}"
echo "Pending messages in stream:"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO STREAM post-image-processing 2>/dev/null | grep -E "length|first-entry|last-entry" || echo "Stream doesn't exist"

echo ""
echo -e "${BLUE}Step 3: Check Recent Messages in Stream${NC}"
echo "Last 5 messages:"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XREVRANGE post-image-processing + - COUNT 5 2>/dev/null || echo "No messages found"

echo ""
echo -e "${BLUE}Step 4: Check AI Service Logs for Errors${NC}"
echo "Content Moderation:"
docker-compose -f docker-compose.prod.yml logs --tail=20 content_moderation | grep -E "ERROR|error|Received|Ready" | tail -5

echo ""
echo "Image Tagger:"
docker-compose -f docker-compose.prod.yml logs --tail=20 image_tagger | grep -E "ERROR|error|Received|Ready" | tail -5

echo ""
echo "Scene Recognition:"
docker-compose -f docker-compose.prod.yml logs --tail=20 scene_recognition | grep -E "ERROR|error|Received|Ready" | tail -5

echo ""
echo "Image Captioning:"
docker-compose -f docker-compose.prod.yml logs --tail=20 image_captioning | grep -E "ERROR|error|Received|Ready" | tail -5

echo ""
echo "Face Recognition:"
docker-compose -f docker-compose.prod.yml logs --tail=20 face_recognition | grep -E "ERROR|error|Received|Ready" | tail -5

echo ""
echo -e "${BLUE}Step 5: Check if Consumer Groups Need to be Created${NC}"
echo "Creating consumer groups if missing..."

# Create consumer groups for AI services
echo "Creating content-moderation-group..."
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing content-moderation-group 0 MKSTREAM >/dev/null 2>&1 && echo "✅ Created content-moderation-group" || echo "⚠️  content-moderation-group already exists"

echo "Creating image-tagger-group..."
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing image-tagger-group 0 MKSTREAM >/dev/null 2>&1 && echo "✅ Created image-tagger-group" || echo "⚠️  image-tagger-group already exists"

echo "Creating scene-recognition-group..."
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing scene-recognition-group 0 MKSTREAM >/dev/null 2>&1 && echo "✅ Created scene-recognition-group" || echo "⚠️  scene-recognition-group already exists"

echo "Creating image-captioning-group..."
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing image-captioning-group 0 MKSTREAM >/dev/null 2>&1 && echo "✅ Created image-captioning-group" || echo "⚠️  image-captioning-group already exists"

echo "Creating face-recognition-group..."
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing face-recognition-group 0 MKSTREAM >/dev/null 2>&1 && echo "✅ Created face-recognition-group" || echo "⚠️  face-recognition-group already exists"

echo ""
echo -e "${BLUE}Step 6: Restart Services to Join Groups${NC}"
echo "Restarting AI services..."
docker-compose -f docker-compose.prod.yml restart content_moderation image_tagger scene_recognition image_captioning face_recognition
sleep 5

echo ""
echo -e "${BLUE}Step 7: Send Test Message${NC}"
TEST_MEDIA_ID=88888
TEST_POST_ID=88888
docker exec redis redis-cli -a ${REDIS_PASSWORD} XADD post-image-processing "*" mediaId $TEST_MEDIA_ID postId $TEST_POST_ID mediaUrl "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png" uploaderId 101 correlationId "test-88888"
echo "Test message sent (mediaId: $TEST_MEDIA_ID, postId: $TEST_POST_ID)"
echo "Waiting 30 seconds for processing..."
sleep 30

echo ""
echo -e "${BLUE}Step 8: Check Results${NC}"
echo "ML Insights Results:"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XREAD STREAMS ml-insights-results 0 | grep -A10 $TEST_MEDIA_ID || echo "No results found"

echo ""
echo "Face Detection Results:"
docker exec redis redis-cli -a ${REDIS_PASSWORD} XREAD STREAMS face-detection-results 0 | grep -A10 $TEST_MEDIA_ID || echo "No results found"

echo ""
echo -e "${GREEN}✅ Diagnostic Complete${NC}"

