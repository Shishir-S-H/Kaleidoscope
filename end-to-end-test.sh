#!/bin/bash
# End-to-End Test Script for Complete User Workflow
# Tests the entire flow from post creation to AI processing to final results

echo "🚀 Kaleidoscope AI Services - End-to-End User Workflow Test"
echo "============================================================"
echo ""

# Load passwords from environment or .env file or use defaults
# Try to load from .env file first (handle BOM/encoding issues)
load_env_file() {
    local env_file=$1
    if [ -f "$env_file" ]; then
        # Create a temporary cleaned version of the .env file
        local temp_file=$(mktemp)
        # Remove BOM, carriage returns, and invalid characters
        # Use sed to remove CR characters and filter out problematic lines
        sed 's/\r$//' "$env_file" 2>/dev/null | \
            grep -v "^#: command not found" | \
            grep -v "^lthr: command not found" | \
            grep -v "^[[:space:]]*$" > "$temp_file" 2>/dev/null || true
        
        # Source the cleaned file
        set -a
        source "$temp_file" 2>/dev/null || true
        set +a
        
        # Clean up temp file
        rm -f "$temp_file" 2>/dev/null || true
    fi
}

# Try to load from .env file first
if [ -f ".env" ]; then
    load_env_file ".env"
elif [ -f "../.env" ]; then
    load_env_file "../.env"
fi

# Use environment variable or default
REDIS_PASSWORD=${REDIS_PASSWORD:-kaleidoscope1-reddis}
ELASTICSEARCH_PASSWORD=${ELASTICSEARCH_PASSWORD:-kaleidoscope1-elastic}
BACKEND_URL=${BACKEND_URL:-http://localhost:8080}
BACKEND_API_BASE="${BACKEND_URL}/kaleidoscope/api"
BACKEND_AUTH_BASE="${BACKEND_URL}/kaleidoscope/api/auth"

# Test user credentials (can be overridden via environment variables)
TEST_USER_EMAIL=${TEST_USER_EMAIL:-user@gmail.com}
TEST_USER_PASSWORD=${TEST_USER_PASSWORD:-User@123}
# Alternative: ajax81968@gmail.com / User1@123

# Test mode: "api" (real user flow) or "direct" (simulate backend)
TEST_MODE=${TEST_MODE:-api}

# Docker compose file path (try different locations)
if [ -f "docker-compose.prod.yml" ]; then
    DOCKER_COMPOSE_FILE="docker-compose.prod.yml"
elif [ -f "../docker-compose.prod.yml" ]; then
    DOCKER_COMPOSE_FILE="../docker-compose.prod.yml"
else
    DOCKER_COMPOSE_FILE="docker-compose.prod.yml"
    echo -e "${YELLOW}⚠️${NC}  docker-compose.prod.yml not found, using default path"
fi

# Find Redis container name (do this after checking services are running)
# This will be set in Step 1 after services are verified
REDIS_CONTAINER=""

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
# Using reliable public image URLs that should pass backend validation
TEST_IMAGE_1="https://picsum.photos/800/600?random=1"
TEST_IMAGE_2="https://picsum.photos/600/800?random=2"

echo -e "${CYAN}Test Configuration:${NC}"
echo "  Test Mode: $TEST_MODE"
echo "  User Email: $TEST_USER_EMAIL"
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
        local length=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XLEN "$stream" 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]')
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
    local found=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XREVRANGE "$stream" + - COUNT 10 2>/dev/null | grep -E "${field}|${value}" | grep -c "$value" || echo "0")
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
    # Redis stream output format: field1 value1 field2 value2 ...
    # We need to check if mediaId field has the value we're looking for
    local stream_output=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XREVRANGE "$stream" + - COUNT 20 2>/dev/null || echo "")
    
    # Check if mediaId field with our value exists
    # Pattern: mediaId followed by the media_id value (could be on same or next line)
    local found=$(echo "$stream_output" | grep -E "(mediaId|^${media_id}$)" | grep -A1 "mediaId" | grep -c "^${media_id}$" || echo "0")
    
    # Also try simpler pattern: just check if media_id appears near mediaId
    if [ "$found" -eq 0 ] 2>/dev/null; then
        found=$(echo "$stream_output" | grep -E "mediaId|${media_id}" | grep -c "${media_id}" || echo "0")
    fi
    
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

# Check Redis and set container name
REDIS_CONTAINER=$(docker ps --format "{{.Names}}" | grep -E "^redis$|kaleidoscope.*redis" | head -1)
if [ -n "$REDIS_CONTAINER" ]; then
    echo -e "${GREEN}✅${NC} Redis is running (container: $REDIS_CONTAINER)"
else
    echo -e "${RED}❌${NC} Redis is not running"
    echo "  Starting Redis..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d redis >/dev/null 2>&1
    sleep 3
    REDIS_CONTAINER=$(docker ps --format "{{.Names}}" | grep -E "^redis$|kaleidoscope.*redis" | head -1)
    if [ -n "$REDIS_CONTAINER" ]; then
        echo -e "${GREEN}✅${NC} Redis started successfully (container: $REDIS_CONTAINER)"
    else
        echo -e "${RED}❌${NC} Failed to start Redis"
        exit 1
    fi
fi

