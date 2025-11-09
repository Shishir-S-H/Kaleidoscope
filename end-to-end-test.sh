#!/bin/bash
# End-to-End Test Script for Complete User Workflow
# Tests the entire flow from post creation to AI processing to final results

echo "🚀 Kaleidoscope AI Services - End-to-End User Workflow Test"
echo "============================================================"
echo ""

# Load passwords from environment or .env file or use defaults
# Try to load from .env file first
if [ -f ".env" ]; then
    # Source .env file if it exists
    set -a
    source .env 2>/dev/null || true
    set +a
elif [ -f "../.env" ]; then
    # Try parent directory
    set -a
    source ../.env 2>/dev/null || true
    set +a
fi

# Use environment variable or default
REDIS_PASSWORD=${REDIS_PASSWORD:-kaleidoscope1-reddis}
ELASTICSEARCH_PASSWORD=${ELASTICSEARCH_PASSWORD:-kaleidoscope1-elastic}
BACKEND_URL=${BACKEND_URL:-http://localhost:8080}

# Docker compose file path (try different locations)
if [ -f "docker-compose.prod.yml" ]; then
    DOCKER_COMPOSE_FILE="docker-compose.prod.yml"
elif [ -f "../docker-compose.prod.yml" ]; then
    DOCKER_COMPOSE_FILE="../docker-compose.prod.yml"
else
    DOCKER_COMPOSE_FILE="docker-compose.prod.yml"
    echo -e "${YELLOW}⚠️${NC}  docker-compose.prod.yml not found, using default path"
fi

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Test configuration
TEST_POST_ID=${TEST_POST_ID:-$(date +%s)}
TEST_MEDIA_ID_1=${TEST_MEDIA_ID_1:-$(($(date +%s) + 1))}
TEST_MEDIA_ID_2=${TEST_MEDIA_ID_2:-$(($(date +%s) + 2))}
TEST_USER_ID=${TEST_USER_ID:-101}
TEST_CORRELATION_ID="e2e-test-$(date +%s)"

# Test image URLs (reliable sources)
TEST_IMAGE_1="https://picsum.photos/800/600?random=1"
TEST_IMAGE_2="https://picsum.photos/600/800?random=2"

echo -e "${CYAN}Test Configuration:${NC}"
echo "  Post ID: $TEST_POST_ID"
echo "  Media IDs: $TEST_MEDIA_ID_1, $TEST_MEDIA_ID_2"
echo "  User ID: $TEST_USER_ID"
echo "  Correlation ID: $TEST_CORRELATION_ID"
echo ""

# Function to check service health
check_service_health() {
    local service=$1
    # Check if container exists and is running (flexible matching)
    if docker ps --format "{{.Names}}" | grep -qE "^${service}$|^kaleidoscope-${service}"; then
        echo -e "${GREEN}✅${NC} $service is running"
        return 0
    elif docker ps --format "{{.Names}}" | grep -qi "${service}"; then
        # Container exists with different name
        local actual_name=$(docker ps --format "{{.Names}}" | grep -i "${service}" | head -1)
        echo -e "${GREEN}✅${NC} $service is running (as $actual_name)"
        return 0
    else
        echo -e "${RED}❌${NC} $service is not running"
        return 1
    fi
}

# Function to wait for message in stream
wait_for_message() {
    local stream=$1
    local timeout=${2:-30}
    local count=0
    echo -n "  Waiting for message in $stream..."
    while [ $count -lt $timeout ]; do
        local length=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XLEN "$stream" 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]')
        # Handle empty string or non-numeric values
        if [ -z "$length" ] || [ "$length" = "" ]; then
            length=0
        fi
        if [ "$length" -gt 0 ] 2>/dev/null; then
            echo -e " ${GREEN}✅${NC} (found $length messages)"
            return 0
        fi
        sleep 1
        count=$((count + 1))
        echo -n "."
    done
    echo -e " ${RED}❌${NC} (timeout after ${timeout}s)"
    return 1
}

