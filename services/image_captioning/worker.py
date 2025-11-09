import json
import os
import sys
import time
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

# Initialize logger
LOGGER = get_logger("image-captioning")

# Hugging Face API configuration
HF_API_URL = os.getenv("HF_API_URL")
HF_API_TOKEN = os.getenv("HF_API_TOKEN")

# Redis Streams configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STREAM_INPUT = "post-image-processing"
STREAM_OUTPUT = "ml-insights-results"
STREAM_DLQ = "ai-processing-dlq"  # Dead Letter Queue
CONSUMER_GROUP = "image-captioning-group"
CONSUMER_NAME = "image-captioning-worker-1"

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
def call_hf_api(image_bytes: bytes) -> str:
    """
    Call the Hugging Face API for image-to-text captioning.
    
    Args:
        image_bytes: Raw image bytes to send to the API
    
    Returns:
        Generated caption text
    """
    if not HF_API_URL:
        raise ValueError("HF_API_URL environment variable not set")
    
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}
    
    LOGGER.debug("Calling Hugging Face API", extra={"api_url": HF_API_URL})
    
    # Prepare multipart/form-data request to match our HF Space format
    files = {
        'file': ('image.jpg', image_bytes, 'image/jpeg')
    }
    
    response = requests.post(
        HF_API_URL,
        headers=headers,
        files=files,
        timeout=60
    )
    response.raise_for_status()
    
    # The API returns a list with a single dictionary containing 'generated_text'
    # or our Space format: {"generated_text": "..."}
    api_result = response.json()
    LOGGER.debug("Received API response", extra={"result": api_result})
    
    # Extract caption from response
    if isinstance(api_result, list) and len(api_result) > 0:
        caption = api_result[0].get("generated_text", "")
    elif isinstance(api_result, dict):
        caption = api_result.get("generated_text", "")
    else:
        caption = ""
    
    return caption


def process_image_captioning(image_bytes: bytes) -> Dict[str, Any]:
    """
    Generate a caption for an image using the Hugging Face API.
    
    Args:
        image_bytes: Raw image bytes
    
    Returns:
        Dict with 'caption' (str)
    """
    # Call the Hugging Face API
    caption = call_hf_api(image_bytes)
    
    # Build response
    response = {
        "caption": caption
    }
    
    return response


def handle_message(message_id: str, data: dict, publisher: RedisStreamPublisher):
    """
    Callback function for processing messages from Redis Stream with retry logic and DLQ.
    """
    decoded_data = None
    retry_count = 0
    
    try:
        # Decode message data
        decoded_data = decode_message(data)
        media_id = int(decoded_data.get("mediaId", 0))
        post_id = int(decoded_data.get("postId", 0))
        media_url = decoded_data.get("mediaUrl", "")
        correlation_id = decoded_data.get("correlationId", "")
        
        LOGGER.info("Received captioning job", extra={
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
                
                # Generate caption via Hugging Face API (with retry)
                LOGGER.info("Generating caption", extra={"media_id": media_id, "correlation_id": correlation_id})
                caption_result = process_image_captioning(image_bytes)
                LOGGER.info("Caption generated", extra={
                    "media_id": media_id,
                    "caption": caption_result['caption'],
                    "correlation_id": correlation_id
                })
                
                # Publish result to ml-insights-results stream
                result_message = {
                    "mediaId": str(media_id),
                    "postId": str(post_id),
                    "service": "captioning",
                    "caption": caption_result['caption'],
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                
                publisher.publish(STREAM_OUTPUT, result_message)
                LOGGER.info("Published result", extra={
                    "media_id": media_id,
                    "stream": STREAM_OUTPUT,
                    "correlation_id": correlation_id
                })
                
                # Success - exit retry loop
                return
                
            except (requests.RequestException, requests.Timeout, ConnectionError, ValueError) as e:
                last_exception = e
                if attempt < MAX_RETRIES:
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
        LOGGER.exception("Error processing message after all retries", extra={
            "error": str(e),
            "message_id": message_id,
            "retry_count": retry_count,
            "correlation_id": decoded_data.get("correlationId", "") if decoded_data else ""
        })
        
        # Publish to dead letter queue
        try:
            publish_to_dlq(
                publisher=publisher,
                dlq_stream=STREAM_DLQ,
                original_message_id=message_id,
                original_data=data,
                error=e,
                service_name="image-captioning",
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
    LOGGER.info("Image Captioning Worker starting (Redis Streams + HuggingFace API)")
    
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