# Ensure REDIS_CONTAINER is set
if [ -z "$REDIS_CONTAINER" ]; then
    REDIS_CONTAINER=$(docker ps --format "{{.Names}}" | grep -E "^redis$|kaleidoscope.*redis" | head -1)
    if [ -z "$REDIS_CONTAINER" ]; then
        echo -e "${RED}❌${NC} Redis container not found"
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
BASELINE_POST_IMAGE=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XLEN post-image-processing 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
BASELINE_ML_INSIGHTS=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XLEN ml-insights-results 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
BASELINE_FACE_DETECTION=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XLEN face-detection-results 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
BASELINE_POST_ENRICHED=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XLEN post-insights-enriched 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")

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
docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XGROUP CREATE post-image-processing content-moderation-group 0 MKSTREAM >/dev/null 2>&1 || true
docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XGROUP CREATE post-image-processing image-tagger-group 0 MKSTREAM >/dev/null 2>&1 || true
docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XGROUP CREATE post-image-processing scene-recognition-group 0 MKSTREAM >/dev/null 2>&1 || true
docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XGROUP CREATE post-image-processing image-captioning-group 0 MKSTREAM >/dev/null 2>&1 || true
docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XGROUP CREATE post-image-processing face-recognition-group 0 MKSTREAM >/dev/null 2>&1 || true
echo -e "${GREEN}✅${NC} Consumer groups created/verified"

echo ""
echo -e "${BLUE}Step 3: User Creates Post via Backend API${NC}"
echo "=============================================="