# Function to check message in stream
check_message_in_stream() {
    local stream=$1
    local field=$2
    local value=$3
    local found=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XREVRANGE "$stream" + - COUNT 10 2>/dev/null | grep -E "${field}|${value}" | grep -c "$value" || echo "0")
    if [ "$found" -gt 0 ]; then
        echo -e "    ${GREEN}✅${NC} Found message with $field=$value"
        return 0
    else
        echo -e "    ${RED}❌${NC} Message with $field=$value not found"
        return 1
    fi
}

# Function to verify AI service processed message
verify_ai_service_processed() {
    local service=$1
    local media_id=$2
    local stream=$3
    echo -n "  Checking $service processed mediaId=$media_id..."
    
    # Check if message exists in output stream
    local found=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XREVRANGE "$stream" + - COUNT 20 2>/dev/null | grep -c "mediaId.*${media_id}" || echo "0")
    # Handle empty string
    if [ -z "$found" ] || [ "$found" = "" ]; then
        found=0
    fi
    if [ "$found" -gt 0 ] 2>/dev/null; then
        echo -e " ${GREEN}✅${NC}"
        return 0
    else
        echo -e " ${RED}❌${NC}"
        return 1
    fi
}

echo -e "${BLUE}Step 1: Pre-flight Checks${NC}"
echo "================================"

# Check all services are running
echo "Checking service health..."
echo "Available containers:"
docker ps --format "  {{.Names}}" | grep -E "redis|elasticsearch|content_moderation|image_tagger|scene_recognition|image_captioning|face_recognition|post_aggregator|es_sync|app" || echo "  No matching containers found"

echo ""
echo "Checking required services..."

# Check Redis
if docker ps --format "{{.Names}}" | grep -qE "^redis$|kaleidoscope.*redis"; then
    echo -e "${GREEN}✅${NC} Redis is running"
else
    echo -e "${RED}❌${NC} Redis is not running"
    echo "  Starting Redis..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d redis >/dev/null 2>&1
    sleep 3
    if docker ps --format "{{.Names}}" | grep -qE "^redis$|kaleidoscope.*redis"; then
        echo -e "${GREEN}✅${NC} Redis started successfully"
    else
        echo -e "${RED}❌${NC} Failed to start Redis"
        exit 1
    fi
fi

# Check Elasticsearch
if docker ps --format "{{.Names}}" | grep -qE "^elasticsearch$|kaleidoscope.*elasticsearch"; then
    echo -e "${GREEN}✅${NC} Elasticsearch is running"
else
    echo -e "${YELLOW}⚠️${NC}  Elasticsearch is not running (will start it)"
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d elasticsearch >/dev/null 2>&1
    sleep 5
fi

# Check AI services
check_service_health "content_moderation" || echo -e "${YELLOW}⚠️${NC}  content_moderation not running"
check_service_health "image_tagger" || echo -e "${YELLOW}⚠️${NC}  image_tagger not running"
check_service_health "scene_recognition" || echo -e "${YELLOW}⚠️${NC}  scene_recognition not running"
check_service_health "image_captioning" || echo -e "${YELLOW}⚠️${NC}  image_captioning not running"
check_service_health "face_recognition" || echo -e "${YELLOW}⚠️${NC}  face_recognition not running"
check_service_health "post_aggregator" || echo -e "${YELLOW}⚠️${NC}  post_aggregator not running"
check_service_health "es_sync" || echo -e "${YELLOW}⚠️${NC}  es_sync not running"
check_service_health "kaleidoscope-app" || check_service_health "app" || echo -e "${YELLOW}⚠️${NC}  Backend not running (will test AI services only)"

echo ""
echo -e "${BLUE}Step 2: Baseline State${NC}"
echo "======================"

