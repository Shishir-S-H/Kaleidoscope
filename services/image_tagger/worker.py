import json
import os
import sys
from pathlib import Path
from typing import Dict, Any
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
LOGGER = get_logger("image-tagger")

# Hugging Face API configuration
HF_API_URL = os.getenv("HF_API_URL")
HF_API_TOKEN = os.getenv("HF_API_TOKEN")

# Default image tags for zero-shot classification
IMAGE_TAGS = [
    "person", "people", "face", "car", "vehicle", "building", "architecture",
    "tree", "nature", "sky", "water", "beach", "mountain", "forest",
    "food", "animal", "dog", "cat", "bird", "indoor", "outdoor",
    "city", "street", "road", "sunset", "sunrise", "night", "day"
]

# Tagging configuration
DEFAULT_TOP_N = int(os.getenv("DEFAULT_TOP_N", "5"))
DEFAULT_THRESHOLD = float(os.getenv("DEFAULT_THRESHOLD", "0.05"))

# Redis Streams configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STREAM_INPUT = "post-image-processing"
STREAM_OUTPUT = "ml-insights-results"
CONSUMER_GROUP = "image-tagger-group"
CONSUMER_NAME = "image-tagger-worker-1"

def call_hf_api(image_bytes: bytes) -> Dict[str, Any]:
    """
    Call the Hugging Face API to get image tags and scores.
    
    Args:
        image_bytes: Raw image bytes to send to the API
    
    Returns:
        Dict with tag probabilities from the API
    """
    if not HF_API_URL:
        raise ValueError("HF_API_URL environment variable not set")
    
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}
    
    LOGGER.debug("Calling Hugging Face API", extra={"api_url": HF_API_URL})
    
    # Prepare multipart/form-data request to match our HF Space format
    files = {
        'file': ('image.jpg', image_bytes, 'image/jpeg'),
        'labels': (None, json.dumps(IMAGE_TAGS))
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
    
    # Convert to a dictionary of tag: score
    scores = {}
    if isinstance(api_result, list):
        for item in api_result:
            if "label" in item and "score" in item:
                scores[item["label"]] = item["score"]
    
    return scores


def process_image_tagging(image_bytes: bytes, top_n: int = None, threshold: float = None) -> Dict[str, Any]:
    """
    Process image tagging using the Hugging Face API.
    
    Args:
        image_bytes: Raw image bytes
        top_n: Number of top tags to return
        threshold: Minimum score threshold for tags
    
    Returns:
        Dict with 'tags' (list) and 'scores' (dict)
    """
    # Use defaults if not provided
    top_n = top_n or DEFAULT_TOP_N
    threshold = threshold or DEFAULT_THRESHOLD
    
    # Call the Hugging Face API
    api_scores = call_hf_api(image_bytes)
    
    # Filter tags by threshold and get top N
    filtered_tags = [(tag, score) for tag, score in api_scores.items() if score > threshold]
    sorted_tags = sorted(filtered_tags, key=lambda x: x[1], reverse=True)[:top_n]
    
    # Build response
    response = {
        "tags": [tag for tag, _ in sorted_tags],
        "scores": {tag: round(score, 4) for tag, score in sorted_tags}
    }
    
    return response


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
        
        LOGGER.info("Received tagging job", extra={
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
        
        # Run tagging via Hugging Face API
        LOGGER.info("Running tagging", extra={"media_id": media_id})
        tagging_result = process_image_tagging(image_bytes)
        LOGGER.info("Tagging complete", extra={
            "media_id": media_id,
            "num_tags": len(tagging_result['tags']),
            "tags": tagging_result['tags']
        })
        
        # Publish result to ml-insights-results stream
        result_message = {
            "mediaId": str(media_id),
            "postId": str(post_id),
            "service": "tagging",
            "tags": json.dumps(tagging_result['tags'])
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
    LOGGER.info("Image Tagger Worker starting (Redis Streams + HuggingFace API)")
    
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
            "consumer_group": CONSUMER_GROUP,
            "default_top_n": DEFAULT_TOP_N,
            "default_threshold": DEFAULT_THRESHOLD
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
