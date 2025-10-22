#!/usr/bin/env python3
"""
Test script for Redis Streams AI services.
This script publishes test messages and monitors the output streams.
"""

import json
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import redis

# Configuration
REDIS_URL = "redis://localhost:6379"
INPUT_STREAM = "post-image-processing"
ML_INSIGHTS_STREAM = "ml-insights-results"
FACE_DETECTION_STREAM = "face-detection-results"

# Sample test image URL (use a public image for testing)
TEST_IMAGE_URL = "https://images.unsplash.com/photo-1506905925346-21bda4d32df4"  # Mountain landscape

def connect_redis():
    """Connect to Redis."""
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        print("✅ Connected to Redis successfully!")
        return client
    except Exception as e:
        print(f"❌ Failed to connect to Redis: {e}")
        sys.exit(1)

def create_consumer_groups(client):
    """Create consumer groups if they don't exist."""
    streams_and_groups = [
        (INPUT_STREAM, "content-moderation-group"),
        (INPUT_STREAM, "image-tagger-group"),
        (INPUT_STREAM, "scene-recognition-group"),
        (INPUT_STREAM, "image-captioning-group"),
        (INPUT_STREAM, "face-recognition-group"),
    ]
    
    for stream, group in streams_and_groups:
        try:
            client.xgroup_create(stream, group, id='0', mkstream=True)
            print(f"✅ Created consumer group '{group}' for stream '{stream}'")
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" in str(e):
                print(f"ℹ️  Consumer group '{group}' already exists")
            else:
                print(f"⚠️  Error creating group '{group}': {e}")

def publish_test_message(client, media_id=1, post_id=1):
    """Publish a test message to the input stream."""
    message = {
        "mediaId": str(media_id),
        "postId": str(post_id),
        "mediaUrl": TEST_IMAGE_URL
    }
    
    try:
        message_id = client.xadd(INPUT_STREAM, message)
        print(f"\n📤 Published test message to '{INPUT_STREAM}':")
        print(f"   Message ID: {message_id}")
        print(f"   Media ID: {media_id}")
        print(f"   Post ID: {post_id}")
        print(f"   Image URL: {TEST_IMAGE_URL}")
        return message_id
    except Exception as e:
        print(f"❌ Failed to publish message: {e}")
        return None

def read_stream(client, stream_name, count=10, block_ms=5000):
    """Read messages from a stream."""
    try:
        messages = client.xread({stream_name: '0'}, count=count, block=block_ms)
        return messages
    except Exception as e:
        print(f"❌ Error reading from '{stream_name}': {e}")
        return []

def monitor_output_streams(client, timeout=60):
    """Monitor output streams for results."""
    print(f"\n👀 Monitoring output streams for {timeout} seconds...")
    print(f"   - {ML_INSIGHTS_STREAM}")
    print(f"   - {FACE_DETECTION_STREAM}\n")
    
    start_time = time.time()
    results = {
        "ml_insights": [],
        "face_detection": []
    }
    
    while time.time() - start_time < timeout:
        # Read from ml-insights-results
        ml_messages = read_stream(client, ML_INSIGHTS_STREAM, count=10, block_ms=1000)
        for stream, messages in ml_messages:
            for msg_id, data in messages:
                print(f"\n📥 Received from {ML_INSIGHTS_STREAM}:")
                print(f"   Message ID: {msg_id}")
                print(f"   Data: {json.dumps(data, indent=2)}")
                results["ml_insights"].append(data)
        
        # Read from face-detection-results
        face_messages = read_stream(client, FACE_DETECTION_STREAM, count=10, block_ms=1000)
        for stream, messages in face_messages:
            for msg_id, data in messages:
                print(f"\n📥 Received from {FACE_DETECTION_STREAM}:")
                print(f"   Message ID: {msg_id}")
                print(f"   Data: {json.dumps(data, indent=2)}")
                results["face_detection"].append(data)
        
        # Check if we've received results from all services
        if len(results["ml_insights"]) >= 4 and len(results["face_detection"]) >= 1:
            print("\n✅ Received results from all 5 services!")
            break
        
        time.sleep(1)
    
    return results

def check_stream_info(client, stream_name):
    """Check information about a stream."""
    try:
        info = client.xinfo_stream(stream_name)
        print(f"\nℹ️  Stream '{stream_name}' info:")
        print(f"   Length: {info.get('length', 0)}")
        print(f"   Groups: {info.get('groups', 0)}")
        return info
    except Exception as e:
        print(f"⚠️  Stream '{stream_name}' does not exist or error: {e}")
        return None

def list_consumer_groups(client, stream_name):
    """List consumer groups for a stream."""
    try:
        groups = client.xinfo_groups(stream_name)
        print(f"\nℹ️  Consumer groups for '{stream_name}':")
        for group in groups:
            print(f"   - {group['name']}: {group['consumers']} consumers, {group['pending']} pending")
        return groups
    except Exception as e:
        print(f"⚠️  No groups for '{stream_name}' or error: {e}")
        return []

def summary_report(results):
    """Print a summary report of the test."""
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    print(f"\n📊 Results Received:")
    print(f"   ML Insights: {len(results['ml_insights'])}")
    print(f"   Face Detection: {len(results['face_detection'])}")
    
    # Check for each service
    services_found = {
        "moderation": False,
        "tagging": False,
        "scene_recognition": False,
        "captioning": False,
        "face_recognition": len(results['face_detection']) > 0
    }
    
    for msg in results['ml_insights']:
        service = msg.get('service')
        if service in services_found:
            services_found[service] = True
    
    print(f"\n✅ Services that responded:")
    for service, responded in services_found.items():
        status = "✅" if responded else "❌"
        print(f"   {status} {service}")
    
    all_responded = all(services_found.values())
    
    print(f"\n{'='*60}")
    if all_responded:
        print("✅ ALL SERVICES WORKING!")
    else:
        print("⚠️  SOME SERVICES DID NOT RESPOND")
    print("="*60)
    
    return all_responded

def main():
    """Main test function."""
    print("="*60)
    print("KALEIDOSCOPE AI - REDIS STREAMS TEST")
    print("="*60)
    
    # Connect to Redis
    client = connect_redis()
    
    # Check existing streams
    print("\n📋 Checking existing streams...")
    check_stream_info(client, INPUT_STREAM)
    check_stream_info(client, ML_INSIGHTS_STREAM)
    check_stream_info(client, FACE_DETECTION_STREAM)
    
    # Create consumer groups
    print("\n🔧 Setting up consumer groups...")
    create_consumer_groups(client)
    
    # List consumer groups
    list_consumer_groups(client, INPUT_STREAM)
    
    # Publish test message
    print("\n" + "="*60)
    input("Press ENTER to publish a test message...")
    
    message_id = publish_test_message(client, media_id=12345, post_id=67890)
    if not message_id:
        sys.exit(1)
    
    # Monitor for results
    print("\n⏳ Waiting for AI services to process...")
    print("   (This may take 10-30 seconds depending on HuggingFace API)")
    
    results = monitor_output_streams(client, timeout=120)
    
    # Print summary
    all_ok = summary_report(results)
    
    # Exit with appropriate code
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)