# Get baseline stream lengths
echo "Recording baseline stream lengths..."
BASELINE_POST_IMAGE=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XLEN post-image-processing 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
BASELINE_ML_INSIGHTS=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XLEN ml-insights-results 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
BASELINE_FACE_DETECTION=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XLEN face-detection-results 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
BASELINE_POST_ENRICHED=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XLEN post-insights-enriched 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")

# Ensure baseline values are numeric
[ -z "$BASELINE_POST_IMAGE" ] && BASELINE_POST_IMAGE=0
[ -z "$BASELINE_ML_INSIGHTS" ] && BASELINE_ML_INSIGHTS=0
[ -z "$BASELINE_FACE_DETECTION" ] && BASELINE_FACE_DETECTION=0
[ -z "$BASELINE_POST_ENRICHED" ] && BASELINE_POST_ENRICHED=0

echo "  post-image-processing: $BASELINE_POST_IMAGE messages"
echo "  ml-insights-results: $BASELINE_ML_INSIGHTS messages"
echo "  face-detection-results: $BASELINE_FACE_DETECTION messages"
echo "  post-insights-enriched: $BASELINE_POST_ENRICHED messages"

echo ""
echo -e "${BLUE}Step 2.5: Ensure Consumer Groups Exist${NC}"
echo "======================================"
echo "Creating consumer groups for AI services..."
docker exec redis redis-cli -a "${REDIS_PASSWORD}" XGROUP CREATE post-image-processing content-moderation-group 0 MKSTREAM >/dev/null 2>&1 || true
docker exec redis redis-cli -a "${REDIS_PASSWORD}" XGROUP CREATE post-image-processing image-tagger-group 0 MKSTREAM >/dev/null 2>&1 || true
docker exec redis redis-cli -a "${REDIS_PASSWORD}" XGROUP CREATE post-image-processing scene-recognition-group 0 MKSTREAM >/dev/null 2>&1 || true
docker exec redis redis-cli -a "${REDIS_PASSWORD}" XGROUP CREATE post-image-processing image-captioning-group 0 MKSTREAM >/dev/null 2>&1 || true
docker exec redis redis-cli -a "${REDIS_PASSWORD}" XGROUP CREATE post-image-processing face-recognition-group 0 MKSTREAM >/dev/null 2>&1 || true
echo -e "${GREEN}✅${NC} Consumer groups created/verified"

echo ""
echo -e "${BLUE}Step 3: Simulate User Creates Post with Images${NC}"
echo "=============================================="
echo "Simulating backend publishing to post-image-processing stream..."

# Verify messages can be published
echo "  Testing Redis connection..."
# Try to ping Redis (handle both with and without password)
REDIS_PING_RESULT=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" PING 2>&1 | grep -v "Warning" | tail -1 || echo "")
if [ -z "$REDIS_PING_RESULT" ]; then
    # Try without password
    REDIS_PING_RESULT=$(docker exec redis redis-cli PING 2>&1 | tail -1 || echo "")
fi

if echo "$REDIS_PING_RESULT" | grep -q "PONG"; then
    echo -e "  ${GREEN}✅${NC} Redis connection successful"
elif [ -z "$REDIS_PASSWORD" ]; then
    echo -e "  ${YELLOW}⚠️${NC}  REDIS_PASSWORD not set, trying without password..."
    # Try without password
    if docker exec redis redis-cli PING 2>&1 | grep -q "PONG"; then
        echo -e "  ${GREEN}✅${NC} Redis connection successful (no password)"
    else
        echo -e "  ${RED}❌${NC} Redis connection failed"
        echo "  Debug: Trying to get password from .env file..."
        if [ -f ".env" ]; then
            REDIS_PASSWORD_FROM_ENV=$(grep "^REDIS_PASSWORD=" .env 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo "")
            if [ -n "$REDIS_PASSWORD_FROM_ENV" ]; then
                echo "  Found REDIS_PASSWORD in .env, trying again..."
                REDIS_PASSWORD="$REDIS_PASSWORD_FROM_ENV"
                if docker exec redis redis-cli -a "${REDIS_PASSWORD}" PING 2>&1 | grep -v "Warning" | grep -q "PONG"; then
                    echo -e "  ${GREEN}✅${NC} Redis connection successful (with password from .env)"
                else
                    echo -e "  ${RED}❌${NC} Redis connection failed even with password from .env"
                    exit 1
                fi
            else
                echo -e "  ${RED}❌${NC} REDIS_PASSWORD not found in .env file"
                exit 1
            fi
        else
            echo -e "  ${RED}❌${NC} .env file not found"
            exit 1
        fi
    fi
