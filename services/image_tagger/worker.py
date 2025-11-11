import json
import os
import sys
import time
import threading
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
from shared.utils.retry import retry_with_backoff, publish_to_dlq
from shared.utils.metrics import record_processing_time, record_success, record_failure, record_retry, record_dlq, get_metrics, ProcessingTimer
from shared.utils.health import check_health

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
DEFAULT_THRESHOLD = float(os.getenv("DEFAULT_THRESHOLD", "0.01"))  # Lowered from 0.05 to 0.01 (1%) to capture more tags

# Redis Streams configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STREAM_INPUT = "post-image-processing"
STREAM_OUTPUT = "ml-insights-results"
STREAM_DLQ = "ai-processing-dlq"  # Dead Letter Queue
CONSUMER_GROUP = "image-tagger-group"
CONSUMER_NAME = "image-tagger-worker-1"

# Retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 30.0  # seconds
BACKOFF_MULTIPLIER = 2.0

@retry_with_backoff(
    max_retries=MAX_RETRIES,
    initial_delay=INITIAL_RETRY_DELAY,
    max_delay=MAX_RETRY_DELAY,
    backoff_multiplier=BACKOFF_MULTIPLIER,
    retryable_exceptions=(requests.RequestException, requests.Timeout, ConnectionError)
)
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
    
    # Log all scores for debugging
    LOGGER.debug("API tag scores received", extra={
        "total_tags": len(api_scores),
        "top_5_scores": dict(sorted(api_scores.items(), key=lambda x: x[1], reverse=True)[:5])
    })
    
    # Filter tags by threshold and get top N
    filtered_tags = [(tag, score) for tag, score in api_scores.items() if score > threshold]
    sorted_tags = sorted(filtered_tags, key=lambda x: x[1], reverse=True)[:top_n]
    
    # If no tags above threshold, still return top N tags (even if below threshold) for better results
    if not sorted_tags and api_scores:
        sorted_tags = sorted(api_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
        LOGGER.info("No tags above threshold, returning top tags anyway", extra={
            "threshold": threshold,
            "top_tags": [tag for tag, _ in sorted_tags]
        })
    
    # Build response
    response = {
        "tags": [tag for tag, _ in sorted_tags],
        "scores": {tag: round(score, 4) for tag, score in sorted_tags}
    }
    
    return response


def handle_message(message_id: str, data: dict, publisher: RedisStreamPublisher):
    """
    Callback function for processing messages from Redis Stream with retry logic and DLQ.
    """
    decoded_data = None
    retry_count = 0
    start_time = time.time()
    
    try:
        # Decode message data
        decoded_data = decode_message(data)
        media_id = int(decoded_data.get("mediaId", 0))
        post_id = int(decoded_data.get("postId", 0))
        media_url = decoded_data.get("mediaUrl", "")
        correlation_id = decoded_data.get("correlationId", "")
        
        LOGGER.info("Received tagging job", extra={
            "message_id": message_id,
            "media_id": media_id,
            "post_id": post_id,
            "media_url": media_url,
            "correlation_id": correlation_id
        })
        
        if not media_id or not media_url:
            LOGGER.error("Invalid message format", extra={"data": decoded_data})
            return
        
        # Retry logic for processing
        last_exception = None
        delay = INITIAL_RETRY_DELAY
        
        for attempt in range(MAX_RETRIES + 1):
            try:
                retry_count = attempt
                
                # Download image from URL (with retry)
                LOGGER.info("Downloading image", extra={
                    "media_id": media_id,
                    "media_url": media_url,
                    "correlation_id": correlation_id,
                    "attempt": attempt + 1
                })
                
                try:
                    response = requests.get(media_url, timeout=30)
                    response.raise_for_status()
                    image_bytes = response.content
                    LOGGER.info("Image downloaded successfully", extra={"media_id": media_id, "correlation_id": correlation_id})
                except (requests.RequestException, requests.Timeout, ConnectionError) as e:
                    if attempt < MAX_RETRIES:
                        LOGGER.warning(f"Image download failed (attempt {attempt + 1}/{MAX_RETRIES + 1}): {str(e)}. Retrying in {delay:.2f} seconds...", extra={
                            "media_id": media_id,
                            "attempt": attempt + 1,
                            "delay": delay,
                            "correlation_id": correlation_id
                        })
                        time.sleep(delay)
                        delay = min(delay * BACKOFF_MULTIPLIER, MAX_RETRY_DELAY)
                        continue
                    else:
                        raise
                
                # Run tagging via Hugging Face API (with retry)
                LOGGER.info("Running tagging", extra={"media_id": media_id, "correlation_id": correlation_id})
                tagging_result = process_image_tagging(image_bytes)
                LOGGER.info("Tagging complete", extra={
                    "media_id": media_id,
                    "num_tags": len(tagging_result['tags']),
                    "tags": tagging_result['tags'],
                    "correlation_id": correlation_id
                })
                
                # Publish result to ml-insights-results stream
                result_message = {
                    "mediaId": str(media_id),
                    "postId": str(post_id),
                    "service": "tagging",
                    "tags": json.dumps(tagging_result['tags']),
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                
                publisher.publish(STREAM_OUTPUT, result_message)
                LOGGER.info("Published result", extra={
                    "media_id": media_id,
                    "stream": STREAM_OUTPUT,
                    "correlation_id": correlation_id
                })
                
                # Record success metrics
                processing_time = time.time() - start_time
                record_processing_time(processing_time)
                record_success()
                
                # Success - exit retry loop
                return
                
            except (requests.RequestException, requests.Timeout, ConnectionError, ValueError) as e:
                last_exception = e
                if attempt < MAX_RETRIES:
                    record_retry()  # Record retry attempt
                    LOGGER.warning(f"Processing failed (attempt {attempt + 1}/{MAX_RETRIES + 1}): {str(e)}. Retrying in {delay:.2f} seconds...", extra={
                        "media_id": media_id,
                        "attempt": attempt + 1,
                        "delay": delay,
                        "correlation_id": correlation_id,
                        "error": str(e)
                    })
                    time.sleep(delay)
                    delay = min(delay * BACKOFF_MULTIPLIER, MAX_RETRY_DELAY)
                else:
                    raise
        
        # If we get here, all retries failed
        if last_exception:
            raise last_exception
            
    except Exception as e:
        # Record failure metrics
        processing_time = time.time() - start_time
        record_processing_time(processing_time)
        record_failure(str(e))
        
        LOGGER.exception("Error processing message after all retries", extra={
            "error": str(e),
            "message_id": message_id,
            "retry_count": retry_count,
            "correlation_id": decoded_data.get("correlationId", "") if decoded_data else ""
        })
        
        # Publish to dead letter queue
        try:
            record_dlq()  # Record DLQ message
            publish_to_dlq(
                publisher=publisher,
                dlq_stream=STREAM_DLQ,
                original_message_id=message_id,
                original_data=data,
                error=e,
                service_name="image-tagger",
                retry_count=retry_count
            )
        except Exception as dlq_error:
            LOGGER.exception("Failed to publish to dead letter queue", extra={
                "dlq_error": str(dlq_error),
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
        
        # Start periodic health check logging (every 5 minutes)
        def health_check_loop():
            while True:
                time.sleep(300)  # 5 minutes
                try:
                    metrics = get_metrics()
                    health = check_health(metrics, "image-tagger")
                    LOGGER.info("Health check", extra={
                        "health_status": health["status"],
                        "metrics": metrics,
                        "health_checks": health["checks"]
                    })
                except Exception as e:
                    LOGGER.exception("Error in health check", extra={"error": str(e)})
        
        health_check_thread = threading.Thread(target=health_check_loop, daemon=True)
        health_check_thread.start()
        
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
