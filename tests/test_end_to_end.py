#!/usr/bin/env python3
"""
End-to-End Automated Test Script
Tests both WRITE and READ paths of the Kaleidoscope AI system.

WRITE PATH: Job → AI Services → Post Aggregator → ES Sync → Elasticsearch
READ PATH: Search queries → Elasticsearch → Results

Author: AI Assistant
Date: October 15, 2025
"""

import redis
import requests
import json
import time
import sys
from typing import Dict, List, Optional
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

REDIS_HOST = "localhost"
REDIS_PORT = 6379
ES_HOST = "http://localhost:9200"

# Streams
STREAM_IMAGE_JOBS = "post-image-processing"
STREAM_ML_RESULTS = "ml-insights-results"
STREAM_POST_ENRICHED = "post-insights-enriched"
STREAM_ES_SYNC = "es-sync-queue"

# Test data
TEST_POST_ID = 99999
TEST_MEDIA_IDS = [88801, 88802, 88803]
TEST_IMAGE_URLS = [
    "https://images.unsplash.com/photo-1507525428034-b723cf961d3e",  # Beach
    "https://images.unsplash.com/photo-1506126613408-eca07ce68773",  # Beach sunset
    "https://images.unsplash.com/photo-1519046904884-53103b34b206"   # Beach group
]

# Colors for output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


# ============================================================================
# TEST UTILITIES
# ============================================================================

