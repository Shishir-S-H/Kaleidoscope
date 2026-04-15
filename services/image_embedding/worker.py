"""Image Embedding Worker

Consumes ml-inference-tasks, runs CLIP-style feature extraction to produce a
512-dim image embedding, and publishes the result to ml-insights-results with
service="image_embedding".

This result is optional for the post aggregation gate (OPTIONAL_SERVICES) but
is required to populate read_model_recommendations_knn via Java's
ReadModelUpdateService.updateRecommendationsKnnReadModel().
"""

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
from shared.utils.retry import publish_to_dlq
from shared.utils.metrics import (
    record_processing_time, record_success, record_failure,
    record_dlq, get_metrics,
)
from shared.utils.health import check_health
from shared.providers.registry import get_provider
from shared.utils.health_server import start_health_server, mark_ready
from shared.utils.result_publisher import publish_ml_insight

LOGGER = get_logger("image-embedding")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STREAM_INPUT = "ml-inference-tasks"
STREAM_OUTPUT = "ml-insights-results"
STREAM_DLQ = "ai-processing-dlq"
CONSUMER_GROUP = "image-embedding-ml-group"
CONSUMER_NAME = "image-embedding-worker-1"

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
        local_file_path = decoded_data.get("localFilePath", "")
        correlation_id = decoded_data.get("correlationId", "")

        LOGGER.info("Received embedding job", extra={
            "message_id": message_id,
            "media_id": media_id,
            "post_id": post_id,
            "local_file_path": local_file_path,
            "correlation_id": correlation_id,
        })

        if not media_id or not local_file_path:
            LOGGER.error("Invalid message format", extra={"data": decoded_data})
            return

        image_bytes = open(local_file_path, "rb").read()

        provider = get_provider("embedding")
        result = provider.embed(image_bytes)

        if not result.embedding or len(result.embedding) == 0:
            LOGGER.warning("Empty embedding returned for mediaId=%s — skipping publish", media_id)
            record_processing_time(time.time() - start_time)
            record_success()
            return

        LOGGER.info(
            "Generated embedding with %d dimensions for mediaId=%s",
            result.dimensions, media_id,
        )

        publish_ml_insight(
            publisher,
            STREAM_OUTPUT,
            media_id=str(media_id),
            post_id=str(post_id),
            service="image_embedding",
            correlation_id=correlation_id,
            image_embedding=result.embedding,
        )

        LOGGER.info("Published embedding result", extra={
            "media_id": media_id,
            "stream": STREAM_OUTPUT,
            "dimensions": result.dimensions,
            "correlation_id": correlation_id,
        })

        record_processing_time(time.time() - start_time)
        record_success()

    except Exception as e:
        record_processing_time(time.time() - start_time)
        record_failure(str(e))

        LOGGER.exception("Error processing embedding message", extra={
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
                service_name="image-embedding",
                retry_count=0,
            )
        except Exception as dlq_error:
            LOGGER.exception("Failed to publish to dead letter queue", extra={
                "dlq_error": str(dlq_error),
                "message_id": message_id,
            })


def main():
    LOGGER.info("Image Embedding Worker starting...")

    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    consumer = None
    publisher = None

    try:
        publisher = RedisStreamPublisher(REDIS_URL)
        consumer = RedisStreamConsumer(REDIS_URL, STREAM_INPUT, CONSUMER_GROUP, CONSUMER_NAME)

        start_health_server(
            service_name="image-embedding",
            health_fn=lambda: check_health(get_metrics(), "image-embedding"),
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
        LOGGER.info("Worker shut down complete")


if __name__ == "__main__":
    main()