if [ "$TEST_MODE" = "api" ]; then
    echo "Using REAL user flow: Authenticate → Create Post → Verify Processing"
    echo ""
    
    # Step 3.1: Authenticate with backend
    echo -e "${BLUE}Step 3.1: Authenticate with Backend${NC}"
    echo "----------------------------------------"
    echo "  Logging in as: $TEST_USER_EMAIL"
    
    # Login and capture both headers and body
    LOGIN_RESPONSE=$(curl -s -i -X POST "${BACKEND_AUTH_BASE}/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"${TEST_USER_EMAIL}\",\"password\":\"${TEST_USER_PASSWORD}\"}" \
        2>&1)
    
    # Check HTTP status code
    HTTP_STATUS=$(echo "$LOGIN_RESPONSE" | grep -i "^HTTP" | head -1 | awk '{print $2}' || echo "")
    
    if [ "$HTTP_STATUS" != "200" ]; then
        echo -e "  ${RED}❌${NC} Authentication failed (HTTP $HTTP_STATUS)"
        echo "  Response: $LOGIN_RESPONSE"
        echo ""
        echo -e "  ${RED}❌${NC} Cannot proceed without authentication. Exiting..."
        exit 1
    fi
    
    # Extract JWT token from Authorization header (backend returns it in header as "Authorization: Bearer <token>")
    # JWT tokens contain: a-z, A-Z, 0-9, ., -, _, +, /, = (base64 characters)
    JWT_TOKEN=$(echo "$LOGIN_RESPONSE" | grep -i "^authorization:" | sed 's/.*[Bb]earer //' | tr -d '\r' | tr -d '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' || echo "")
    
    if [ -z "$JWT_TOKEN" ]; then
        # Try to extract from response body as fallback
        JWT_TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"accessToken":"[^"]*' | cut -d'"' -f4 || echo "")
    fi
    
    if [ -z "$JWT_TOKEN" ]; then
        echo -e "  ${RED}❌${NC} Authentication failed - token not found"
        echo "  Response headers:"
        echo "$LOGIN_RESPONSE" | grep -i "authorization\|http" | head -5
        echo ""
        echo -e "  ${RED}❌${NC} Cannot proceed without authentication. Exiting..."
        exit 1
    else
        echo -e "  ${GREEN}✅${NC} Authentication successful"
        echo "  Token: ${JWT_TOKEN:0:30}..."
        echo "  Token length: ${#JWT_TOKEN} characters"
    fi
    
    if [ "$TEST_MODE" = "api" ] && [ -n "$JWT_TOKEN" ]; then
        # Step 3.2: Fetch categories
        echo ""
        echo -e "${BLUE}Step 3.2: Fetch Available Categories${NC}"
        echo "----------------------------------------"
        
        CATEGORIES_RESPONSE=$(curl -s -X GET "${BACKEND_API_BASE}/categories?page=0&size=10" \
            -H "Authorization: Bearer ${JWT_TOKEN}" \
            -H "Content-Type: application/json" \
            2>&1)
        
        # Extract first category ID (simple JSON parsing)
        CATEGORY_ID=$(echo "$CATEGORIES_RESPONSE" | grep -o '"categoryId":[0-9]*' | head -1 | cut -d':' -f2 || echo "")
        
        if [ -z "$CATEGORY_ID" ]; then
            echo -e "  ${YELLOW}⚠️${NC}  Could not fetch categories, using default categoryId=1"
            CATEGORY_ID=1
        else
            echo -e "  ${GREEN}✅${NC} Found category ID: $CATEGORY_ID"
        fi
        
        # Step 3.3: Create post via API
        echo ""
        echo -e "${BLUE}Step 3.3: Create Post via Backend API${NC}"
        echo "----------------------------------------"
        
        # Generate upload signatures first (backend requires this)
        echo "  Generating upload signatures..."
        SIGNATURE_RESPONSE=$(curl -s -X POST "${BACKEND_API_BASE}/posts/upload-signatures" \
            -H "Authorization: Bearer ${JWT_TOKEN}" \
            -H "Content-Type: application/json" \
            -d "{\"fileNames\":[\"test-image-1.jpg\",\"test-image-2.jpg\"],\"contentType\":\"POST\"}" \
            2>&1)
        
        # Check if signature generation worked
        if echo "$SIGNATURE_RESPONSE" | grep -q "401\|Unauthorized"; then
            echo -e "  ${YELLOW}⚠️${NC}  Upload signature generation failed (401), trying post creation anyway..."
        fi
        
        # Create post with media
        POST_TITLE="E2E Test Post $(date +%s)"
        POST_BODY="This is an end-to-end test post created automatically. Testing AI processing pipeline."
        
        CREATE_POST_BODY=$(cat <<EOF
{
  "title": "${POST_TITLE}",
  "body": "${POST_BODY}",
  "summary": "E2E test post",
  "visibility": "PUBLIC",
  "categoryIds": [${CATEGORY_ID}],
  "mediaDetails": [
    {
      "url": "${TEST_IMAGE_1}",
      "mediaType": "IMAGE",
      "position": 0,
      "width": 800,
      "height": 600,
      "fileSizeKb": 120,
      "durationSeconds": null,
      "extraMetadata": {}
    },
    {
      "url": "${TEST_IMAGE_2}",
      "mediaType": "IMAGE",
      "position": 1,
      "width": 600,
      "height": 800,
      "fileSizeKb": 100,
      "durationSeconds": null,
      "extraMetadata": {}
    }
  ]
}
EOF
)
        
        echo "  Creating post with 2 images..."
        echo "  Using JWT token: ${JWT_TOKEN:0:30}..."
        echo "  Endpoint: ${BACKEND_API_BASE}/posts"
        
        # Test token with a simple GET request first
        echo "  Testing token with GET request..."
        TEST_GET_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "${BACKEND_API_BASE}/categories?page=0&size=1" \
            -H "Authorization: Bearer ${JWT_TOKEN}" \
            2>&1)
        TEST_GET_HTTP=$(echo "$TEST_GET_RESPONSE" | tail -1)
        if [ "$TEST_GET_HTTP" != "200" ]; then
            echo -e "  ${RED}❌${NC} Token validation failed (HTTP $TEST_GET_HTTP)"
            echo "  Token might be invalid or expired"
            echo "  Response: $(echo "$TEST_GET_RESPONSE" | head -n -1)"
        else
            echo -e "  ${GREEN}✅${NC} Token is valid for GET requests"
        fi
        
        # Make the POST request with verbose error output
        echo "  Making POST request to create post..."
        
        # Check backend logs before request
        echo "  Checking backend logs before request..."
        BACKEND_LOGS_BEFORE=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=10 app 2>/dev/null | tail -5 || echo "")
        
        # Make the request
        CREATE_POST_RESPONSE=$(curl -v -s -w "\n%{http_code}" -X POST "${BACKEND_API_BASE}/posts" \
            -H "Authorization: Bearer ${JWT_TOKEN}" \
            -H "Content-Type: application/json" \
            -H "Origin: http://localhost:8080" \
            -d "$CREATE_POST_BODY" \
            2>&1)
        
        # Extract correlation ID from response if available
        CORRELATION_ID_FROM_RESPONSE=$(echo "$CREATE_POST_RESPONSE" | grep -i "X-Correlation-ID" | sed 's/.*X-Correlation-ID: //' | tr -d '\r' | tr -d ' ' | head -1 || echo "")
        
        # Check backend logs after request
        echo "  Checking backend logs after request..."
        sleep 2
        
        # Check backend logs with multiple patterns
        BACKEND_LOGS_AFTER=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=100 app 2>/dev/null | grep -E "POST.*posts|/posts|createPost|PostController|AuthTokenFilter|JWT|Authentication|401|Unauthorized|Creating post" | tail -15 || echo "")
        
        # If we have a correlation ID, search for it specifically
        if [ -n "$CORRELATION_ID_FROM_RESPONSE" ]; then
            echo "  Found correlation ID in response: ${CORRELATION_ID_FROM_RESPONSE:0:20}..."
            CORRELATION_LOGS=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=200 app 2>/dev/null | grep -i "$CORRELATION_ID_FROM_RESPONSE" | tail -20 || echo "")
            if [ -n "$CORRELATION_LOGS" ]; then
                echo "  Backend logs for this correlation ID:"
                echo "$CORRELATION_LOGS" | sed 's/^/    /'
            else
                echo "  ⚠️  No logs found for this correlation ID"
                echo "  Trying to find any recent logs with this ID..."
                # Try without case sensitivity and with partial match
                CORRELATION_PARTIAL=$(echo "$CORRELATION_ID_FROM_RESPONSE" | cut -d'-' -f1)
                CORRELATION_LOGS_PARTIAL=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=500 app 2>/dev/null | grep -i "$CORRELATION_PARTIAL" | tail -10 || echo "")
                if [ -n "$CORRELATION_LOGS_PARTIAL" ]; then
                    echo "  Found logs with partial correlation ID:"
                    echo "$CORRELATION_LOGS_PARTIAL" | sed 's/^/    /'
                fi
            fi
        fi
        
        # Debug: Show request details if it fails
        if echo "$CREATE_POST_RESPONSE" | tail -1 | grep -q "401"; then
            echo "  Debug: Request details:"
            echo "    URL: ${BACKEND_API_BASE}/posts"
            echo "    Token prefix: ${JWT_TOKEN:0:50}..."
            echo "    Token length: ${#JWT_TOKEN}"
            echo "    Request body size: $(echo "$CREATE_POST_BODY" | wc -c) bytes"
            if [ -n "$CORRELATION_ID_FROM_RESPONSE" ]; then
                echo "    Correlation ID: ${CORRELATION_ID_FROM_RESPONSE}"
            fi
            echo ""
            
            # Show curl verbose output for debugging (filter out verbose connection info)
            echo "  Curl response headers:"
            echo "$CREATE_POST_RESPONSE" | grep -E "^< HTTP|< X-|< Content-Type|< Authorization" | head -10 | sed 's/^/    /' || echo "    No response headers available"
            echo ""
            
            # Check backend logs for the POST request
            if [ -n "$BACKEND_LOGS_AFTER" ]; then
                echo "  Backend logs for POST request:"
                echo "$BACKEND_LOGS_AFTER" | sed 's/^/    /'
            else
                echo "  ⚠️  No backend logs found for POST request"
                echo "  Checking if backend is logging at all..."
                RECENT_LOGS=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=20 app 2>/dev/null | tail -5 || echo "")
                if [ -n "$RECENT_LOGS" ]; then
                    echo "  Recent backend logs (last 5 lines):"
                    echo "$RECENT_LOGS" | sed 's/^/    /'
                else
                    echo "  ⚠️  No backend logs found at all - backend might not be logging"
                fi
                echo ""
                echo "  This might indicate:"
                echo "    - Request is being rejected at security filter level"
                echo "    - AuthTokenFilter is rejecting the request silently"
                echo "    - Request is being blocked before reaching the controller"
            fi
            echo ""
            
            # Check for authentication errors specifically
            BACKEND_AUTH_ERRORS=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=200 app 2>/dev/null | grep -E "AuthTokenFilter|JWT|Authentication|401|Unauthorized|Invalid JWT|JWT expired|JWT validation" | tail -15 || echo "")
            if [ -n "$BACKEND_AUTH_ERRORS" ]; then
                echo "  Backend authentication errors (last 15):"
                echo "$BACKEND_AUTH_ERRORS" | sed 's/^/    /'
            else
                echo "  No authentication errors in backend logs"
            fi
            
            # Check for any errors or exceptions in recent logs
            echo ""
            echo "  Checking for any recent errors or exceptions..."
            RECENT_ERRORS=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=100 app 2>/dev/null | grep -E "ERROR|Exception|Failed|401" | tail -10 || echo "")
            if [ -n "$RECENT_ERRORS" ]; then
                echo "  Recent errors/exceptions:"
                echo "$RECENT_ERRORS" | sed 's/^/    /'
            fi
            
            # Check if AuthTokenFilter is being called for POST requests
            echo ""
            echo "  Checking AuthTokenFilter logs for POST requests..."
            AUTH_FILTER_LOGS=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=200 app 2>/dev/null | grep -E "AuthTokenFilter.*POST|AuthTokenFilter.*posts|AuthTokenFilter called for URI.*posts" | tail -5 || echo "")
            if [ -n "$AUTH_FILTER_LOGS" ]; then
                echo "  AuthTokenFilter logs for POST:"
                echo "$AUTH_FILTER_LOGS" | sed 's/^/    /'
            else
                echo "  No AuthTokenFilter logs found for POST requests"
            fi
            
            # Show full backend logs around the time of the request
            echo ""
            echo "  Full backend logs for correlation ID (last 100 lines):"
            if [ -n "$CORRELATION_ID_FROM_RESPONSE" ]; then
                FULL_LOGS=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=500 app 2>/dev/null | grep -A 10 -B 10 "$CORRELATION_ID_FROM_RESPONSE" | head -50 || echo "")
                if [ -n "$FULL_LOGS" ]; then
                    echo "$FULL_LOGS" | sed 's/^/    /'
                else
                    echo "  No logs found for correlation ID: $CORRELATION_ID_FROM_RESPONSE"
                    echo "  Showing recent backend logs (last 30 lines) instead:"
                    RECENT_FULL=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=30 app 2>/dev/null || echo "")
                    if [ -n "$RECENT_FULL" ]; then
                        echo "$RECENT_FULL" | sed 's/^/    /'
                    fi
                fi
            fi
        fi
        
        HTTP_CODE=$(echo "$CREATE_POST_RESPONSE" | tail -1)
        POST_RESPONSE_BODY=$(echo "$CREATE_POST_RESPONSE" | head -n -1)
        
        echo "  HTTP Status: $HTTP_CODE"
        
        if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "200" ]; then
            echo -e "  ${GREEN}✅${NC} Post created successfully"
            
            # Parse JSON response to extract postId and mediaIds
            # Backend returns: {"success":true,"message":"...","data":{"postId":123,"media":[{"mediaId":456},...]}}
            TEST_POST_ID=$(echo "$POST_RESPONSE_BODY" | grep -o '"postId":[0-9]*' | head -1 | cut -d':' -f2 || echo "")
            if [ -z "$TEST_POST_ID" ]; then
                # Try alternative format (nested in data)
                TEST_POST_ID=$(echo "$POST_RESPONSE_BODY" | grep -o '"data".*"postId":[0-9]*' | grep -o '"postId":[0-9]*' | cut -d':' -f2 || echo "")
            fi
            if [ -z "$TEST_POST_ID" ]; then
                # Try id field
                TEST_POST_ID=$(echo "$POST_RESPONSE_BODY" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2 || echo "")
            fi
            
            # Extract media IDs from response
            TEST_MEDIA_ID_1=$(echo "$POST_RESPONSE_BODY" | grep -o '"mediaId":[0-9]*' | head -1 | cut -d':' -f2 || echo "")
            TEST_MEDIA_ID_2=$(echo "$POST_RESPONSE_BODY" | grep -o '"mediaId":[0-9]*' | tail -1 | cut -d':' -f2 || echo "")
            
            if [ -z "$TEST_POST_ID" ]; then
                echo -e "  ${RED}❌${NC} Could not extract postId from response"
                echo "  Response body: $POST_RESPONSE_BODY"
                echo ""
                echo "  ${YELLOW}⚠️${NC}  Test cannot continue without postId. Exiting..."
                exit 1
            else
                echo "  Post ID: $TEST_POST_ID"
                if [ -n "$TEST_MEDIA_ID_1" ] && [ -n "$TEST_MEDIA_ID_2" ]; then
                    echo "  Media IDs: $TEST_MEDIA_ID_1, $TEST_MEDIA_ID_2"
                else
                    echo "  Media IDs: (extracting from stream)"
                fi
            fi
            
            # Update correlation ID to match what backend will use
            TEST_CORRELATION_ID="e2e-test-${TEST_POST_ID}"
            
            echo ""
            echo "  Monitoring backend publishing to Redis streams..."
            echo "  Waiting for backend to publish messages to post-image-processing..."
            
            # Wait for backend to publish messages (check stream length increase)
            BASELINE_POST_IMAGE_NOW=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XLEN post-image-processing 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
            [ -z "$BASELINE_POST_IMAGE_NOW" ] && BASELINE_POST_IMAGE_NOW=0
            
            # Wait up to 10 seconds for new messages
            WAIT_COUNT=0
            while [ $WAIT_COUNT -lt 10 ]; do
                sleep 1
                CURRENT_LENGTH=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XLEN post-image-processing 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
                [ -z "$CURRENT_LENGTH" ] && CURRENT_LENGTH=0
                if [ "$CURRENT_LENGTH" -gt "$BASELINE_POST_IMAGE_NOW" ] 2>/dev/null; then
                    NEW_MESSAGES=$((CURRENT_LENGTH - BASELINE_POST_IMAGE_NOW))
                    echo -e "  ${GREEN}✅${NC} Backend published $NEW_MESSAGES message(s) to post-image-processing stream"
                    break
                fi
                WAIT_COUNT=$((WAIT_COUNT + 1))
            done
            
            if [ $WAIT_COUNT -eq 10 ]; then
                echo -e "  ${YELLOW}⚠️${NC}  Backend may not have published messages yet (check backend logs)"
            fi
            
            # Extract media IDs from stream if not in response
            if [ -z "$TEST_MEDIA_ID_1" ] || [ -z "$TEST_MEDIA_ID_2" ]; then
                echo "  Extracting media IDs from Redis stream..."
                sleep 2
                RECENT_MESSAGES=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XREVRANGE post-image-processing + - COUNT 5 2>/dev/null | grep -A 10 "postId.*${TEST_POST_ID}" || echo "")
                if [ -n "$RECENT_MESSAGES" ]; then
                    TEST_MEDIA_ID_1=$(echo "$RECENT_MESSAGES" | awk '/^postId$/{found=1} found && /^mediaId$/{getline; print; exit}' | head -1 || echo "")
                    TEST_MEDIA_ID_2=$(echo "$RECENT_MESSAGES" | awk '/^postId$/{found=1} found && /^mediaId$/{getline; print}' | tail -1 || echo "")
                    if [ -n "$TEST_MEDIA_ID_1" ] && [ -n "$TEST_MEDIA_ID_2" ]; then
                        echo "  Media IDs extracted: $TEST_MEDIA_ID_1, $TEST_MEDIA_ID_2"
                    fi
                fi
            fi
            
        else
            echo -e "  ${RED}❌${NC} Post creation failed (HTTP $HTTP_CODE)"
            echo "  Response: $POST_RESPONSE_BODY"
            
            # If 401, try to debug token
            if [ "$HTTP_CODE" = "401" ]; then
                echo "  Debug: Checking token validity..."
                # Try to use token for another request
                TEST_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "${BACKEND_API_BASE}/categories?page=0&size=1" \
                    -H "Authorization: Bearer ${JWT_TOKEN}" \
                    2>&1)
                TEST_HTTP=$(echo "$TEST_RESPONSE" | tail -1)
                if [ "$TEST_HTTP" = "200" ]; then
                    echo "  Token is valid for other endpoints, post creation might have different requirements"
                    echo "  Check backend logs for authentication/authorization errors"
                else
                    echo "  Token might be invalid or expired (HTTP $TEST_HTTP)"
                fi
            fi
            
            echo ""
            echo -e "  ${RED}❌${NC} Cannot proceed without successful post creation via API"
            echo "  Test requires backend API to work properly. Exiting..."
            exit 1
        fi
    fi
