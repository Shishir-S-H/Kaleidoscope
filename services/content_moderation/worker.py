import json
import os
import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
from dotenv import load_dotenv

import requests

# Add parent directories to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables
load_dotenv()

# Import logger and Redis Streams
from shared.utils.logger import get_logger
from shared.redis_streams import RedisStreamPublisher, RedisStreamConsumer
from shared.redis_streams.utils import decode_message

# Initialize logger
LOGGER = get_logger("content-moderation")

# Hugging Face API configuration
HF_API_URL = os.getenv("HF_API_URL")
HF_API_TOKEN = os.getenv("HF_API_TOKEN")

# Content moderation labels
MODERATION_LABELS = [
    "safe content", "appropriate content",
    "nsfw content", "explicit content", "nudity",
    "violence", "gore"
]

# Redis Streams configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STREAM_INPUT = "post-image-processing"
STREAM_OUTPUT = "ml-insights-results"
CONSUMER_GROUP = "content-moderation-group"
CONSUMER_NAME = "content-moderation-worker-1"

def call_hf_api(image_bytes: bytes) -> Dict[str, Any]:
    """
    Call the Hugging Face API to get content moderation scores.
    
    Args:
        image_bytes: Raw image bytes to send to the API
    
    Returns:
        Dict with classification scores from the API
    """
    if not HF_API_URL:
        raise ValueError("HF_API_URL environment variable not set")
    
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}
    
    LOGGER.debug("Calling Hugging Face API", extra={"api_url": HF_API_URL})
    
    # Prepare multipart/form-data request to match our HF Space format
    files = {
        'file': ('image.jpg', image_bytes, 'image/jpeg'),
        'labels': (None, json.dumps(MODERATION_LABELS))
    }
    
    response = requests.post(
        HF_API_URL,
        headers=headers,
        files=files,
        timeout=60
    )
    response.raise_for_status()
    
    # The API returns either:
    # - HF Inference API format: [{"label": "...", "score": ...}, ...]
    # - Our HF Space format: {"results": [{"label": "...", "score": ...}, ...]}
    api_result = response.json()
    
    # Handle both formats
    if isinstance(api_result, dict) and "results" in api_result:
        api_result = api_result["results"]  # Extract list from our Space format
    
    LOGGER.debug("Received API response", extra={"result_count": len(api_result) if isinstance(api_result, list) else 0})
    
    # Convert to a dictionary of label: score
    scores = {}
    if isinstance(api_result, list):
        for item in api_result:
            if "label" in item and "score" in item:
                scores[item["label"]] = item["score"]
    
    return scores


def moderate_image(image_bytes: bytes) -> Dict[str, Any]:
    """
    Run moderation logic on an image using the Hugging Face API.
    
    Args:
        image_bytes: Raw image bytes
    
    Returns:
        Dict with 'is_safe' (bool) and 'scores' (dict)
    """
    # Call the Hugging Face API
    api_scores = call_hf_api(image_bytes)
    
    # Calculate safety score using the same logic as the original
    unsafe_scores = [api_scores.get(label, 0.0) for label in ["nsfw", "nudity", "violence"] if label in api_scores]
    
    # Adjust thresholds for the softmax probability scale
    unsafe_threshold = 0.15
    safe_threshold = 0.16
    
    # Check if any unsafe content is detected above threshold
    has_unsafe = any(score > unsafe_threshold for score in unsafe_scores)
    
    # Check if safe content is detected
    safe_labels = ["safe", "appropriate"]
    safe_scores = [api_scores.get(label, 0.0) for label in safe_labels if label in api_scores]
    has_safe = any(score > safe_threshold for score in safe_scores)
    
    # Calculate if content is safe
    max_unsafe_score = max(unsafe_scores) if unsafe_scores else 0.0
    max_safe_score = max(safe_scores) if safe_scores else 0.0
    
    score_gap = max_safe_score - max_unsafe_score
    significant_gap = score_gap > 0.01
    
    is_safe = (not has_unsafe) or (has_safe and significant_gap)
    
    # Find top label and confidence
    if api_scores:
        sorted_scores = sorted(api_scores.items(), key=lambda x: x[1], reverse=True)
        top_label = sorted_scores[0][0]
        confidence = sorted_scores[0][1]
    else:
        top_label = "unknown"
        confidence = 0.0
    
    return {
        "is_safe": is_safe,
        "scores": {k: round(v, 4) for k, v in api_scores.items()},
        "top_label": top_label,
        "confidence": round(confidence, 4)
    }