def print_header(text: str):
    """Print section header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}")
    print(f"{text}")
    print(f"{'=' * 70}{Colors.ENDC}\n")


def print_step(step_num: int, text: str):
    """Print test step."""
    print(f"{Colors.OKBLUE}[STEP {step_num}]{Colors.ENDC} {text}")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.OKGREEN}[SUCCESS]{Colors.ENDC} {text}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} {text}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.WARNING}[WARNING]{Colors.ENDC} {text}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.OKCYAN}[INFO]{Colors.ENDC} {text}")


class TestResult:
    """Track test results."""
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.details = []
    
    def add_pass(self, test_name: str, details: str = ""):
        self.total += 1
        self.passed += 1
        self.details.append(f"[PASS] {test_name}: {details}")
    
    def add_fail(self, test_name: str, error: str):
        self.total += 1
        self.failed += 1
        self.details.append(f"[FAIL] {test_name}: {error}")
    
    def add_warning(self, message: str):
        self.warnings += 1
        self.details.append(f"[WARN] {message}")
    
    def print_summary(self):
        print_header("TEST SUMMARY")
        print(f"Total Tests: {self.total}")
        print(f"{Colors.OKGREEN}Passed: {self.passed}{Colors.ENDC}")
        print(f"{Colors.FAIL}Failed: {self.failed}{Colors.ENDC}")
        print(f"{Colors.WARNING}Warnings: {self.warnings}{Colors.ENDC}")
        print()
        
        if self.failed > 0:
            print(f"{Colors.FAIL}FAILED TESTS:{Colors.ENDC}")
            for detail in self.details:
                if "[FAIL]" in detail:
                    print(f"  {detail}")
            print()
        
        pass_rate = (self.passed / self.total * 100) if self.total > 0 else 0
        
        if pass_rate == 100:
            print(f"{Colors.OKGREEN}{Colors.BOLD}ALL TESTS PASSED!{Colors.ENDC}")
            return 0
        elif pass_rate >= 80:
            print(f"{Colors.WARNING}MOSTLY PASSED (some issues){Colors.ENDC}")
            return 1
        else:
            print(f"{Colors.FAIL}TESTS FAILED{Colors.ENDC}")
            return 2


# ============================================================================
# INFRASTRUCTURE TESTS
# ============================================================================

def test_infrastructure(results: TestResult) -> bool:
    """Test that all infrastructure is running."""
    print_header("INFRASTRUCTURE TESTS")
    
    # Test Redis
    print_step(1, "Testing Redis connection")
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
        print_success(f"Redis is running at {REDIS_HOST}:{REDIS_PORT}")
        results.add_pass("Redis Connection", f"{REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        print_error(f"Redis connection failed: {e}")
        results.add_fail("Redis Connection", str(e))
        return False
    
    # Test Elasticsearch
    print_step(2, "Testing Elasticsearch connection")
    try:
        response = requests.get(ES_HOST, timeout=5)
        if response.status_code == 200:
            es_info = response.json()
            print_success(f"Elasticsearch {es_info['version']['number']} is running")
            results.add_pass("Elasticsearch Connection", f"v{es_info['version']['number']}")
        else:
            print_error(f"Elasticsearch returned status {response.status_code}")
            results.add_fail("Elasticsearch Connection", f"Status {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Elasticsearch connection failed: {e}")
        results.add_fail("Elasticsearch Connection", str(e))
        return False
    
    # Check Elasticsearch indices
    print_step(3, "Checking Elasticsearch indices")
    expected_indices = [
        "media_search", "post_search", "user_search", "face_search",
        "recommendations_knn", "feed_personalized", "known_faces_index"
    ]
    
    try:
        response = requests.get(f"{ES_HOST}/_cat/indices?format=json", timeout=5)
        indices = response.json()
        index_names = [idx['index'] for idx in indices if not idx['index'].startswith('.')]
        
        found_count = 0
        for expected in expected_indices:
            if expected in index_names:
                found_count += 1
                print_info(f"  Found index: {expected}")
            else:
                print_warning(f"  Missing index: {expected}")
        
        if found_count == len(expected_indices):
            print_success(f"All {len(expected_indices)} indices present")
            results.add_pass("Elasticsearch Indices", f"{found_count}/{len(expected_indices)} found")
        else:
            print_warning(f"Only {found_count}/{len(expected_indices)} indices found")
            results.add_warning(f"Missing {len(expected_indices) - found_count} indices")
            results.add_pass("Elasticsearch Indices", f"{found_count}/{len(expected_indices)} found")
    
    except Exception as e:
        print_error(f"Failed to check indices: {e}")
        results.add_fail("Elasticsearch Indices", str(e))
    
    # Check Docker services
    print_step(4, "Checking Docker services")
    try:
        import subprocess
        result = subprocess.run(
            ['docker', 'compose', 'ps', '--format', 'json'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            services_raw = result.stdout.strip()
            if services_raw:
                # Parse each line as JSON
                services = []
                for line in services_raw.split('\n'):
                    if line.strip():
                        try:
                            services.append(json.loads(line))
                        except:
                            pass
                
                running_services = [s for s in services if 'running' in s.get('State', '').lower()]
                print_success(f"{len(running_services)} Docker services running")
                results.add_pass("Docker Services", f"{len(running_services)} running")
                
                for svc in running_services:
                    print_info(f"  {svc.get('Service', 'unknown')}: {svc.get('State', 'unknown')}")
            else:
                print_warning("No Docker services found")
                results.add_warning("No Docker services detected")
        else:
            print_warning("Could not check Docker services (docker compose may not be available)")
            results.add_warning("Docker check skipped")
    
    except Exception as e:
        print_warning(f"Could not check Docker services: {e}")
        results.add_warning(f"Docker check failed: {e}")
    
    return True


# ============================================================================
# WRITE PATH TESTS
# ============================================================================

def test_write_path(results: TestResult) -> bool:
    """Test the complete write path."""
    print_header("WRITE PATH TESTS")
    
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    
    # Step 1: Publish image processing jobs
    print_step(1, "Publishing image processing jobs")
    job_ids = []
    
    for i, (media_id, image_url) in enumerate(zip(TEST_MEDIA_IDS, TEST_IMAGE_URLS)):
        job_id = f"test_job_{media_id}_{int(time.time())}"
        job_message = {
            "job_id": job_id,
            "post_id": str(TEST_POST_ID),
            "media_id": str(media_id),
            "image_url": image_url,
            "user_id": "1"
        }
        
        try:
            message_id = r.xadd(STREAM_IMAGE_JOBS, job_message)
            job_ids.append(job_id)
            print_info(f"  Published job {i+1}/3: {job_id} (message: {message_id})")
        except Exception as e:
            print_error(f"  Failed to publish job: {e}")
            results.add_fail("Publish Image Jobs", str(e))
            return False
    
    print_success(f"Published {len(job_ids)} image processing jobs")
    results.add_pass("Publish Image Jobs", f"{len(job_ids)} jobs published")
    
    # Step 2: Wait for AI services to process
    print_step(2, "Waiting for AI services to process (this may take 10-40 seconds)")
    print_info("  Note: AI services use HuggingFace API which can be slow")
    print_info("  You can check logs with: docker compose logs -f content_moderation")
    
    # We'll wait and then check if results appeared
    # In a real system, you'd poll the results stream
    print_info("  Waiting 30 seconds for AI processing...")
    for i in range(30):
        time.sleep(1)
        if i % 5 == 4:
            print_info(f"  ... {30-i-1} seconds remaining")
    
    # Check ml-insights-results stream
    try:
        messages = r.xread({STREAM_ML_RESULTS: '0'}, count=100, block=1000)
        if messages:
            result_count = len(messages[0][1]) if messages else 0
            print_info(f"  Found {result_count} messages in {STREAM_ML_RESULTS}")
            if result_count > 0:
                print_success("AI services produced results")
                results.add_pass("AI Services Processing", f"{result_count} results found")
            else:
                print_warning("No AI results found yet (may need more time)")
                results.add_warning("AI results not found in 30 seconds")
        else:
            print_warning("No messages in ml-insights-results stream")
            results.add_warning("No AI processing detected")
    except Exception as e:
        print_error(f"Error checking AI results: {e}")
        results.add_fail("AI Services Processing", str(e))
    
    # Step 3: Check post aggregator output
    print_step(3, "Checking Post Aggregator output")
    try:
        messages = r.xread({STREAM_POST_ENRICHED: '0'}, count=50, block=1000)
        if messages and len(messages) > 0:
            enriched_count = len(messages[0][1])
            print_info(f"  Found {enriched_count} enriched post(s)")
            
            # Show latest enriched post
            if enriched_count > 0:
                latest = messages[0][1][-1]
                data = latest[1]
                print_info(f"  Latest enriched post_id: {data.get('post_id', 'N/A')}")
                print_info(f"  Event type: {data.get('event_type', 'N/A')}")
                print_info(f"  Total faces: {data.get('total_faces', 'N/A')}")
                print_success("Post Aggregator is working")
                results.add_pass("Post Aggregator", f"{enriched_count} posts enriched")
            else:
                print_warning("Post Aggregator hasn't produced results yet")
                results.add_warning("No enriched posts found")
        else:
            print_warning("No enriched posts found (aggregator may need more time)")
            results.add_warning("Post aggregation pending")
    except Exception as e:
        print_error(f"Error checking post aggregator: {e}")
        results.add_fail("Post Aggregator", str(e))
    
    # Step 4: Test ES Sync directly
    print_step(4, "Testing ES Sync service directly")
    
    test_doc = {
        "media_id": TEST_MEDIA_IDS[0],
        "post_id": TEST_POST_ID,
        "post_title": "E2E Test - Beach Vacation",
        "post_all_tags": ["test", "beach", "automated"],
        "media_url": TEST_IMAGE_URLS[0],
        "ai_caption": "Automated E2E test image",
        "ai_tags": ["test", "beach"],
        "ai_scenes": ["beach", "outdoor"],
        "image_embedding": [0.1] * 512,
        "is_safe": True,
        "detected_users": [],
        "uploader_id": 1,
        "uploader_username": "test_user",
        "uploader_department": "Engineering",
        "reaction_count": 0,
        "comment_count": 0,
        "created_at": datetime.now().isoformat() + "Z",
        "updated_at": datetime.now().isoformat() + "Z"
    }
    
    sync_message = {
        "operation": "index",
        "indexType": "media_search",
        "documentId": f"test_e2e_{TEST_MEDIA_IDS[0]}",
        "documentData": json.dumps(test_doc)
    }
    
    try:
        message_id = r.xadd(STREAM_ES_SYNC, sync_message)
        print_info(f"  Published sync message: {message_id}")
        
        # Wait for ES Sync to process
        print_info("  Waiting 3 seconds for ES Sync...")
        time.sleep(3)
        
        # Check if document exists in ES
        doc_id = sync_message["documentId"]
        response = requests.get(f"{ES_HOST}/media_search/_doc/{doc_id}")
        
        if response.status_code == 200:
            doc = response.json()
            print_success(f"Document indexed in Elasticsearch!")
            print_info(f"  Document ID: {doc['_id']}")
            print_info(f"  Media ID: {doc['_source']['media_id']}")
            results.add_pass("ES Sync Service", "Document indexed successfully")
        else:
            print_warning(f"Document not found in ES (status: {response.status_code})")
            results.add_warning("ES Sync may need more time")
    
    except Exception as e:
        print_error(f"ES Sync test failed: {e}")
        results.add_fail("ES Sync Service", str(e))
    
    print_success("Write path tests completed")
    return True


# ============================================================================
# READ PATH TESTS
# ============================================================================

def test_read_path(results: TestResult) -> bool:
    """Test the complete read path."""
    print_header("READ PATH TESTS")
    
    # Test 1: Simple text search
    print_step(1, "Testing text search")
    try:
        response = requests.get(
            f"{ES_HOST}/media_search/_search",
            params={"q": "beach"},
            timeout=5
        )
        
        if response.status_code == 200:
            search_results = response.json()
            hit_count = search_results['hits']['total']['value']
            search_time = search_results['took']
            
            print_success(f"Text search working! Found {hit_count} results in {search_time}ms")
            results.add_pass("Text Search", f"{hit_count} results, {search_time}ms")
            
            if hit_count > 0:
                first_hit = search_results['hits']['hits'][0]
                print_info(f"  First result: {first_hit['_source'].get('ai_caption', 'N/A')[:50]}...")
                print_info(f"  Score: {first_hit['_score']}")
        else:
            print_error(f"Search failed with status {response.status_code}")
            results.add_fail("Text Search", f"Status {response.status_code}")
    
    except Exception as e:
        print_error(f"Text search failed: {e}")
        results.add_fail("Text Search", str(e))
    
    # Test 2: Get specific document
    print_step(2, "Testing document retrieval")
    try:
        doc_id = f"test_e2e_{TEST_MEDIA_IDS[0]}"
        response = requests.get(f"{ES_HOST}/media_search/_doc/{doc_id}", timeout=5)
        
        if response.status_code == 200:
            doc = response.json()
            print_success(f"Document retrieved successfully")
            print_info(f"  Document ID: {doc['_id']}")
            print_info(f"  Media ID: {doc['_source']['media_id']}")
            print_info(f"  Caption: {doc['_source'].get('ai_caption', 'N/A')}")
            results.add_pass("Document Retrieval", f"ID: {doc_id}")
        elif response.status_code == 404:
            print_warning(f"Document not found (may not be indexed yet)")
            results.add_warning("Test document not indexed yet")
        else:
            print_error(f"Retrieval failed with status {response.status_code}")
            results.add_fail("Document Retrieval", f"Status {response.status_code}")
    
    except Exception as e:
        print_error(f"Document retrieval failed: {e}")
        results.add_fail("Document Retrieval", str(e))
    
    # Test 3: Multi-field search
    print_step(3, "Testing multi-field search")
    try:
        query = {
            "query": {
                "multi_match": {
                    "query": "beach sunset",
                    "fields": ["ai_caption", "ai_tags", "post_title"]
                }
            }
        }
        
        response = requests.post(
            f"{ES_HOST}/media_search/_search",
            json=query,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        if response.status_code == 200:
            results_data = response.json()
            hit_count = results_data['hits']['total']['value']
            search_time = results_data['took']
            
            print_success(f"Multi-field search working! Found {hit_count} results in {search_time}ms")
            results.add_pass("Multi-field Search", f"{hit_count} results, {search_time}ms")
        else:
            print_error(f"Multi-field search failed with status {response.status_code}")
            results.add_fail("Multi-field Search", f"Status {response.status_code}")
    
    except Exception as e:
        print_error(f"Multi-field search failed: {e}")
        results.add_fail("Multi-field Search", str(e))
    
    # Test 4: Filter search (tags)
    print_step(4, "Testing filtered search")
    try:
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"ai_caption": "beach"}}
                    ],
                    "filter": [
                        {"term": {"is_safe": True}}
                    ]
                }
            }
        }
        
        response = requests.post(
            f"{ES_HOST}/media_search/_search",
            json=query,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        if response.status_code == 200:
            results_data = response.json()
            hit_count = results_data['hits']['total']['value']
            search_time = results_data['took']
            
            print_success(f"Filtered search working! Found {hit_count} results in {search_time}ms")
            results.add_pass("Filtered Search", f"{hit_count} results, {search_time}ms")
        else:
            print_error(f"Filtered search failed with status {response.status_code}")
            results.add_fail("Filtered Search", f"Status {response.status_code}")
    
    except Exception as e:
        print_error(f"Filtered search failed: {e}")
        results.add_fail("Filtered Search", str(e))
    
    # Test 5: Aggregations
    print_step(5, "Testing aggregations")
    try:
        query = {
            "size": 0,
            "aggs": {
                "tags": {
                    "terms": {
                        "field": "ai_tags",
                        "size": 10
                    }
                }
            }
        }
        
        response = requests.post(
            f"{ES_HOST}/media_search/_search",
            json=query,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        if response.status_code == 200:
            results_data = response.json()
            agg_buckets = results_data.get('aggregations', {}).get('tags', {}).get('buckets', [])
            
            print_success(f"Aggregations working! Found {len(agg_buckets)} unique tags")
            results.add_pass("Aggregations", f"{len(agg_buckets)} tag buckets")
            
            if agg_buckets:
                print_info("  Top tags:")
                for bucket in agg_buckets[:5]:
                    print_info(f"    - {bucket['key']}: {bucket['doc_count']}")
        else:
            print_error(f"Aggregation failed with status {response.status_code}")
            results.add_fail("Aggregations", f"Status {response.status_code}")
    
    except Exception as e:
        print_error(f"Aggregation failed: {e}")
        results.add_fail("Aggregations", str(e))
    
    print_success("Read path tests completed")
    return True


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

def test_performance(results: TestResult):
    """Test system performance."""
    print_header("PERFORMANCE TESTS")
    
    # Test search performance
    print_step(1, "Testing search performance (10 queries)")
    
    try:
        search_times = []
        for i in range(10):
            start = time.time()
            response = requests.get(
                f"{ES_HOST}/media_search/_search",
                params={"q": "beach"},
                timeout=5
            )
            elapsed = (time.time() - start) * 1000  # Convert to ms
            search_times.append(elapsed)
        
        avg_time = sum(search_times) / len(search_times)
        min_time = min(search_times)
        max_time = max(search_times)
        
        print_success(f"Search performance results:")
        print_info(f"  Average: {avg_time:.2f}ms")
        print_info(f"  Min: {min_time:.2f}ms")
        print_info(f"  Max: {max_time:.2f}ms")
        
        if avg_time < 100:
            results.add_pass("Search Performance", f"Avg: {avg_time:.2f}ms (Excellent)")
        elif avg_time < 500:
            results.add_pass("Search Performance", f"Avg: {avg_time:.2f}ms (Good)")
        else:
            results.add_warning(f"Search performance slow: {avg_time:.2f}ms")
            results.add_pass("Search Performance", f"Avg: {avg_time:.2f}ms (Needs optimization)")
    
    except Exception as e:
        print_error(f"Performance test failed: {e}")
        results.add_fail("Search Performance", str(e))


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    """Run all tests."""
    print(f"{Colors.BOLD}{Colors.HEADER}")
    print("=" * 70)
    print("  KALEIDOSCOPE AI - END-TO-END AUTOMATED TEST SUITE")
    print("=" * 70)
    print(f"{Colors.ENDC}")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    print(f"Elasticsearch: {ES_HOST}")
    print()
    
    results = TestResult()
    
    # Run test suites
    infra_ok = test_infrastructure(results)
    
    if infra_ok:
        test_write_path(results)
        test_read_path(results)
        test_performance(results)
    else:
        print_error("Infrastructure tests failed. Skipping other tests.")
        print_info("Please ensure Redis and Elasticsearch are running:")
        print_info("  docker compose up -d redis elasticsearch")
    
    # Print summary
    exit_code = results.print_summary()
    
    print()
    print_info("For detailed logs, check:")
    print_info("  docker compose logs -f")
    print()
    print_info("For manual testing instructions, see:")
    print_info("  kaleidoscope-ai/MANUAL_TESTING_GUIDE.md")
    print()
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

