import json
import os
import sys
import uuid
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
LOGGER = get_logger("face-recognition")

# Hugging Face API configuration
HF_API_URL = os.getenv("HF_API_URL")
HF_API_TOKEN = os.getenv("HF_API_TOKEN")

# Redis Streams configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STREAM_INPUT = "post-image-processing"
STREAM_OUTPUT = "face-detection-results"
CONSUMER_GROUP = "face-recognition-group"
CONSUMER_NAME = "face-recognition-worker-1"

def call_hf_api(image_bytes: bytes) -> Dict[str, Any]:
    """
    Call the Hugging Face API for face detection.
    
    Args:
        image_bytes: Raw image bytes to send to the API
    
    Returns:
        Dict with face detection results (faces_detected and faces list)
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
    
    # The API should return a dict with 'faces_detected' and 'faces' list
    api_result = response.json()
    LOGGER.debug("Received API response", extra={
        "faces_detected": api_result.get("faces_detected", 0)
    })
    
    return api_result


def process_face_detection(image_bytes: bytes) -> Dict[str, Any]:
    """
    Process face detection using the Hugging Face API.
    
    Args:
        image_bytes: Raw image bytes
    
    Returns:
        Dict with 'faces_detected' (int) and 'faces' (list of dicts with bbox and embedding)
    """
    # Call the Hugging Face API
    result = call_hf_api(image_bytes)
    
    # Return the result directly (assumes API returns correct format)
    return result


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
        
        LOGGER.info("Received face recognition job", extra={
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
        
        # Run face detection via Hugging Face API (expects 1024-dim embeddings)
        LOGGER.info("Detecting faces", extra={"media_id": media_id})
        detection_result = process_face_detection(image_bytes)
        LOGGER.info("Face detection complete", extra={
            "media_id": media_id,
            "faces_detected": detection_result.get('faces_detected', 0)
        })
        
        # Publish result to face-detection-results stream
        # Format faces for backend consumption
        faces_list = []
        for face in detection_result.get('faces', []):
            faces_list.append({
                "faceId": face.get("face_id", str(uuid.uuid4())),
                "bbox": json.dumps(face.get("bbox", [])),
                "embedding": json.dumps(face.get("embedding", [])),  # 1024-dim from AdaFace model
                "confidence": str(face.get("confidence", 0.0))
            })
        
        result_message = {
            "mediaId": str(media_id),
            "postId": str(post_id),
            "facesDetected": str(detection_result.get('faces_detected', 0)),
            "faces": json.dumps(faces_list)
        }
        
        publisher.publish(STREAM_OUTPUT, result_message)
        LOGGER.info("Published result", extra={
            "media_id": media_id,
            "faces_detected": detection_result.get('faces_detected', 0),
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
    NOTE: Expects HF API to return 1024-dim face embeddings (AdaFace model).
    """
    LOGGER.info("Face Recognition Worker starting (Redis Streams + HuggingFace API)")
    LOGGER.info("Expected embedding dimension: 1024 (AdaFace model)")
    
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