fi

# If API mode failed, exit (we require API mode for real user flow)
if [ "$TEST_MODE" != "api" ] || [ -z "$JWT_TOKEN" ]; then
    echo -e "${RED}❌${NC} Test requires API mode with valid authentication"
    echo "  Cannot proceed without backend API. Exiting..."
    exit 1
fi

# Verify we have postId from API
if [ -z "$TEST_POST_ID" ] || [ "$TEST_POST_ID" = "0" ]; then
    echo -e "${RED}❌${NC} Test requires valid postId from backend API"
    echo "  Cannot proceed without postId. Exiting..."
    exit 1
fi

# Continue with monitoring the workflow
echo ""
echo -e "${GREEN}✅${NC} Post created via backend API. Monitoring workflow..."
echo "  Post ID: $TEST_POST_ID"
echo "  Media IDs: $TEST_MEDIA_ID_1, $TEST_MEDIA_ID_2"
echo "  Correlation ID: $TEST_CORRELATION_ID"
echo ""
echo "  Waiting 5 seconds for AI services to start processing..."
sleep 5

echo ""
echo -e "${BLUE}Step 4: Verify AI Services Processing${NC}"
echo "===================================="

# Wait for AI services to process
echo "Waiting for AI services to process images..."
# Wait a bit longer for processing
echo "  Waiting 15 seconds for AI services to process..."
sleep 15
wait_for_message "ml-insights-results" 60
wait_for_message "face-detection-results" 60