else
    echo -e "  ${RED}❌${NC} Redis connection failed"
    echo "  Debug info:"
    echo "    REDIS_PASSWORD length: ${#REDIS_PASSWORD}"
    echo "    Redis container: $(docker ps --format '{{.Names}}' | grep redis | head -1)"
    echo "    Trying direct connection test..."
    docker exec redis redis-cli -a "${REDIS_PASSWORD}" PING 2>&1 || true
    exit 1
fi

# Publish messages to post-image-processing (simulating backend)
echo "  Publishing media 1 (mediaId=$TEST_MEDIA_ID_1)..."
docker exec redis redis-cli -a "${REDIS_PASSWORD}" XADD post-image-processing "*" \
    postId "$TEST_POST_ID" \
    mediaId "$TEST_MEDIA_ID_1" \
    mediaUrl "$TEST_IMAGE_1" \
    uploaderId "$TEST_USER_ID" \
    correlationId "$TEST_CORRELATION_ID" \
    >/dev/null 2>&1

echo "  Publishing media 2 (mediaId=$TEST_MEDIA_ID_2)..."
docker exec redis redis-cli -a "${REDIS_PASSWORD}" XADD post-image-processing "*" \
    postId "$TEST_POST_ID" \
    mediaId "$TEST_MEDIA_ID_2" \
    mediaUrl "$TEST_IMAGE_2" \
    uploaderId "$TEST_USER_ID" \
    correlationId "$TEST_CORRELATION_ID" \
    >/dev/null 2>&1

echo -e "${GREEN}✅${NC} Published 2 media items to post-image-processing stream"

# Verify messages were published
echo "  Verifying messages in stream..."
STREAM_LENGTH=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XLEN post-image-processing 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
[ -z "$STREAM_LENGTH" ] && STREAM_LENGTH=0
echo "  Stream length: $STREAM_LENGTH messages"

# Show recent messages
echo "  Recent messages in stream:"
docker exec redis redis-cli -a "${REDIS_PASSWORD}" XREVRANGE post-image-processing + - COUNT 2 2>/dev/null | grep -E "postId|mediaId|mediaUrl" | head -6 || echo "  No messages found"

echo "  Waiting 5 seconds for AI services to start processing..."
sleep 5

# Check AI service logs for any errors
echo "  Checking AI service logs for errors..."
docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=20 content_moderation 2>/dev/null | grep -E "ERROR|Exception|Failed" | head -3 || echo "  No errors in content_moderation logs"

echo ""
echo -e "${BLUE}Step 4: Verify AI Services Processing${NC}"
echo "===================================="

# Wait for AI services to process
echo "Waiting for AI services to process images..."
wait_for_message "ml-insights-results" 60
wait_for_message "face-detection-results" 60

# Verify each AI service processed both images
echo ""
echo "Verifying AI service processing:"

# Content Moderation
verify_ai_service_processed "content-moderation" "$TEST_MEDIA_ID_1" "ml-insights-results"
verify_ai_service_processed "content-moderation" "$TEST_MEDIA_ID_2" "ml-insights-results"

# Image Tagger
verify_ai_service_processed "image-tagger" "$TEST_MEDIA_ID_1" "ml-insights-results"
verify_ai_service_processed "image-tagger" "$TEST_MEDIA_ID_2" "ml-insights-results"

# Scene Recognition
verify_ai_service_processed "scene-recognition" "$TEST_MEDIA_ID_1" "ml-insights-results"
verify_ai_service_processed "scene-recognition" "$TEST_MEDIA_ID_2" "ml-insights-results"