def handle_message(message_id: str, data: dict, publisher: RedisStreamPublisher):
    """
    Callback function for processing messages from Redis Stream.
    """
    try:
        # Decode message data
        decoded_data = decode_message(data)
        media_id = int(decoded_data.get("mediaId", 0))
        post_id = int(decoded_data.get("postId", 0))
        media_url = decoded_data.get("mediaUrl", "")
        
        LOGGER.info("Received moderation job", extra={
            "message_id": message_id,
            "media_id": media_id,
            "post_id": post_id,
            "media_url": media_url
        })
        
        if not media_id or not media_url:
            LOGGER.error("Invalid message format", extra={"data": decoded_data})
            return
        
        # Download image from URL
        LOGGER.info("Downloading image", extra={"media_id": media_id, "media_url": media_url})
        response = requests.get(media_url, timeout=30)
        response.raise_for_status()
        image_bytes = response.content
        LOGGER.info("Image downloaded successfully", extra={"media_id": media_id})
        
        # Run moderation via Hugging Face API
        LOGGER.info("Running moderation", extra={"media_id": media_id})
        moderation_result = moderate_image(image_bytes)
        LOGGER.info("Moderation complete", extra={
            "media_id": media_id,
            "is_safe": moderation_result['is_safe'],
            "top_label": moderation_result.get('top_label')
        })
        
        # Publish result to ml-insights-results stream
        result_message = {
            "mediaId": str(media_id),
            "postId": str(post_id),
            "service": "moderation",
            "isSafe": "true" if moderation_result["is_safe"] else "false",
            "moderationConfidence": str(moderation_result.get("confidence", 0.0)),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        publisher.publish(STREAM_OUTPUT, result_message)
        LOGGER.info("Published result", extra={
            "media_id": media_id,
            "stream": STREAM_OUTPUT
        })
        
    except Exception as e:
        LOGGER.exception("Error processing message", extra={
            "error": str(e),
            "message_id": message_id
        })


def main():
    """
    Main worker function using Redis Streams.
    """
    LOGGER.info("Content Moderation Worker starting (Redis Streams + HuggingFace API)")
    
    # Validate HF API configuration
    if not HF_API_URL:
        LOGGER.error("HF_API_URL environment variable is required. Exiting.")
        return
    
    LOGGER.info("Using Hugging Face API", extra={"api_url": HF_API_URL})
    LOGGER.info("Connecting to Redis Streams", extra={"redis_url": REDIS_URL})
    
    try:
        # Initialize publisher and consumer
        publisher = RedisStreamPublisher(REDIS_URL)
        consumer = RedisStreamConsumer(
            REDIS_URL,
            STREAM_INPUT,
            CONSUMER_GROUP,
            CONSUMER_NAME
        )
        
        LOGGER.info("Connected to Redis Streams", extra={
            "input_stream": STREAM_INPUT,
            "output_stream": STREAM_OUTPUT,
            "consumer_group": CONSUMER_GROUP
        })
        
        # Define handler with publisher bound
        def message_handler(message_id: str, data: dict):
            handle_message(message_id, data, publisher)
        
        LOGGER.info("Worker ready - waiting for messages")
        
        # Start consuming (blocks indefinitely)
        consumer.consume(message_handler, block_ms=5000, count=1)
        
    except KeyboardInterrupt:
        LOGGER.warning("Interrupted by user")
    except Exception as e:
        LOGGER.exception("Unexpected error in main loop", extra={"error": str(e)})
    finally:
        LOGGER.info("Worker shutting down")


if __name__ == "__main__":
    main()