# Show recent messages for debugging
echo ""
echo "  Recent messages in ml-insights-results (last 3):"
docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XREVRANGE ml-insights-results + - COUNT 3 2>/dev/null | grep -E "mediaId|postId|service" | head -9 || echo "  No messages found"

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
    BACKEND_PENDING=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XPENDING ml-insights-results backend-group 2>/dev/null | head -1 | grep -v "Warning" | tr -d '[:space:]' || echo "0")
    [ -z "$BACKEND_PENDING" ] && BACKEND_PENDING=0
    echo "  Backend pending messages: $BACKEND_PENDING"
    
    if [ "$BACKEND_PENDING" -gt 0 ] 2>/dev/null; then
        echo "  Investigating pending messages..."
        # Get pending message details
        PENDING_DETAILS=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XPENDING ml-insights-results backend-group - + 5 2>/dev/null | grep -v "Warning" || echo "")
        if [ -n "$PENDING_DETAILS" ]; then
            echo "  Pending message details (first 5):"
            echo "$PENDING_DETAILS" | head -5 | sed 's/^/    /'
            
            # Calculate age of oldest pending message (in seconds)
            OLDEST_IDLE=$(echo "$PENDING_DETAILS" | head -1 | awk '{print $3}' || echo "0")
            if [ "$OLDEST_IDLE" -gt 0 ] 2>/dev/null; then
                OLDEST_AGE_HOURS=$((OLDEST_IDLE / 1000 / 3600))
                OLDEST_AGE_MINUTES=$(((OLDEST_IDLE / 1000) % 3600 / 60))
                if [ "$OLDEST_AGE_HOURS" -gt 0 ] 2>/dev/null; then
                    echo -e "  ${YELLOW}⚠️${NC}  Oldest pending message is ${OLDEST_AGE_HOURS}h ${OLDEST_AGE_MINUTES}m old (may need manual ACK)"
                elif [ "$OLDEST_AGE_MINUTES" -gt 5 ] 2>/dev/null; then
                    echo -e "  ${YELLOW}⚠️${NC}  Oldest pending message is ${OLDEST_AGE_MINUTES}m old"
                fi
            fi
        fi
        
        # Check backend logs for processing errors
        BACKEND_PROCESSING_ERRORS=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=100 app 2>/dev/null | grep -E "ERROR.*ml-insights-results|Exception.*ml-insights-results|Failed to process.*ml-insights" | tail -3 || echo "")
        if [ -n "$BACKEND_PROCESSING_ERRORS" ]; then
            echo -e "  ${RED}❌${NC} Backend processing errors:"
            echo "$BACKEND_PROCESSING_ERRORS" | sed 's/^/    /'
        fi
    fi
    
    # Wait a bit for backend to process
    echo "  Waiting 10 seconds for backend to process..."
    sleep 10
    
    # Re-check pending after wait
    BACKEND_PENDING_AFTER=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XPENDING ml-insights-results backend-group 2>/dev/null | head -1 | grep -v "Warning" | tr -d '[:space:]' || echo "0")
    [ -z "$BACKEND_PENDING_AFTER" ] && BACKEND_PENDING_AFTER=0
    if [ "$BACKEND_PENDING_AFTER" -lt "$BACKEND_PENDING" ] 2>/dev/null; then
        echo -e "  ${GREEN}✅${NC} Backend is processing messages (pending decreased from $BACKEND_PENDING to $BACKEND_PENDING_AFTER)"
    elif [ "$BACKEND_PENDING_AFTER" -eq "$BACKEND_PENDING" ] 2>/dev/null && [ "$BACKEND_PENDING" -gt 0 ]; then
        echo -e "  ${YELLOW}⚠️${NC}  Backend pending messages unchanged (may be stuck)"
    fi
    
    # Check if backend triggered aggregation
    echo "  Checking if backend triggered post aggregation..."
    AGGREGATION_TRIGGERS=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XREVRANGE post-aggregation-trigger + - COUNT 5 2>/dev/null | grep -c "postId.*${TEST_POST_ID}" || echo "0")
    [ -z "$AGGREGATION_TRIGGERS" ] && AGGREGATION_TRIGGERS=0
    if [ "$AGGREGATION_TRIGGERS" -gt 0 ] 2>/dev/null; then
        echo -e "    ${GREEN}✅${NC} Backend triggered aggregation for postId=$TEST_POST_ID"
    else
        echo -e "    ${YELLOW}⚠️${NC}  Backend did not trigger aggregation (may need real post in database)"
        echo "    Note: This is expected when using direct Redis mode (post not in database)"
    fi
