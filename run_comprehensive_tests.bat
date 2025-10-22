@echo off
REM Kaleidoscope AI - Comprehensive Testing Script (Windows)
REM This script runs all API tests using curl commands

setlocal enabledelayedexpansion

REM Configuration
set ES_HOST=http://localhost:9200
set DOCKER_HOST=http://localhost:2375
set TEST_INDEX=media_search
set TEST_DOC_ID=test_doc_1

REM Counters
set TOTAL_TESTS=0
set PASSED_TESTS=0
set FAILED_TESTS=0

echo.
echo ==================================================
echo Kaleidoscope AI - Comprehensive Testing Script
echo ==================================================
echo.

REM Function to run a test
:run_test
set test_name=%~1
set curl_command=%~2
set /a TOTAL_TESTS+=1

echo [INFO] Running: %test_name%

REM Execute the curl command
%curl_command% >nul 2>&1
if %errorlevel% equ 0 (
    echo [SUCCESS] %test_name% - PASSED
    set /a PASSED_TESTS+=1
) else (
    echo [ERROR] %test_name% - FAILED ^(Exit code: %errorlevel%^)
    set /a FAILED_TESTS+=1
)
goto :eof

REM Check if Docker is running
:check_docker
echo [INFO] Checking Docker status...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running. Please start Docker Desktop.
    exit /b 1
)
echo [SUCCESS] Docker is running
goto :eof

REM Start services
:start_services
echo [INFO] Starting Kaleidoscope AI services...

if not exist "docker-compose.yml" (
    echo [ERROR] docker-compose.yml not found. Please run this script from the kaleidoscope-ai directory.
    exit /b 1
)

docker compose up -d
echo [SUCCESS] Services started
goto :eof

REM Wait for service
:wait_for_service
set service_name=%~1
set service_url=%~2
set max_attempts=30
set attempt=1

echo [INFO] Waiting for %service_name% to be ready...

:wait_loop
curl -s "%service_url%" >nul 2>&1
if %errorlevel% equ 0 (
    echo [SUCCESS] %service_name% is ready!
    goto :eof
)

echo [INFO] Attempt %attempt%/%max_attempts% - %service_name% not ready yet...
timeout /t 2 /nobreak >nul
set /a attempt+=1
if %attempt% leq %max_attempts% goto wait_loop

echo [ERROR] %service_name% failed to start within %max_attempts% attempts
exit /b 1

REM Create indices
:create_indices
echo [INFO] Creating Elasticsearch indices...

if exist "scripts\setup_es_indices.py" (
    python scripts\setup_es_indices.py
    echo [SUCCESS] Elasticsearch indices created
) else (
    echo [WARNING] setup_es_indices.py not found, skipping index creation
)
goto :eof

REM Run all tests
:run_all_tests
echo [INFO] Starting comprehensive API tests...
echo ==================================================

REM Phase 1: Infrastructure Tests
echo [INFO] Phase 1: Infrastructure Health Checks
echo --------------------------------------------------

call :run_test "Elasticsearch Health Check" "curl -s -X GET \"%ES_HOST%\" -H \"Content-Type: application/json\""
call :run_test "Docker Services Status" "curl -s -X GET \"%DOCKER_HOST%/containers/json\" -H \"Content-Type: application/json\""
call :run_test "Redis Health Check" "docker exec -it kaleidoscope-ai-redis-1 redis-cli ping"

REM Phase 2: Elasticsearch Management
echo [INFO] Phase 2: Elasticsearch Management
echo --------------------------------------------------

call :run_test "List All Indices" "curl -s -X GET \"%ES_HOST%/_cat/indices?v\" -H \"Content-Type: application/json\""
call :run_test "Get Index Mapping" "curl -s -X GET \"%ES_HOST%/%TEST_INDEX%/_mapping\" -H \"Content-Type: application/json\""
call :run_test "Cluster Health" "curl -s -X GET \"%ES_HOST%/_cluster/health\" -H \"Content-Type: application/json\""

REM Phase 3: Document Operations
echo [INFO] Phase 3: Document Operations
echo --------------------------------------------------

call :run_test "Index Document" "curl -s -X POST \"%ES_HOST%/%TEST_INDEX%/_doc/%TEST_DOC_ID%\" -H \"Content-Type: application/json\" -d \"{\"media_id\": 12345, \"post_id\": 100, \"ai_caption\": \"Test document\", \"ai_tags\": [\"test\"], \"is_safe\": true}\""
call :run_test "Get Document by ID" "curl -s -X GET \"%ES_HOST%/%TEST_INDEX%/_doc/%TEST_DOC_ID%\" -H \"Content-Type: application/json\""
call :run_test "Update Document" "curl -s -X POST \"%ES_HOST%/%TEST_INDEX%/_update/%TEST_DOC_ID%\" -H \"Content-Type: application/json\" -d \"{\"doc\": {\"reaction_count\": 50}}\""