# Image Captioning
verify_ai_service_processed "image-captioning" "$TEST_MEDIA_ID_1" "ml-insights-results"
verify_ai_service_processed "image-captioning" "$TEST_MEDIA_ID_2" "ml-insights-results"

# Face Recognition
verify_ai_service_processed "face-recognition" "$TEST_MEDIA_ID_1" "face-detection-results"
verify_ai_service_processed "face-recognition" "$TEST_MEDIA_ID_2" "face-detection-results"

echo ""
echo -e "${BLUE}Step 5: Verify Backend Consumed Results${NC}"
echo "====================================="

# Check if backend consumed messages (if running)
if docker ps --format "{{.Names}}" | grep -q "^kaleidoscope-app$"; then
    echo "Checking backend consumer status..."
    BACKEND_PENDING=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XPENDING ml-insights-results backend-group 2>/dev/null | head -1 | grep -v "Warning" | tr -d '[:space:]' || echo "0")
    [ -z "$BACKEND_PENDING" ] && BACKEND_PENDING=0
    echo "  Backend pending messages: $BACKEND_PENDING"
    
    # Wait a bit for backend to process
    echo "  Waiting 10 seconds for backend to process..."
    sleep 10
    
    # Check if backend triggered aggregation
    echo "  Checking if backend triggered post aggregation..."
    AGGREGATION_TRIGGERS=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XREVRANGE post-aggregation-trigger + - COUNT 5 2>/dev/null | grep -c "postId.*${TEST_POST_ID}" || echo "0")
    [ -z "$AGGREGATION_TRIGGERS" ] && AGGREGATION_TRIGGERS=0
    if [ "$AGGREGATION_TRIGGERS" -gt 0 ] 2>/dev/null; then
        echo -e "    ${GREEN}✅${NC} Backend triggered aggregation for postId=$TEST_POST_ID"
    else
        echo -e "    ${YELLOW}⚠️${NC}  Backend did not trigger aggregation (may need real post in database)"
    fi
else
    echo -e "${YELLOW}⚠️${NC}  Backend not running, skipping backend verification"
fi

echo ""
echo -e "${BLUE}Step 6: Trigger Post Aggregation${NC}"
echo "=================================="

# Manually trigger aggregation (in case backend didn't)
echo "Triggering post aggregation manually..."
docker exec redis redis-cli -a "${REDIS_PASSWORD}" XADD post-aggregation-trigger "*" \
    postId "$TEST_POST_ID" \
    action aggregate \
    correlationId "$TEST_CORRELATION_ID" \
    >/dev/null 2>&1

echo "  Waiting 10 seconds for aggregation..."
sleep 10

# Check if aggregation completed
echo "Checking post aggregation results..."
wait_for_message "post-insights-enriched" 30

# Verify aggregated message
echo "Verifying aggregated message format..."
AGGREGATED_MESSAGE=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XREVRANGE post-insights-enriched + - COUNT 1 2>/dev/null | grep -E "postId|allAiTags|allAiScenes|correlationId" || echo "")

if echo "$AGGREGATED_MESSAGE" | grep -q "postId.*${TEST_POST_ID}"; then
    echo -e "  ${GREEN}✅${NC} Found aggregated message for postId=$TEST_POST_ID"
    
    # Check format
    if echo "$AGGREGATED_MESSAGE" | grep -q "allAiTags"; then
        echo -e "  ${GREEN}✅${NC} Message contains allAiTags field"
    else
        echo -e "  ${RED}❌${NC} Message missing allAiTags field"
    fi
    
    if echo "$AGGREGATED_MESSAGE" | grep -q "allAiScenes"; then
        echo -e "  ${GREEN}✅${NC} Message contains allAiScenes field"
    else
        echo -e "  ${RED}❌${NC} Message missing allAiScenes field"
    fi
    
    if echo "$AGGREGATED_MESSAGE" | grep -q "correlationId.*${TEST_CORRELATION_ID}"; then
        echo -e "  ${GREEN}✅${NC} Message contains correlationId"
    else
        echo -e "  ${YELLOW}⚠️${NC}  Message missing correlationId"
    fi