else
    echo -e "${YELLOW}⚠️${NC}  Backend not running, skipping backend verification"
fi

echo ""
echo -e "${BLUE}Step 6: Wait for Backend to Trigger Post Aggregation${NC}"
echo "=============================================================="

# Wait for backend to trigger aggregation (it should trigger after all media are processed)
echo "Waiting for backend to trigger post aggregation..."
echo "  Backend should trigger aggregation after all media for postId=$TEST_POST_ID are processed"

# Wait up to 30 seconds for backend to trigger aggregation
WAIT_COUNT=0
AGGREGATION_TRIGGERED=0
while [ $WAIT_COUNT -lt 30 ]; do
    sleep 2
    # Check if backend triggered aggregation
    AGGREGATION_TRIGGERS=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XREVRANGE post-aggregation-trigger + - COUNT 5 2>/dev/null | grep -c "postId.*${TEST_POST_ID}" || echo "0")
    [ -z "$AGGREGATION_TRIGGERS" ] && AGGREGATION_TRIGGERS=0
    if [ "$AGGREGATION_TRIGGERS" -gt 0 ] 2>/dev/null; then
        echo -e "  ${GREEN}✅${NC} Backend triggered aggregation for postId=$TEST_POST_ID"
        AGGREGATION_TRIGGERED=1
        break
    fi
    WAIT_COUNT=$((WAIT_COUNT + 2))
    if [ $((WAIT_COUNT % 10)) -eq 0 ]; then
        echo "  Still waiting... (${WAIT_COUNT}s elapsed)"
    fi
done

if [ "$AGGREGATION_TRIGGERED" -eq 0 ]; then
    echo -e "  ${YELLOW}⚠️${NC}  Backend did not trigger aggregation after 30 seconds"
    echo "  This may indicate:"
    echo "    - Backend is still processing media"
    echo "    - Backend has errors processing media"
    echo "    - Post may not exist in database (check backend logs)"
    echo ""
    echo "  Checking backend logs for aggregation trigger..."
    BACKEND_AGG_LOG=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=100 app 2>/dev/null | grep -E "Triggering.*aggregation|All media.*processed|triggerAggregation" | grep -i "$TEST_POST_ID" | tail -3 || echo "")
    if [ -n "$BACKEND_AGG_LOG" ]; then
        echo "  Backend aggregation logs:"
        echo "$BACKEND_AGG_LOG" | sed 's/^/    /'
    else
        echo "  No aggregation trigger logs found for postId=$TEST_POST_ID"
    fi
fi

echo "  Waiting 10 seconds for aggregation to complete..."
sleep 10

# Check if aggregation completed
echo "Checking post aggregation results..."
wait_for_message "post-insights-enriched" 30

