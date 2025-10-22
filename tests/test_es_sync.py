#!/usr/bin/env python3
"""
Test script for Elasticsearch Sync Service
Publishes test sync messages to Redis and verifies they're indexed in ES.
"""

import redis
import json
import time
import sys
import requests

# Configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6379
ES_HOST = "http://localhost:9200"
STREAM_NAME = "es-sync-queue"

def test_media_search_sync():
    """Test syncing a document to media_search index."""
    print("[TEST] Testing media_search index sync")
    print("-" * 60)
    
    # Connect to Redis
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    print("[OK] Connected to Redis")
    
    # Create test document
    test_doc = {
        "media_id": 12345,
        "post_id": 100,
        "post_title": "Test Post - Beach Vacation",
        "post_all_tags": ["vacation", "beach", "summer"],
        "media_url": "https://example.com/image.jpg",
        "ai_caption": "Beautiful sunset at the beach",
        "ai_tags": ["sunset", "beach", "ocean"],
        "ai_scenes": ["beach", "outdoor"],
        "image_embedding": [0.1] * 512,  # 512-dim vector
        "is_safe": True,
        "detected_users": [
            {"user_id": 1, "username": "alice"},
            {"user_id": 2, "username": "bob"}
        ],
        "uploader_id": 1,
        "uploader_username": "alice",
        "uploader_department": "Engineering",
        "reaction_count": 42,
        "comment_count": 10,
        "created_at": "2025-10-15T10:00:00Z",
        "updated_at": "2025-10-15T10:00:00Z"
    }
    
    # Publish to Redis Stream
    message = {
        "operation": "index",
        "indexType": "media_search",
        "documentId": "test_media_12345",
        "documentData": json.dumps(test_doc)
    }
    
    message_id = r.xadd(STREAM_NAME, message)
    print(f"[OK] Published sync message: {message_id}")
    print(f"     Operation: {message['operation']}")
    print(f"     Index: {message['indexType']}")
    print(f"     Document ID: {message['documentId']}")
    
    # Wait for processing
    print("[INFO] Waiting 3 seconds for processing...")
    time.sleep(3)
    
    # Verify in Elasticsearch
    doc_url = f"{ES_HOST}/media_search/_doc/test_media_12345"
    response = requests.get(doc_url)
    
    if response.status_code == 200:
        doc = response.json()
        print("[OK] Document found in Elasticsearch!")
        print(f"     Media ID: {doc['_source']['media_id']}")
        print(f"     Caption: {doc['_source']['ai_caption']}")
        print(f"     Tags: {doc['_source']['ai_tags']}")
        print(f"     Detected Users: {len(doc['_source']['detected_users'])}")
        print()
        return True
    else:
        print(f"[ERROR] Document not found (Status: {response.status_code})")
        print()
        return False


def test_post_search_sync():
    """Test syncing a document to post_search index."""
    print("[TEST] Testing post_search index sync")
    print("-" * 60)
    
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    
    test_doc = {
        "post_id": 200,
        "post_title": "Team Outing at the Park",
        "aggregated_tags": ["team", "outdoor", "picnic", "fun"],
        "combined_caption": "Team enjoying a picnic. Beautiful park scenery. Group photo with everyone.",
        "event_type": "team_outing",
        "media_count": 3,
        "total_faces": 8,
        "is_safe": True,
        "detected_users": [
            {"user_id": 1, "username": "alice"},
            {"user_id": 2, "username": "bob"},
            {"user_id": 3, "username": "charlie"}
        ],
        "uploader_id": 1,
        "uploader_username": "alice",
        "uploader_department": "Engineering",
        "reaction_count": 24,
        "comment_count": 5,
        "created_at": "2025-10-15T11:00:00Z",
        "updated_at": "2025-10-15T11:00:00Z"
    }
    
    message = {
        "operation": "index",
        "indexType": "post_search",
        "documentId": "test_post_200",
        "documentData": json.dumps(test_doc)
    }
    
    message_id = r.xadd(STREAM_NAME, message)
    print(f"[OK] Published sync message: {message_id}")
    
    print("[INFO] Waiting 3 seconds for processing...")
    time.sleep(3)
    
    doc_url = f"{ES_HOST}/post_search/_doc/test_post_200"
    response = requests.get(doc_url)
    
    if response.status_code == 200:
        doc = response.json()
        print("[OK] Document found in Elasticsearch!")
        print(f"     Post ID: {doc['_source']['post_id']}")
        print(f"     Title: {doc['_source']['post_title']}")
        print(f"     Event Type: {doc['_source']['event_type']}")
        print(f"     Total Faces: {doc['_source']['total_faces']}")
        print()
        return True
    else:
        print(f"[ERROR] Document not found (Status: {response.status_code})")
        print()
        return False


def test_user_search_sync():
    """Test syncing a document to user_search index."""
    print("[TEST] Testing user_search index sync")
    print("-" * 60)
    
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    
    test_doc = {
        "user_id": 1,
        "username": "alice",
        "full_name": "Alice Johnson",
        "bio": "Software engineer passionate about AI and photography",
        "department": "Engineering",
        "interests": ["AI", "Photography", "Travel", "Hiking"],
        "post_count": 42,
        "follower_count": 150,
        "following_count": 80,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2025-10-15T12:00:00Z"
    }
    
    message = {
        "operation": "index",
        "indexType": "user_search",
        "documentId": "test_user_1",
        "documentData": json.dumps(test_doc)
    }
    
    message_id = r.xadd(STREAM_NAME, message)
    print(f"[OK] Published sync message: {message_id}")
    
    print("[INFO] Waiting 3 seconds for processing...")
    time.sleep(3)
    
    doc_url = f"{ES_HOST}/user_search/_doc/test_user_1"
    response = requests.get(doc_url)
    
    if response.status_code == 200:
        doc = response.json()
        print("[OK] Document found in Elasticsearch!")
        print(f"     User ID: {doc['_source']['user_id']}")
        print(f"     Username: {doc['_source']['username']}")
        print(f"     Department: {doc['_source']['department']}")
        print(f"     Interests: {doc['_source']['interests']}")
        print()
        return True
    else:
        print(f"[ERROR] Document not found (Status: {response.status_code})")
        print()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Elasticsearch Sync Service - Integration Tests")
    print("=" * 60)
    print()
    
    results = {
        "media_search": test_media_search_sync(),
        "post_search": test_post_search_sync(),
        "user_search": test_user_search_sync()
    }
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    print(f"Total Tests: {total}")
    print(f"[OK] Passed: {passed}")
    print(f"[ERROR] Failed: {failed}")
    print()
    
    for test_name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {test_name}")
    
    print()
    
    if failed == 0:
        print("[SUCCESS] All Elasticsearch sync tests passed!")
        print()
        print("Next steps:")
        print("  1. Check all indices: curl http://localhost:9200/_cat/indices?v")
        print("  2. Search test data: curl http://localhost:9200/media_search/_search?q=beach")
        print("  3. View ES Sync logs: docker compose logs es_sync")
        sys.exit(0)
    else:
        print("[ERROR] Some tests failed. Check ES Sync logs:")
        print("  docker compose logs es_sync")
        sys.exit(1)


if __name__ == "__main__":
    main()