REM Phase 4: Search Operations
echo [INFO] Phase 4: Search Operations
echo --------------------------------------------------

call :run_test "Simple Text Search" "curl -s -X GET \"%ES_HOST%/%TEST_INDEX%/_search?q=test\" -H \"Content-Type: application/json\""
call :run_test "Multi-Field Search" "curl -s -X POST \"%ES_HOST%/%TEST_INDEX%/_search\" -H \"Content-Type: application/json\" -d \"{\"query\": {\"multi_match\": {\"query\": \"test\", \"fields\": [\"ai_caption\", \"ai_tags\"]}}}\""
call :run_test "Filtered Search" "curl -s -X POST \"%ES_HOST%/%TEST_INDEX%/_search\" -H \"Content-Type: application/json\" -d \"{\"query\": {\"bool\": {\"must\": [{\"match\": {\"ai_caption\": \"test\"}}], \"filter\": [{\"term\": {\"is_safe\": true}}]}}}\""

REM Phase 5: Redis Streams
echo [INFO] Phase 5: Redis Streams
echo --------------------------------------------------

call :run_test "Check Stream Information" "docker exec -it kaleidoscope-ai-redis-1 redis-cli XINFO STREAM post-image-processing"
call :run_test "List All Streams" "docker exec -it kaleidoscope-ai-redis-1 redis-cli KEYS \"*\""
call :run_test "Add Message to Stream" "docker exec -it kaleidoscope-ai-redis-1 redis-cli XADD post-image-processing \"*\" job_id \"test_job_123\" post_id \"100\""

REM Phase 6: Service Health
echo [INFO] Phase 6: Service Health
echo --------------------------------------------------

call :run_test "Check Service Logs" "curl -s -X GET \"%DOCKER_HOST%/containers/kaleidoscope-ai-content_moderation-1/logs?stdout=true&stderr=true&tail=5\""
call :run_test "Check Service Stats" "curl -s -X GET \"%DOCKER_HOST%/containers/kaleidoscope-ai-content_moderation-1/stats\""

REM Phase 7: Advanced Operations
echo [INFO] Phase 7: Advanced Operations
echo --------------------------------------------------

call :run_test "Bulk Index Operations" "curl -s -X POST \"%ES_HOST%/_bulk\" -H \"Content-Type: application/x-ndjson\" --data-binary \"{\"index\":{\"_index\":\"%TEST_INDEX%\",\"_id\":\"bulk_doc_1\"}}\n{\"media_id\":11111,\"ai_caption\":\"Bulk test document\",\"ai_tags\":[\"test\",\"bulk\"]}\n\""
call :run_test "Multi-Index Search" "curl -s -X POST \"%ES_HOST%/media_search,post_search/_search\" -H \"Content-Type: application/json\" -d \"{\"query\": {\"match_all\": {}}, \"size\": 10}\""

REM Phase 8: Cleanup
echo [INFO] Phase 8: Cleanup
echo --------------------------------------------------

call :run_test "Delete Test Document" "curl -s -X DELETE \"%ES_HOST%/%TEST_INDEX%/_doc/%TEST_DOC_ID%\" -H \"Content-Type: application/json\""
call :run_test "Delete Bulk Document" "curl -s -X DELETE \"%ES_HOST%/%TEST_INDEX%/_doc/bulk_doc_1\" -H \"Content-Type: application/json\""

goto :eof

REM Print test summary
:print_summary
echo ==================================================
echo [INFO] Test Summary
echo ==================================================
echo Total Tests: %TOTAL_TESTS%
echo Passed: %PASSED_TESTS%
echo Failed: %FAILED_TESTS%

if %FAILED_TESTS% equ 0 (
    echo [SUCCESS] All tests passed! 🎉
    exit /b 0
) else (
    echo [ERROR] Some tests failed. Please check the output above.
    exit /b 1
)
goto :eof

REM Main execution
:main
call :check_docker
call :start_services
call :wait_for_service "Elasticsearch" "%ES_HOST%"
call :wait_for_service "Redis" "redis://localhost:6379"
call :create_indices
call :run_all_tests
call :print_summary
goto :eof

REM Handle script arguments
if "%1"=="start" (
    call :start_services
    goto :eof
)
if "%1"=="test" (
    call :run_all_tests
    call :print_summary
    goto :eof
)
if "%1"=="cleanup" (
    echo [INFO] Cleaning up test data...
    curl -s -X DELETE "%ES_HOST%/%TEST_INDEX%/_doc/%TEST_DOC_ID%" -H "Content-Type: application/json" >nul 2>&1
    curl -s -X DELETE "%ES_HOST%/%TEST_INDEX%/_doc/bulk_doc_1%" -H "Content-Type: application/json" >nul 2>&1
    echo [SUCCESS] Cleanup completed
    goto :eof
)
if "%1"=="stop" (
    echo [INFO] Stopping services...
    docker compose down
    echo [SUCCESS] Services stopped
    goto :eof
)

REM Default: run main function
call :main