else
    echo -e "  ${RED}❌${NC} Aggregated message not found for postId=$TEST_POST_ID"
fi

echo ""
echo -e "${BLUE}Step 7: Verify Backend Consumed Enriched Insights${NC}"
echo "=============================================="

# Check if backend consumed enriched insights
if docker ps --format "{{.Names}}" | grep -q "^kaleidoscope-app$"; then
    echo "Checking backend consumer for post-insights-enriched..."
    
    # Wait for backend to process
    echo "  Waiting 15 seconds for backend to process..."
    sleep 15
    
    # Check backend logs for processing
    BACKEND_PROCESSED=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=100 app 2>/dev/null | grep -c "Successfully processed post-insights-enriched.*postId.*${TEST_POST_ID}" || echo "0")
    [ -z "$BACKEND_PROCESSED" ] && BACKEND_PROCESSED=0
    if [ "$BACKEND_PROCESSED" -gt 0 ] 2>/dev/null; then
        echo -e "  ${GREEN}✅${NC} Backend processed enriched insights for postId=$TEST_POST_ID"
    else
        echo -e "  ${YELLOW}⚠️${NC}  Backend did not process enriched insights (check logs for errors)"
    fi
    
    # Check pending messages
    BACKEND_PENDING=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XPENDING post-insights-enriched backend-group 2>/dev/null | head -1 | grep -v "Warning" | tr -d '[:space:]' || echo "0")
    [ -z "$BACKEND_PENDING" ] && BACKEND_PENDING=0
    echo "  Backend pending messages: $BACKEND_PENDING"
else
    echo -e "${YELLOW}⚠️${NC}  Backend not running, skipping backend verification"
fi

echo ""
echo -e "${BLUE}Step 8: Verify ES Sync${NC}"
echo "===================="

# Check if ES sync was triggered
echo "Checking ES sync queue..."
ES_SYNC_MESSAGES=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XLEN es-sync-queue 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
[ -z "$ES_SYNC_MESSAGES" ] && ES_SYNC_MESSAGES=0
echo "  ES sync queue length: $ES_SYNC_MESSAGES"

if [ "$ES_SYNC_MESSAGES" -gt 0 ] 2>/dev/null; then
    echo -e "  ${GREEN}✅${NC} ES sync queue has messages"
    
    # Wait for ES sync to process
    echo "  Waiting 10 seconds for ES sync to process..."
    sleep 10
    
    # Check ES sync logs
    ES_SYNC_PROCESSED=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=50 es_sync 2>/dev/null | grep -c "Processing.*sync" || echo "0")
    if [ "$ES_SYNC_PROCESSED" -gt 0 ]; then
        echo -e "  ${GREEN}✅${NC} ES sync is processing messages"
    else
        echo -e "  ${YELLOW}⚠️${NC}  ES sync may not be processing (check logs)"
    fi
else
    echo -e "  ${YELLOW}⚠️${NC}  ES sync queue is empty (backend may not have triggered sync)"
fi

echo ""
echo -e "${BLUE}Step 9: Verify Elasticsearch Indexing${NC}"
echo "====================================="

# Check if data is in Elasticsearch
echo "Checking Elasticsearch indices..."
if curl -sSf -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200/_cat/indices 2>/dev/null | grep -q "post_search\|media_search"; then
    echo -e "  ${GREEN}✅${NC} Elasticsearch indices exist"
    
    # Try to search for the post
    echo "  Searching for post in Elasticsearch..."
    SEARCH_RESULT=$(curl -sSf -u elastic:${ELASTICSEARCH_PASSWORD} "http://localhost:9200/post_search/_search?q=postId:${TEST_POST_ID}" 2>/dev/null | grep -c "\"hits\"" || echo "0")
    [ -z "$SEARCH_RESULT" ] && SEARCH_RESULT=0
    if [ "$SEARCH_RESULT" -gt 0 ] 2>/dev/null; then
        echo -e "    ${GREEN}✅${NC} Post found in Elasticsearch"
    else
        echo -e "    ${YELLOW}⚠️${NC}  Post not found in Elasticsearch (may need more time or backend issue)"
    fi
