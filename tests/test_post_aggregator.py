#!/usr/bin/env python3
"""
Test script for Post Aggregator Service.
Simulates a post with multiple images and tests aggregation.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import redis

# Configuration
REDIS_URL = "redis://localhost:6379"
AGGREGATION_TRIGGER_STREAM = "post-aggregation-trigger"
AGGREGATION_OUTPUT_STREAM = "post-insights-enriched"

def connect_redis():
    """Connect to Redis."""
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        print("[OK] Connected to Redis successfully!")
        return client
    except Exception as e:
        print(f"[ERROR] Failed to connect to Redis: {e}")
        sys.exit(1)

def publish_test_aggregation(client):
    """Publish a test aggregation trigger message."""
    
    # Simulate insights from 3 images of a beach party
    media_insights = [
        {
            "mediaId": "1",
            "postId": "100",
            "tags": json.dumps(["beach", "people", "outdoor", "water"]),
            "scenes": json.dumps(["beach", "outdoor"]),
            "caption": "People enjoying at the beach",
            "facesDetected": "3",
            "isSafe": "true",
            "moderationConfidence": "0.95"
        },
        {
            "mediaId": "2",
            "postId": "100",
            "tags": json.dumps(["beach", "people", "sunset"]),
            "scenes": json.dumps(["beach", "outdoor"]),
            "caption": "Beautiful sunset at the beach",
            "facesDetected": "2",
            "isSafe": "true",
            "moderationConfidence": "0.98"
        },
        {
            "mediaId": "3",
            "postId": "100",
            "tags": json.dumps(["people", "food", "outdoor"]),
            "scenes": json.dumps(["beach", "outdoor"]),
            "caption": "Beach picnic with friends",
            "facesDetected": "4",
            "isSafe": "true",
            "moderationConfidence": "0.92"
        }
    ]
    
    # Publish aggregation trigger
    message = {
        "postId": "100",
        "mediaInsights": json.dumps(media_insights)
    }
    
    message_id = client.xadd(AGGREGATION_TRIGGER_STREAM, message)
    
    print(f"\n[PUBLISHED] Aggregation trigger:")
    print(f"   Stream: {AGGREGATION_TRIGGER_STREAM}")
    print(f"   Message ID: {message_id}")
    print(f"   Post ID: 100")
    print(f"   Media Count: {len(media_insights)}")
    print(f"   Total Faces: 9 (3+2+4)")
    
    return message_id

def read_aggregation_result(client, timeout=10):
    """Read the aggregation result."""
    print(f"\n[WAITING] For aggregation result (timeout: {timeout}s)...")
    
    try:
        messages = client.xread({AGGREGATION_OUTPUT_STREAM: '0'}, count=1, block=timeout * 1000)
        
        if messages:
            stream_name, stream_messages = messages[0]
            message_id, data = stream_messages[0]
            
            print(f"\n[RECEIVED] Aggregation result:")
            print(f"   Message ID: {message_id}")
            print(f"   Data: {json.dumps(data, indent=2)}")
            
            # Parse and display key insights
            print(f"\n[INSIGHTS] Aggregated Results:")
            print(f"   Event Type: {data.get('eventType', 'N/A')}")
            print(f"   Total Faces: {data.get('totalFaces', 'N/A')}")
            print(f"   Media Count: {data.get('mediaCount', 'N/A')}")
            print(f"   Is Safe: {data.get('isSafe', 'N/A')}")
            
            if data.get('aggregatedTags'):
                tags = json.loads(data['aggregatedTags'])
                print(f"   Top Tags: {', '.join(tags[:5])}")
            
            if data.get('aggregatedScenes'):
                scenes = json.loads(data['aggregatedScenes'])
                print(f"   Scenes: {', '.join(scenes)}")
            
            if data.get('combinedCaption'):
                print(f"   Caption: {data['combinedCaption'][:100]}...")
            
            return data
        else:
            print("[WARNING] No aggregation result received (timeout)")
            return None
    except Exception as e:
        print(f"[ERROR] Error reading aggregation result: {e}")
        return None

def main():
    """Main test function."""
    print("="*60)
    print("POST AGGREGATOR - TEST")
    print("="*60)
    
    # Connect to Redis
    client = connect_redis()
    
    # Check if post_aggregator service is running
    print("\n[INFO] Prerequisites:")
    print("   Make sure post_aggregator service is running:")
    print("   docker compose up -d post_aggregator")
    print()
    
    input("Press ENTER to publish test aggregation trigger...")
    
    # Publish test message
    publish_test_aggregation(client)
    
    # Read result
    result = read_aggregation_result(client, timeout=30)
    
    if result:
        print("\n" + "="*60)
        print("[PASS] TEST PASSED!")
        print("="*60)
        print("\nPost Aggregator service is working correctly!")
        return 0
    else:
        print("\n" + "="*60)
        print("[FAIL] TEST FAILED!")
        print("="*60)
        print("\nNo result received. Check:")
        print("  1. Is post_aggregator service running?")
        print("  2. Check logs: docker compose logs post_aggregator")
        return 1

if __name__ == "__main__":
    sys.exit(main())