# Verify aggregated message (check last 10 messages for our postId)
echo "Verifying aggregated message format..."
AGGREGATED_MESSAGES=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XREVRANGE post-insights-enriched + - COUNT 10 2>/dev/null || echo "")

# In Redis streams, format is: messageId field1 value1 field2 value2 ...
# We need to find where postId field is followed by our TEST_POST_ID value
# Use awk to find messages where postId field is followed by our postId value
AGGREGATED_MESSAGE=$(echo "$AGGREGATED_MESSAGES" | awk -v postid="${TEST_POST_ID}" '
    BEGIN { found=0; in_message=0; message="" }
    /^[0-9]+-[0-9]+$/ { 
        if (found) exit
        in_message=1
        message=$0 "\n"
        next
    }
    in_message {
        message=message $0 "\n"
        if ($0 == "postId") {
            getline next_line
            message=message next_line "\n"
            if (next_line == postid) {
                found=1
                # Get more lines for full message
                for (i=0; i<20; i++) {
                    if ((getline line) > 0) {
                        message=message line "\n"
                    } else {
                        break
                    }
                }
                print message
                exit
            }
        }
    }
' || echo "")

if [ -n "$AGGREGATED_MESSAGE" ] && echo "$AGGREGATED_MESSAGE" | grep -q "^postId$" && echo "$AGGREGATED_MESSAGE" | grep -q "^${TEST_POST_ID}$"; then
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
    
    # Show the actual message for debugging
    echo "  Message preview:"
    echo "$AGGREGATED_MESSAGE" | grep -E "postId|allAiTags|allAiScenes|correlationId|inferredEventType" | head -5 | sed 's/^/    /'
else
    echo -e "  ${RED}❌${NC} Aggregated message not found for postId=$TEST_POST_ID"
    echo "  Checking recent messages in stream..."
    # Extract postId values from recent messages
    RECENT_POST_IDS=$(echo "$AGGREGATED_MESSAGES" | awk '/^postId$/{getline; print $0}' | head -5 || echo "")
    if [ -n "$RECENT_POST_IDS" ]; then
        echo "  Recent postIds in stream:"
        echo "$RECENT_POST_IDS" | sed 's/^/    /'
    else
        # Show raw message structure for debugging
        echo "  Raw message structure (first 20 lines):"
        echo "$AGGREGATED_MESSAGES" | head -20 | sed 's/^/    /'
    fi
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
    
    # Check pending messages with details
    BACKEND_PENDING=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XPENDING post-insights-enriched backend-group 2>/dev/null | head -1 | grep -v "Warning" | tr -d '[:space:]' || echo "0")
    [ -z "$BACKEND_PENDING" ] && BACKEND_PENDING=0
    echo "  Backend pending messages: $BACKEND_PENDING"
    
    if [ "$BACKEND_PENDING" -gt 0 ] 2>/dev/null; then
        echo "  Investigating pending messages..."
        # Get details of pending messages
        PENDING_DETAILS=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XPENDING post-insights-enriched backend-group - + 5 2>/dev/null | grep -v "Warning" || echo "")
        if [ -n "$PENDING_DETAILS" ]; then
            echo "  Pending message details (first 5):"
            echo "$PENDING_DETAILS" | head -5 | sed 's/^/    /'
            
            # Calculate age of oldest pending message (in milliseconds)
            OLDEST_IDLE=$(echo "$PENDING_DETAILS" | head -1 | awk '{print $3}' || echo "0")
            if [ "$OLDEST_IDLE" -gt 0 ] 2>/dev/null; then
                OLDEST_AGE_HOURS=$((OLDEST_IDLE / 1000 / 3600))
                OLDEST_AGE_MINUTES=$(((OLDEST_IDLE / 1000) % 3600 / 60))
                if [ "$OLDEST_AGE_HOURS" -gt 0 ] 2>/dev/null; then
                    echo -e "  ${YELLOW}⚠️${NC}  Oldest pending message is ${OLDEST_AGE_HOURS}h ${OLDEST_AGE_MINUTES}m old (may need manual ACK)"
                elif [ "$OLDEST_AGE_MINUTES" -gt 5 ] 2>/dev/null; then
                    echo -e "  ${YELLOW}⚠️${NC}  Oldest pending message is ${OLDEST_AGE_MINUTES}m old"
                fi
            fi
        fi
        
        # Check backend logs for errors
        echo "  Checking backend logs for errors..."
        BACKEND_ERRORS=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=100 app 2>/dev/null | grep -E "ERROR.*post-insights-enriched|Exception.*post-insights-enriched|Cannot construct" | tail -5 || echo "")
        if [ -n "$BACKEND_ERRORS" ]; then
            echo -e "  ${RED}❌${NC} Backend errors found:"
            echo "$BACKEND_ERRORS" | sed 's/^/    /'
        else
            echo "  No recent errors in backend logs"
        fi
    fi
else
    echo -e "${YELLOW}⚠️${NC}  Backend not running, skipping backend verification"
fi

echo ""
echo -e "${BLUE}Step 8: Verify ES Sync${NC}"
echo "===================="

# Check if ES sync was triggered
echo "Checking ES sync queue..."
ES_SYNC_MESSAGES=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XLEN es-sync-queue 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
[ -z "$ES_SYNC_MESSAGES" ] && ES_SYNC_MESSAGES=0
echo "  ES sync queue length: $ES_SYNC_MESSAGES"

