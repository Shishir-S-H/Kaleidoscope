"""Face Matcher Worker.

Consumes events from ``face-detection-results`` (published by face_recognition).
For each detected face with an embedding, issues a KNN query against
``known_faces_index`` in Elasticsearch. When the top-1 match score exceeds
``KNN_CONFIDENCE_THRESHOLD`` (default 0.85), publishes a face match event to
``face-recognition-results`` so the Java FaceRecognitionConsumer can process it.

Stream routing fixed (GAP-1/GAP-3): was face-tag-suggestions, now
face-recognition-results to match Java ConsumerStreamConstants.
Payload field names match Java FaceRecognitionResultDTO (GAP-1/GAP-7):
  suggestedUserId (was matchedUserId), confidenceScore as float (was str).
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
from shared.utils.retry import publish_to_dlq
from shared.utils.metrics import (
    record_processing_time, record_success, record_failure,
    record_dlq, get_metrics,
)
from shared.utils.health import check_health
from shared.utils.health_server import start_health_server, mark_ready

LOGGER = get_logger("face-matcher")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
ES_HOST = os.getenv("ES_HOST", "http://elasticsearch:9200")
KNN_CONFIDENCE_THRESHOLD = float(os.getenv("KNN_CONFIDENCE_THRESHOLD", "0.85"))

STREAM_INPUT = "face-detection-results"
STREAM_OUTPUT = "face-recognition-results"
STREAM_DLQ = "ai-processing-dlq"
CONSUMER_GROUP = "face-matcher-group"
CONSUMER_NAME = "face-matcher-worker-1"

KNOWN_FACES_INDEX = "known_faces_index"
KNN_NUM_CANDIDATES = 50

shutdown_event = threading.Event()


def _shutdown_handler(signum, frame):
    LOGGER.info("Shutdown signal received (signal %s)", signum)
    shutdown_event.set()


def _knn_query(es_client, embedding: list) -> dict | None:
    """Run a KNN search against known_faces_index and return the top hit or None."""
    response = es_client.search(
        index=KNOWN_FACES_INDEX,
        body={
            "knn": {
                "field": "face_embedding",
                "query_vector": embedding,
                "k": 1,
                "num_candidates": KNN_NUM_CANDIDATES,
                "filter": {"term": {"is_active": True}},
            }
        },
    )
    hits = response["hits"]["hits"]
    return hits[0] if hits else None


def handle_message(
    message_id: str,
    data: dict,
    publisher: RedisStreamPublisher,
    es_client,
):
    decoded_data = None
    start_time = time.time()

    try:
        decoded_data = decode_message(data)

        media_id = str(decoded_data.get("mediaId", ""))
        post_id = str(decoded_data.get("postId", ""))
        correlation_id = str(decoded_data.get("correlationId", ""))
        faces_detected = int(decoded_data.get("facesDetected", 0))
        faces_raw = decoded_data.get("faces", [])

        if not media_id or faces_detected == 0:
            record_success()
            return

        if isinstance(faces_raw, list):
            faces = faces_raw
        else:
            try:
                faces = json.loads(str(faces_raw))
            except (json.JSONDecodeError, TypeError) as exc:
                LOGGER.warning("Invalid faces JSON", extra={"error": str(exc), "media_id": media_id})
                record_failure(str(exc))
                return

        threshold = float(os.getenv("KNN_CONFIDENCE_THRESHOLD", str(KNN_CONFIDENCE_THRESHOLD)))
        matches_published = 0

        for face in faces:
            face_id = str(face.get("faceId", ""))
            embedding = face.get("embedding", [])
            if not embedding:
                continue

            hit = _knn_query(es_client, embedding)
            if hit is None:
                continue

            score = hit["_score"]
            if score < threshold:
                LOGGER.debug("Face below threshold", extra={
                    "face_id": face_id, "score": score, "threshold": threshold
                })
                continue

            source = hit["_source"]
            matched_user_id = str(source.get("user_id", ""))
            matched_username = str(source.get("username", ""))

            publisher.publish(STREAM_OUTPUT, {
                "mediaId": media_id,
                "postId": post_id,
                "faceId": face_id,
                "suggestedUserId": matched_user_id,
                "matchedUsername": matched_username,
                "confidenceScore": float(score),
                "correlationId": correlation_id,
            })
            matches_published += 1

            LOGGER.info("Face tag suggestion published", extra={
                "media_id": media_id,
                "face_id": face_id,
                "matched_user_id": matched_user_id,
                "score": score,
                "correlation_id": correlation_id,
            })

        record_processing_time(time.time() - start_time)
        record_success()

    except Exception as e:
        record_processing_time(time.time() - start_time)
        record_failure(str(e))

        LOGGER.exception("Error processing face match", extra={
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
                service_name="face-matcher",
                retry_count=0,
            )
        except Exception as dlq_error:
            LOGGER.exception("Failed to publish to dead letter queue", extra={
                "dlq_error": str(dlq_error),
                "message_id": message_id,
            })


def main():
    LOGGER.info("Face Matcher Worker starting...")

    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    consumer = None
    publisher = None
    es_client = None

    try:
        from elasticsearch import Elasticsearch
        es_client = Elasticsearch([ES_HOST])

        publisher = RedisStreamPublisher(REDIS_URL)
        consumer = RedisStreamConsumer(
            REDIS_URL, STREAM_INPUT, CONSUMER_GROUP, CONSUMER_NAME,
            shutdown_event=shutdown_event,
        )

        start_health_server(
            service_name="face-matcher",
            health_fn=lambda: check_health(get_metrics(), "face-matcher"),
            metrics_fn=get_metrics,
        )

        mark_ready()
        LOGGER.info("Worker ready - waiting for messages")

        consumer.consume(
            lambda msg_id, data: handle_message(msg_id, data, publisher, es_client),
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
        LOGGER.info("Worker shut down complete")


if __name__ == "__main__":
    main()
