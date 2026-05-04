"""Profile Enrollment Worker.

Consumes events from ``profile-picture-processing`` (published by the Java
backend when a user uploads or changes their profile picture). Downloads the
image, extracts a face embedding via the configured face provider (Google or HF),
and publishes the embedding payload to ``user-profile-face-embedding-results`` so the Java
UserProfileFaceEmbeddingConsumer can update its read model.

Stream routing fixed (GAP-2): was es-sync-queue (bypassed Java entirely),
now user-profile-face-embedding-results to match Java ConsumerStreamConstants.
DTO fields match Java ProfilePictureEventDTO (GAP-4): imageUrl (not profilePicUrl),
no username field (Java does not publish it).
"""

import json
import os
import signal
import sys
import time
import threading
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

load_dotenv()

from shared.utils.logger import get_logger
from shared.redis_streams import RedisStreamPublisher, RedisStreamConsumer
from shared.redis_streams.utils import decode_message
from shared.schemas.schemas import ProfilePictureEventDTO
from shared.utils.retry import publish_to_dlq
from shared.utils.metrics import (
    record_processing_time, record_success, record_failure,
    record_dlq, get_metrics,
)
from shared.utils.health import check_health
from shared.providers.registry import get_provider
from shared.utils.image_downloader import download_image
from shared.utils.http_client import get_http_session, close_http_session
from shared.utils.health_server import start_health_server, mark_ready

LOGGER = get_logger("profile-enrollment")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STREAM_INPUT = "profile-picture-processing"
STREAM_OUTPUT = "user-profile-face-embedding-results"
STREAM_DLQ = "ai-processing-dlq"
CONSUMER_GROUP = "profile-enrollment-group"
CONSUMER_NAME = "profile-enrollment-worker-1"

shutdown_event = threading.Event()


def _shutdown_handler(signum, frame):
    LOGGER.info("Shutdown signal received (signal %s)", signum)
    shutdown_event.set()


def handle_message(message_id: str, data: dict, publisher: RedisStreamPublisher):
    decoded_data = None
    start_time = time.time()

    try:
        decoded_data = decode_message(data)

        event = ProfilePictureEventDTO.model_validate({
            "userId": str(decoded_data.get("userId", "")),
            "imageUrl": str(decoded_data.get("imageUrl", "")),
            "correlationId": str(decoded_data.get("correlationId", "")),
        })

        LOGGER.info("Received profile enrollment job", extra={
            "message_id": message_id,
            "user_id": event.userId,
            "correlation_id": event.correlationId,
        })

        session = get_http_session()
        image_bytes = download_image(event.imageUrl, session,
                                     correlation_id=event.correlationId)

        provider = get_provider("face")
        result = provider.detect(image_bytes)

        if not result.faces:
            LOGGER.warning(
                "No face detected in profile picture; skipping enrollment",
                extra={"user_id": event.userId, "url": event.imageUrl},
            )
            record_success()
            return

        best_face = max(result.faces, key=lambda f: f.confidence)

        publisher.publish(STREAM_OUTPUT, {
            "userId": event.userId,
            "faceEmbedding": json.dumps(best_face.embedding),
            "correlationId": event.correlationId,
        })

        LOGGER.info("Face embedding published for Java consumption", extra={
            "user_id": event.userId,
            "stream": STREAM_OUTPUT,
            "correlation_id": event.correlationId,
        })

        record_processing_time(time.time() - start_time)
        record_success()

    except Exception as e:
        record_processing_time(time.time() - start_time)
        record_failure(str(e))

        LOGGER.exception("Error processing profile enrollment", extra={
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
                service_name="profile-enrollment",
                retry_count=0,
            )
        except Exception as dlq_error:
            LOGGER.exception("Failed to publish to dead letter queue", extra={
                "dlq_error": str(dlq_error),
                "message_id": message_id,
            })


def main():
    LOGGER.info("Profile Enrollment Worker starting...")

    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    consumer = None
    publisher = None

    try:
        publisher = RedisStreamPublisher(REDIS_URL)
        consumer = RedisStreamConsumer(REDIS_URL, STREAM_INPUT, CONSUMER_GROUP, CONSUMER_NAME,
                                       shutdown_event=shutdown_event)

        start_health_server(
            service_name="profile-enrollment",
            health_fn=lambda: check_health(get_metrics(), "profile-enrollment"),
            metrics_fn=get_metrics,
        )

        mark_ready()
        LOGGER.info("Worker ready - waiting for messages")

        consumer.consume(
            lambda msg_id, data: handle_message(msg_id, data, publisher),
            block_ms=5000,
            count=1,
        )

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