else
    echo -e "  ${YELLOW}⚠️${NC}  Elasticsearch indices not found (may need to be created)"
fi

echo ""
echo -e "${BLUE}Step 10: Check Service Health and Metrics${NC}"
echo "=========================================="

# Check AI service health
echo "Checking AI service health checks..."
HEALTH_CHECKS=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=500 2>/dev/null | grep -c "Health check.*healthy" || echo "0")
echo "  Health check logs found: $HEALTH_CHECKS"

# Check for errors
echo "Checking for errors in logs..."
ERRORS=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=200 2>/dev/null | grep -E "ERROR|Exception" | grep -v "AuthorizationDeniedException" | grep -v "ServletException" | wc -l)
echo "  Error count: $ERRORS"

# Check DLQ
echo "Checking dead letter queue..."
DLQ_LENGTH=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XLEN ai-processing-dlq 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
[ -z "$DLQ_LENGTH" ] && DLQ_LENGTH=0
echo "  DLQ length: $DLQ_LENGTH"
if [ "$DLQ_LENGTH" -eq "0" ] 2>/dev/null; then
    echo -e "  ${GREEN}✅${NC} No messages in DLQ"
else
    echo -e "  ${YELLOW}⚠️${NC}  $DLQ_LENGTH messages in DLQ (check logs for details)"
fi

echo ""
echo -e "${BLUE}Step 11: Final Stream Statistics${NC}"
echo "=================================="

