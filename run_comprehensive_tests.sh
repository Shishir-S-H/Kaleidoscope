#!/bin/bash

# Kaleidoscope AI - Comprehensive Testing Script
# This script runs all API tests using curl commands

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ES_HOST="http://localhost:9200"
DOCKER_HOST="http://localhost:2375"
TEST_INDEX="media_search"
TEST_DOC_ID="test_doc_1"

# Counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "INFO")
            echo -e "${BLUE}[INFO]${NC} $message"
            ;;
        "SUCCESS")
            echo -e "${GREEN}[SUCCESS]${NC} $message"
            ;;
        "ERROR")
            echo -e "${RED}[ERROR]${NC} $message"
            ;;
        "WARNING")
            echo -e "${YELLOW}[WARNING]${NC} $message"
            ;;
    esac
}

# Function to run a test
run_test() {
    local test_name=$1
    local curl_command=$2
    local expected_status=$3
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    print_status "INFO" "Running: $test_name"
    
    # Execute the curl command and capture response
    local response
    local http_status
    
    if [[ $curl_command == *"docker exec"* ]]; then
        # Handle Docker commands
        response=$(eval "$curl_command" 2>/dev/null)
        http_status=$?
    else
        # Handle curl commands
        response=$(eval "$curl_command" 2>/dev/null)
        http_status=$?
    fi
    
    # Check if command succeeded
    if [ $http_status -eq 0 ]; then
        print_status "SUCCESS" "$test_name - PASSED"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        print_status "ERROR" "$test_name - FAILED (Exit code: $http_status)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Function to wait for service
wait_for_service() {
    local service_name=$1
    local service_url=$2
    local max_attempts=30
    local attempt=1
    
    print_status "INFO" "Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$service_url" > /dev/null 2>&1; then
            print_status "SUCCESS" "$service_name is ready!"
            return 0
        fi
        
        print_status "INFO" "Attempt $attempt/$max_attempts - $service_name not ready yet..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_status "ERROR" "$service_name failed to start within $max_attempts attempts"
    return 1
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_status "ERROR" "Docker is not running. Please start Docker Desktop."
        exit 1
    fi
    print_status "SUCCESS" "Docker is running"
}

# Function to start services
start_services() {
    print_status "INFO" "Starting Kaleidoscope AI services..."
    
    if [ ! -f "docker-compose.yml" ]; then
        print_status "ERROR" "docker-compose.yml not found. Please run this script from the kaleidoscope-ai directory."
        exit 1
    fi
    
    docker compose up -d
    print_status "SUCCESS" "Services started"
}

# Function to create Elasticsearch indices
create_indices() {
    print_status "INFO" "Creating Elasticsearch indices..."
    
    if [ -f "scripts/setup_es_indices.py" ]; then
        python scripts/setup_es_indices.py
        print_status "SUCCESS" "Elasticsearch indices created"
    else
        print_status "WARNING" "setup_es_indices.py not found, skipping index creation"
    fi
}

# Main testing function
run_all_tests() {
    print_status "INFO" "Starting comprehensive API tests..."
    echo "=================================================="
    
    # Infrastructure Tests
    print_status "INFO" "Phase 1: Infrastructure Health Checks"
    echo "--------------------------------------------------"
    
    run_test "Elasticsearch Health Check" \
        "curl -s -X GET '$ES_HOST' -H 'Content-Type: application/json'"
    
    run_test "Docker Services Status" \
        "curl -s -X GET '$DOCKER_HOST/containers/json' -H 'Content-Type: application/json'"
    
    run_test "Redis Health Check" \
        "docker exec -it kaleidoscope-ai-redis-1 redis-cli ping"
    
    # Elasticsearch Management Tests
    print_status "INFO" "Phase 2: Elasticsearch Management"
    echo "--------------------------------------------------"
    
    run_test "List All Indices" \
        "curl -s -X GET '$ES_HOST/_cat/indices?v' -H 'Content-Type: application/json'"
    
    run_test "Get Index Mapping" \
        "curl -s -X GET '$ES_HOST/$TEST_INDEX/_mapping' -H 'Content-Type: application/json'"
    
    run_test "Cluster Health" \
        "curl -s -X GET '$ES_HOST/_cluster/health' -H 'Content-Type: application/json'"
    
    # Document Operations Tests
    print_status "INFO" "Phase 3: Document Operations"
    echo "--------------------------------------------------"
    
    run_test "Index Document" \
        "curl -s -X POST '$ES_HOST/$TEST_INDEX/_doc/$TEST_DOC_ID' -H 'Content-Type: application/json' -d '{\"media_id\": 12345, \"post_id\": 100, \"ai_caption\": \"Test document\", \"ai_tags\": [\"test\"], \"is_safe\": true}'"
    
    run_test "Get Document by ID" \
        "curl -s -X GET '$ES_HOST/$TEST_INDEX/_doc/$TEST_DOC_ID' -H 'Content-Type: application/json'"
    
    run_test "Update Document" \
        "curl -s -X POST '$ES_HOST/$TEST_INDEX/_update/$TEST_DOC_ID' -H 'Content-Type: application/json' -d '{\"doc\": {\"reaction_count\": 50}}'"
    
    # Search Operations Tests
    print_status "INFO" "Phase 4: Search Operations"
    echo "--------------------------------------------------"
    
    run_test "Simple Text Search" \
        "curl -s -X GET '$ES_HOST/$TEST_INDEX/_search?q=test' -H 'Content-Type: application/json'"
    
    run_test "Multi-Field Search" \
        "curl -s -X POST '$ES_HOST/$TEST_INDEX/_search' -H 'Content-Type: application/json' -d '{\"query\": {\"multi_match\": {\"query\": \"test\", \"fields\": [\"ai_caption\", \"ai_tags\"]}}}'"
    
    run_test "Filtered Search" \
        "curl -s -X POST '$ES_HOST/$TEST_INDEX/_search' -H 'Content-Type: application/json' -d '{\"query\": {\"bool\": {\"must\": [{\"match\": {\"ai_caption\": \"test\"}}], \"filter\": [{\"term\": {\"is_safe\": true}}]}}}'"
    
    # Redis Streams Tests
    print_status "INFO" "Phase 5: Redis Streams"
    echo "--------------------------------------------------"
    
    run_test "Check Stream Information" \
        "docker exec -it kaleidoscope-ai-redis-1 redis-cli XINFO STREAM post-image-processing"
    
    run_test "List All Streams" \
        "docker exec -it kaleidoscope-ai-redis-1 redis-cli KEYS '*'"
    
    run_test "Add Message to Stream" \
        "docker exec -it kaleidoscope-ai-redis-1 redis-cli XADD post-image-processing '*' job_id 'test_job_123' post_id '100'"
    
    # Service Health Tests
    print_status "INFO" "Phase 6: Service Health"
    echo "--------------------------------------------------"
    
    run_test "Check Service Logs" \
        "curl -s -X GET '$DOCKER_HOST/containers/kaleidoscope-ai-content_moderation-1/logs?stdout=true&stderr=true&tail=5'"
    
    run_test "Check Service Stats" \
        "curl -s -X GET '$DOCKER_HOST/containers/kaleidoscope-ai-content_moderation-1/stats'"
    
    # Advanced Operations Tests
    print_status "INFO" "Phase 7: Advanced Operations"
    echo "--------------------------------------------------"
    
    run_test "Bulk Index Operations" \
        "curl -s -X POST '$ES_HOST/_bulk' -H 'Content-Type: application/x-ndjson' --data-binary '{\"index\":{\"_index\":\"$TEST_INDEX\",\"_id\":\"bulk_doc_1\"}}\n{\"media_id\":11111,\"ai_caption\":\"Bulk test document\",\"ai_tags\":[\"test\",\"bulk\"]}\n'"
    
    run_test "Multi-Index Search" \
        "curl -s -X POST '$ES_HOST/media_search,post_search/_search' -H 'Content-Type: application/json' -d '{\"query\": {\"match_all\": {}}, \"size\": 10}'"
    
    # Cleanup
    print_status "INFO" "Phase 8: Cleanup"
    echo "--------------------------------------------------"
    
    run_test "Delete Test Document" \
        "curl -s -X DELETE '$ES_HOST/$TEST_INDEX/_doc/$TEST_DOC_ID' -H 'Content-Type: application/json'"
    
    run_test "Delete Bulk Document" \
        "curl -s -X DELETE '$ES_HOST/$TEST_INDEX/_doc/bulk_doc_1' -H 'Content-Type: application/json'"
}

# Function to print test summary
print_summary() {
    echo "=================================================="
    print_status "INFO" "Test Summary"
    echo "=================================================="
    echo "Total Tests: $TOTAL_TESTS"
    echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
    echo -e "Failed: ${RED}$FAILED_TESTS${NC}"
    
    if [ $FAILED_TESTS -eq 0 ]; then
        print_status "SUCCESS" "All tests passed! 🎉"
        exit 0
    else
        print_status "ERROR" "Some tests failed. Please check the output above."
        exit 1
    fi
}

# Main execution
main() {
    echo "🚀 Kaleidoscope AI - Comprehensive Testing Script"
    echo "=================================================="
    
    # Check prerequisites
    check_docker
    
    # Start services
    start_services
    
    # Wait for services to be ready
    wait_for_service "Elasticsearch" "$ES_HOST"
    wait_for_service "Redis" "redis://localhost:6379"
    
    # Create indices
    create_indices
    
    # Run all tests
    run_all_tests
    
    # Print summary
    print_summary
}

# Handle script arguments
case "${1:-}" in
    "start")
        start_services
        ;;
    "test")
        run_all_tests
        print_summary
        ;;
    "cleanup")
        print_status "INFO" "Cleaning up test data..."
        curl -s -X DELETE "$ES_HOST/$TEST_INDEX/_doc/$TEST_DOC_ID" -H "Content-Type: application/json" || true
        curl -s -X DELETE "$ES_HOST/$TEST_INDEX/_doc/bulk_doc_1" -H "Content-Type: application/json" || true
        print_status "SUCCESS" "Cleanup completed"
        ;;
    "stop")
        print_status "INFO" "Stopping services..."
        docker compose down
        print_status "SUCCESS" "Services stopped"
        ;;
    *)
        main
        ;;
esac
