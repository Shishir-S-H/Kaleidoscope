import base64
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
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
LOGGER = get_logger("scene-recognition")

# Hugging Face API configuration
HF_API_URL = os.getenv("HF_API_URL")
HF_API_TOKEN = os.getenv("HF_API_TOKEN")
SCENE_LABELS = os.getenv("SCENE_LABELS", "beach,mountains,urban,office,restaurant,forest,desert,lake,park,indoor,outdoor,rural,coastal,mountainous,tropical,arctic").split(",")

# Scene recognition configuration
DEFAULT_THRESHOLD = float(os.getenv("DEFAULT_THRESHOLD", "0.01"))

# Redis Streams configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STREAM_INPUT = "post-image-processing"
STREAM_OUTPUT = "ml-insights-results"
CONSUMER_GROUP = "scene-recognition-group"
CONSUMER_NAME = "scene-recognition-worker-1"

def call_hf_api(image_bytes: bytes, candidate_labels: List[str]) -> List[Dict[str, Any]]:
    """
    Call the Hugging Face API for zero-shot image classification.
    
    Args:
        image_bytes: Raw image bytes to send to the API
        candidate_labels: List of possible scene labels
    
    Returns:
        List of dictionaries with 'label' and 'score' keys
    """
    if not HF_API_URL:
        raise ValueError("HF_API_URL environment variable not set")
    
    if not candidate_labels:
        raise ValueError("SCENE_LABELS must be configured")
    
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}
    
    LOGGER.debug("Calling Hugging Face API", extra={
        "api_url": HF_API_URL,
        "num_labels": len(candidate_labels)
    })
    
    # Prepare multipart/form-data request to match our HF Space format
    files = {
        'file': ('image.jpg', image_bytes, 'image/jpeg'),
        'labels': (None, json.dumps(candidate_labels))
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
    
    LOGGER.debug("Received API response", extra={"result_count": len(api_result) if isinstance(api_result, list) else 1})
    
    return api_result


def process_scene_recognition(image_bytes: bytes, threshold: float = None) -> Dict[str, Any]:
    """
    Run scene recognition logic using the Hugging Face API.
    
    Args:
        image_bytes: Raw image bytes
        threshold: Minimum score threshold for scenes
    
    Returns:
        Dict with 'scene' (str), 'confidence' (float), and 'scores' (dict)
    """
    # Use default if not provided
    threshold = threshold or DEFAULT_THRESHOLD
    
    # Call the Hugging Face API with scene labels
    api_result = call_hf_api(image_bytes, SCENE_LABELS)
    
    # Convert API result to scores dictionary
    scores = {}
    if isinstance(api_result, list):
        for item in api_result:
            if "label" in item and "score" in item:
                scores[item["label"]] = item["score"]
    
    # Filter scenes by threshold
    filtered_scenes = {scene: score for scene, score in scores.items() if score > threshold}
    
    # Get best scene
    if scores:
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_scene = sorted_scores[0][0]
        best_score = sorted_scores[0][1]
    else:
        best_scene = "unknown"
        best_score = 0.0
    
    # Build response
    response = {
        "scene": best_scene,
        "confidence": round(best_score, 4),
        "scores": {scene: round(score, 4) for scene, score in filtered_scenes.items()}
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
        correlation_id = decoded_data.get("correlationId", "")  # Extract correlationId for log tracing
        
        LOGGER.info("Received scene recognition job", extra={
            "message_id": message_id,
            "media_id": media_id,
            "post_id": post_id,
            "media_url": media_url,
            "correlation_id": correlation_id
        })
        
        if not media_id or not media_url:
            LOGGER.error("Invalid message format", extra={"data": decoded_data})
            return
        
        # Download image from URL
        LOGGER.info("Downloading image", extra={"media_id": media_id, "media_url": media_url, "correlation_id": correlation_id})
        response = requests.get(media_url, timeout=30)
        response.raise_for_status()
        image_bytes = response.content
        LOGGER.info("Image downloaded successfully", extra={"media_id": media_id, "correlation_id": correlation_id})
        
        # Run scene recognition via Hugging Face API
        LOGGER.info("Running scene recognition", extra={"media_id": media_id, "correlation_id": correlation_id})
        scene_result = process_scene_recognition(image_bytes)
        LOGGER.info("Scene recognition complete", extra={
            "media_id": media_id,
            "scene": scene_result['scene'],
            "confidence": scene_result['confidence'],
            "correlation_id": correlation_id
        })
        
        # Publish result to ml-insights-results stream
        result_message = {
            "mediaId": str(media_id),
            "postId": str(post_id),
            "service": "scene_recognition",
            "scenes": json.dumps(list(scene_result['scores'].keys())),  # All scenes above threshold
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        publisher.publish(STREAM_OUTPUT, result_message)
        LOGGER.info("Published result", extra={
            "media_id": media_id,
            "stream": STREAM_OUTPUT,
            "correlation_id": correlation_id
        })
        
    except Exception as e:
        LOGGER.exception("Error processing message", extra={
            "error": str(e),
            "message_id": message_id,
            "correlation_id": decoded_data.get("correlationId", "") if 'decoded_data' in locals() else ""
        })


def main():
    """
    Main worker function using Redis Streams.
    """
    LOGGER.info("Scene Recognition Worker starting (Redis Streams + HuggingFace API)")
    
    # Validate HF API configuration
    if not HF_API_URL:
        LOGGER.error("HF_API_URL environment variable is required. Exiting.")
        return
    
    if not SCENE_LABELS:
        LOGGER.error("SCENE_LABELS environment variable is required. Exiting.")
        return
    
    LOGGER.info("Using Hugging Face API", extra={
        "api_url": HF_API_URL,
        "num_labels": len(SCENE_LABELS)
    })
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