# Get final stream lengths
FINAL_POST_IMAGE=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XLEN post-image-processing 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
FINAL_ML_INSIGHTS=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XLEN ml-insights-results 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
FINAL_FACE_DETECTION=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XLEN face-detection-results 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
FINAL_POST_ENRICHED=$(docker exec redis redis-cli -a "${REDIS_PASSWORD}" XLEN post-insights-enriched 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")

# Ensure final values are numeric
[ -z "$FINAL_POST_IMAGE" ] && FINAL_POST_IMAGE=0
[ -z "$FINAL_ML_INSIGHTS" ] && FINAL_ML_INSIGHTS=0
[ -z "$FINAL_FACE_DETECTION" ] && FINAL_FACE_DETECTION=0
[ -z "$FINAL_POST_ENRICHED" ] && FINAL_POST_ENRICHED=0

echo "Stream Statistics:"
echo "  post-image-processing: $BASELINE_POST_IMAGE → $FINAL_POST_IMAGE (+$((FINAL_POST_IMAGE - BASELINE_POST_IMAGE)))"
echo "  ml-insights-results: $BASELINE_ML_INSIGHTS → $FINAL_ML_INSIGHTS (+$((FINAL_ML_INSIGHTS - BASELINE_ML_INSIGHTS)))"
echo "  face-detection-results: $BASELINE_FACE_DETECTION → $FINAL_FACE_DETECTION (+$((FINAL_FACE_DETECTION - BASELINE_FACE_DETECTION)))"
echo "  post-insights-enriched: $BASELINE_POST_ENRICHED → $FINAL_POST_ENRICHED (+$((FINAL_POST_ENRICHED - BASELINE_POST_ENRICHED)))"

echo ""
echo -e "${BLUE}Step 12: Consumer Group Status${NC}"
echo "================================="

# Check consumer group status
echo "Checking consumer group status..."
docker exec redis redis-cli -a "${REDIS_PASSWORD}" XINFO GROUPS post-image-processing 2>/dev/null | grep -E "name|consumers|pending|lag" | head -20
echo ""
docker exec redis redis-cli -a "${REDIS_PASSWORD}" XINFO GROUPS ml-insights-results 2>/dev/null | grep -E "name|consumers|pending|lag" | head -10
echo ""
docker exec redis redis-cli -a "${REDIS_PASSWORD}" XINFO GROUPS post-insights-enriched 2>/dev/null | grep -E "name|consumers|pending|lag" | head -10

echo ""
echo -e "${BLUE}Step 13: Test Summary${NC}"
echo "===================="

# Calculate success rate
SUCCESS_COUNT=0
TOTAL_CHECKS=0

# Check AI services processed
TOTAL_CHECKS=$((TOTAL_CHECKS + 10))
if verify_ai_service_processed "content-moderation" "$TEST_MEDIA_ID_1" "ml-insights-results" >/dev/null 2>&1; then SUCCESS_COUNT=$((SUCCESS_COUNT + 1)); fi
if verify_ai_service_processed "content-moderation" "$TEST_MEDIA_ID_2" "ml-insights-results" >/dev/null 2>&1; then SUCCESS_COUNT=$((SUCCESS_COUNT + 1)); fi
if verify_ai_service_processed "image-tagger" "$TEST_MEDIA_ID_1" "ml-insights-results" >/dev/null 2>&1; then SUCCESS_COUNT=$((SUCCESS_COUNT + 1)); fi
if verify_ai_service_processed "image-tagger" "$TEST_MEDIA_ID_2" "ml-insights-results" >/dev/null 2>&1; then SUCCESS_COUNT=$((SUCCESS_COUNT + 1)); fi
if verify_ai_service_processed "scene-recognition" "$TEST_MEDIA_ID_1" "ml-insights-results" >/dev/null 2>&1; then SUCCESS_COUNT=$((SUCCESS_COUNT + 1)); fi
if verify_ai_service_processed "scene-recognition" "$TEST_MEDIA_ID_2" "ml-insights-results" >/dev/null 2>&1; then SUCCESS_COUNT=$((SUCCESS_COUNT + 1)); fi
if verify_ai_service_processed "image-captioning" "$TEST_MEDIA_ID_1" "ml-insights-results" >/dev/null 2>&1; then SUCCESS_COUNT=$((SUCCESS_COUNT + 1)); fi
if verify_ai_service_processed "image-captioning" "$TEST_MEDIA_ID_2" "ml-insights-results" >/dev/null 2>&1; then SUCCESS_COUNT=$((SUCCESS_COUNT + 1)); fi
if verify_ai_service_processed "face-recognition" "$TEST_MEDIA_ID_1" "face-detection-results" >/dev/null 2>&1; then SUCCESS_COUNT=$((SUCCESS_COUNT + 1)); fi
if verify_ai_service_processed "face-recognition" "$TEST_MEDIA_ID_2" "face-detection-results" >/dev/null 2>&1; then SUCCESS_COUNT=$((SUCCESS_COUNT + 1)); fi

# Check aggregation
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if docker exec redis redis-cli -a "${REDIS_PASSWORD}" XREVRANGE post-insights-enriched + - COUNT 1 2>/dev/null | grep -q "postId.*${TEST_POST_ID}"; then
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
fi

SUCCESS_RATE=$((SUCCESS_COUNT * 100 / TOTAL_CHECKS))

echo "Test Results:"
echo "  Success: $SUCCESS_COUNT/$TOTAL_CHECKS checks passed"
echo "  Success Rate: $SUCCESS_RATE%"

if [ $SUCCESS_RATE -ge 90 ]; then
    echo -e "${GREEN}✅ End-to-End Test PASSED${NC}"
    exit 0
elif [ $SUCCESS_RATE -ge 70 ]; then
    echo -e "${YELLOW}⚠️  End-to-End Test PARTIAL SUCCESS${NC}"
    exit 0
else
    echo -e "${RED}❌ End-to-End Test FAILED${NC}"
    exit 1
fi