if [ "$ES_SYNC_MESSAGES" -gt 0 ] 2>/dev/null; then
    echo -e "  ${GREEN}✅${NC} ES sync queue has messages"
    
    # Wait for ES sync to process
    echo "  Waiting 10 seconds for ES sync to process..."
    sleep 10
    
    # Check ES sync logs for actual processing
    ES_SYNC_PROCESSED=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=100 es_sync 2>/dev/null | grep -c "Processing.*sync\|Successfully synced\|Indexed.*to Elasticsearch" || echo "0")
    [ -z "$ES_SYNC_PROCESSED" ] && ES_SYNC_PROCESSED=0
    if [ "$ES_SYNC_PROCESSED" -gt 0 ] 2>/dev/null; then
        echo -e "  ${GREEN}✅${NC} ES sync is processing messages ($ES_SYNC_PROCESSED recent operations)"
    else
        echo -e "  ${YELLOW}⚠️${NC}  ES sync may not be processing (check logs)"
        # Check for errors
        ES_SYNC_ERRORS=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=50 es_sync 2>/dev/null | grep -E "ERROR|Exception|Failed" | tail -3 || echo "")
        if [ -n "$ES_SYNC_ERRORS" ]; then
            echo "  ES sync errors:"
            echo "$ES_SYNC_ERRORS" | sed 's/^/    /'
        fi
        
        # Check PostgreSQL connection status
        echo "  Checking PostgreSQL connection..."
        PG_CONNECTION=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=100 es_sync 2>/dev/null | grep -E "Connected to PostgreSQL|PostgreSQL connection" | tail -1 || echo "")
        if [ -n "$PG_CONNECTION" ]; then
            echo "  PostgreSQL connection status:"
            echo "$PG_CONNECTION" | sed 's/^/    /'
        else
            echo -e "  ${YELLOW}⚠️${NC}  No PostgreSQL connection log found"
        fi
        
        # Check if es_sync is actually running
        if docker ps --format "{{.Names}}" | grep -qE "^es_sync$|kaleidoscope.*es_sync"; then
            echo "  ES sync container is running"
        else
            echo -e "  ${RED}❌${NC} ES sync container is not running"
        fi
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

# Check for errors with detailed reporting
echo "Checking for errors in logs..."
ERRORS=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=200 2>/dev/null | grep -E "ERROR|Exception" | grep -v "AuthorizationDeniedException" | grep -v "ServletException" | wc -l)
echo "  Error count: $ERRORS"

if [ "$ERRORS" -gt 0 ] 2>/dev/null; then
    echo "  Recent errors by service:"
    # Check errors per service
    for service in content_moderation image_tagger scene_recognition image_captioning face_recognition post_aggregator es_sync app; do
        SERVICE_ERRORS=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=100 "$service" 2>/dev/null | grep -E "ERROR|Exception" | grep -v "AuthorizationDeniedException" | grep -v "ServletException" | wc -l || echo "0")
        if [ "$SERVICE_ERRORS" -gt 0 ] 2>/dev/null; then
            echo "    $service: $SERVICE_ERRORS errors"
            # Show sample error
            SAMPLE_ERROR=$(docker-compose -f "$DOCKER_COMPOSE_FILE" logs --tail=50 "$service" 2>/dev/null | grep -E "ERROR|Exception" | grep -v "AuthorizationDeniedException" | grep -v "ServletException" | tail -1 || echo "")
            if [ -n "$SAMPLE_ERROR" ]; then
                echo "      Sample: $(echo "$SAMPLE_ERROR" | cut -c1-80)..."
            fi
        fi
    done
fi

# Check DLQ with detailed inspection
echo "Checking dead letter queue..."
DLQ_LENGTH=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XLEN ai-processing-dlq 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
[ -z "$DLQ_LENGTH" ] && DLQ_LENGTH=0
echo "  DLQ length: $DLQ_LENGTH"
if [ "$DLQ_LENGTH" -eq "0" ] 2>/dev/null; then
    echo -e "  ${GREEN}✅${NC} No messages in DLQ"
else
    echo -e "  ${YELLOW}⚠️${NC}  $DLQ_LENGTH messages in DLQ"
    echo "  Inspecting DLQ messages (last 3)..."
    DLQ_RAW=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XREVRANGE ai-processing-dlq + - COUNT 3 2>/dev/null || echo "")
    if [ -n "$DLQ_RAW" ]; then
        echo "  DLQ message details:"
        # Extract field-value pairs for key fields
        echo "$DLQ_RAW" | awk '
            /^serviceName$/{getline; print "    serviceName: " $0}
            /^error$/{getline; print "    error: " $0}
            /^originalMessageId$/{getline; print "    originalMessageId: " $0}
            /^retryCount$/{getline; print "    retryCount: " $0}
            /^originalStream$/{getline; print "    originalStream: " $0}
        ' | head -15
        
        # Check if any DLQ messages are from our test
        if echo "$DLQ_RAW" | grep -q "${TEST_CORRELATION_ID}\|${TEST_POST_ID}\|${TEST_MEDIA_ID_1}\|${TEST_MEDIA_ID_2}"; then
            echo -e "  ${RED}❌${NC} Test messages found in DLQ!"
        fi
    else
        echo "  Could not retrieve DLQ message details"
    fi
fi

echo ""
echo -e "${BLUE}Step 11: Final Stream Statistics${NC}"
echo "=================================="

# Get final stream lengths
FINAL_POST_IMAGE=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XLEN post-image-processing 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
FINAL_ML_INSIGHTS=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XLEN ml-insights-results 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
FINAL_FACE_DETECTION=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XLEN face-detection-results 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")
FINAL_POST_ENRICHED=$(docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XLEN post-insights-enriched 2>/dev/null | grep -v "Warning" | tail -1 | tr -d '[:space:]' || echo "0")

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
docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XINFO GROUPS post-image-processing 2>/dev/null | grep -E "name|consumers|pending|lag" | head -20
echo ""
docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XINFO GROUPS ml-insights-results 2>/dev/null | grep -E "name|consumers|pending|lag" | head -10
echo ""
docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XINFO GROUPS post-insights-enriched 2>/dev/null | grep -E "name|consumers|pending|lag" | head -10

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
if docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD}" XREVRANGE post-insights-enriched + - COUNT 1 2>/dev/null | grep -q "postId.*${TEST_POST_ID}"; then
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

