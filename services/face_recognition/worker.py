import json
import os
import signal
import sys
import time
import threading
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

load_dotenv()

from shared.utils.logger import get_logger
from shared.redis_streams import RedisStreamPublisher, RedisStreamConsumer
from shared.redis_streams.utils import decode_message
from shared.utils.retry import publish_to_dlq
from shared.utils.metrics import (
    record_processing_time, record_success, record_failure,
    record_dlq, get_metrics,
)
from shared.utils.health import check_health
from shared.providers.registry import get_provider
from shared.utils.image_downloader import download_image
from shared.utils.http_client import get_http_session, close_http_session
from shared.utils.url_validator import validate_url, URLValidationError
from shared.utils.health_server import start_health_server, mark_ready

LOGGER = get_logger("face-recognition")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STREAM_INPUT = "post-image-processing"
STREAM_OUTPUT = "face-detection-results"
STREAM_DLQ = "ai-processing-dlq"
CONSUMER_GROUP = "face-recognition-group"
CONSUMER_NAME = "face-recognition-worker-1"

shutdown_event = threading.Event()


def _shutdown_handler(signum, frame):
    LOGGER.info("Shutdown signal received (signal %s)", signum)
    shutdown_event.set()


def handle_message(message_id: str, data: dict, publisher: RedisStreamPublisher):
    decoded_data = None
    start_time = time.time()

    try:
        decoded_data = decode_message(data)
        media_id = int(decoded_data.get("mediaId", 0))
        post_id = int(decoded_data.get("postId", 0))
        media_url = decoded_data.get("mediaUrl", "")
        correlation_id = decoded_data.get("correlationId", "")

        LOGGER.info("Received face recognition job", extra={
            "message_id": message_id,
            "media_id": media_id,
            "post_id": post_id,
            "media_url": media_url,
            "correlation_id": correlation_id,
        })

        if not media_id or not media_url:
            LOGGER.error("Invalid message format", extra={"data": decoded_data})
            return

        validate_url(media_url)
        session = get_http_session()
        image_bytes = download_image(media_url, session, correlation_id=correlation_id)

        provider = get_provider("face")
        result = provider.detect(image_bytes)

        formatted_faces_list = []
        for face in result.faces:
            formatted_faces_list.append({
                "faceId": face.face_id,
                "bbox": face.bbox,
                "embedding": face.embedding,
                "confidence": face.confidence,
            })

        result_message = {
            "mediaId": str(media_id),
            "postId": str(post_id),
            "facesDetected": str(result.faces_detected),
            "faces": json.dumps(formatted_faces_list),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "1",
        }

        publisher.publish(STREAM_OUTPUT, result_message)
        LOGGER.info("Published result", extra={
            "media_id": media_id,
            "faces_detected": result.faces_detected,
            "stream": STREAM_OUTPUT,
            "correlation_id": correlation_id,
        })

        processing_time = time.time() - start_time
        record_processing_time(processing_time)
        record_success()

    except Exception as e:
        processing_time = time.time() - start_time
        record_processing_time(processing_time)
        record_failure(str(e))

        LOGGER.exception("Error processing message", extra={
            "error": str(e),
            "message_id": message_id,
            "correlation_id": decoded_data.get("correlationId", "") if decoded_data else "",
        })

        try:
            record_dlq()
            publish_to_dlq(
                publisher=publisher,
                dlq_stream=STREAM_DLQ,
                original_message_id=message_id,
                original_data=data,
                error=e,
                service_name="face-recognition",
                retry_count=0,
            )
        except Exception as dlq_error:
            LOGGER.exception("Failed to publish to dead letter queue", extra={
                "dlq_error": str(dlq_error),
                "message_id": message_id,
            })


def main():
    LOGGER.info("Face Recognition Worker starting...")

    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    consumer = None
    publisher = None

    try:
        publisher = RedisStreamPublisher(REDIS_URL)
        consumer = RedisStreamConsumer(REDIS_URL, STREAM_INPUT, CONSUMER_GROUP, CONSUMER_NAME)

        start_health_server(
            service_name="face-recognition",
            health_fn=lambda: check_health(get_metrics(), "face-recognition"),
            metrics_fn=get_metrics,
        )

        mark_ready()
        LOGGER.info("Worker ready - waiting for messages")

        def message_handler(message_id, data):
            handle_message(message_id, data, publisher)

        consumer.consume(message_handler, block_ms=5000, count=1)

    except KeyboardInterrupt:
        LOGGER.info("Interrupted by user")
    except Exception as e:
        LOGGER.exception("Unexpected error in main loop", extra={"error": str(e)})
    finally:
        shutdown_event.set()
        if consumer:
            consumer.close()
        if publisher:
            publisher.close()
        close_http_session()
        LOGGER.info("Worker shut down complete")


if __name__ == "__main__":
    main()
