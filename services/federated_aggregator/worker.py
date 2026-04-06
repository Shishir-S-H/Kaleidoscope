"""Federated Aggregator Worker — Phase 4.

Consumes gradient-update events from ``federated-gradient-updates``, validates
them against the strict ``ModelUpdateEventDTO`` contract, computes the arithmetic
mean of the gradient payload (a stand-in for a real federated averaging step),
and publishes the result to ``global-model-state``.

No PyTorch / TensorFlow logic is used here — the aggregation is intentionally
reduced to a simple mean so that the service can be tested without ML
dependencies.
"""

import json
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.redis_streams import RedisStreamConsumer, RedisStreamPublisher
from shared.schemas.schemas import ModelUpdateEventDTO
from shared.utils.logger import get_logger

LOGGER = get_logger("federated-aggregator")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

STREAM_INPUT = "federated-gradient-updates"
STREAM_OUTPUT = "global-model-state"
STREAM_DLQ = "ai-processing-dlq"

CONSUMER_GROUP = "federated-aggregator-group"
CONSUMER_NAME = "federated-aggregator-worker-1"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _decode_event(data: Dict[Any, Any]) -> Dict[str, Any]:
    """Decode a raw Redis bytes/string dict into a form suitable for Pydantic.

    Redis stores all values as bytes. The ``gradientPayload`` field is a list
    serialised as a JSON string on the wire; this function deserialises it back
    to ``List[float]`` so that the strict DTO can accept it.
    """
    decoded: Dict[str, Any] = {}
    for k, v in data.items():
        key = k.decode("utf-8") if isinstance(k, bytes) else str(k)
        val = v.decode("utf-8") if isinstance(v, bytes) else v
        decoded[key] = val

    gradient_raw = decoded.get("gradientPayload")
    if isinstance(gradient_raw, str):
        try:
            decoded["gradientPayload"] = json.loads(gradient_raw)
        except (json.JSONDecodeError, ValueError):
            pass  # leave as-is; Pydantic will reject it with a clear error

    return decoded


def _average_gradients(payload: List[float]) -> float:
    """Return the arithmetic mean of *payload*.

    Raises:
        ValueError: if *payload* is empty (division by zero is meaningless).
    """
    if not payload:
        raise ValueError("gradientPayload must not be empty")
    return sum(payload) / len(payload)


# ---------------------------------------------------------------------------
# Worker class
# ---------------------------------------------------------------------------

class FederatedAggregatorWorker:
    """Validates and aggregates federated gradient updates.

    The publisher is injected at construction time so unit tests never touch
    a real Redis connection.
    """

    def __init__(self, publisher: RedisStreamPublisher) -> None:
        self._publisher = publisher

    def handle_message(self, message_id: str, data: Dict[Any, Any]) -> None:
        """Process one incoming gradient update event.

        Args:
            message_id: Redis stream message ID (echoed in DLQ payloads).
            data:        Raw field dict from the Redis stream (bytes or strings).
        """
        # --- 1. Decode + validate incoming event ---
        try:
            normalized = _decode_event(data)
            event = ModelUpdateEventDTO.model_validate(normalized)
        except (ValidationError, Exception) as exc:
            LOGGER.warning(
                "FederatedAggregator: invalid event, routing to DLQ",
                extra={"message_id": message_id, "error": str(exc)},
            )
            self._publisher.publish(
                STREAM_DLQ,
                {
                    "originalMessageId": message_id,
                    "serviceName": "federated-aggregator",
                    "error": str(exc),
                    "errorType": type(exc).__name__,
                },
            )
            return

        # --- 2. Aggregate gradients ---
        try:
            aggregated = _average_gradients(event.gradientPayload)
        except ValueError as exc:
            LOGGER.warning(
                "FederatedAggregator: cannot aggregate empty gradient, routing to DLQ",
                extra={
                    "message_id": message_id,
                    "node_id": event.nodeId,
                    "error": str(exc),
                },
            )
            self._publisher.publish(
                STREAM_DLQ,
                {
                    "originalMessageId": message_id,
                    "serviceName": "federated-aggregator",
                    "error": str(exc),
                    "errorType": type(exc).__name__,
                    "nodeId": event.nodeId,
                    "correlationId": event.correlationId,
                },
            )
            return

        # --- 3. Publish aggregated state ---
        self._publisher.publish(
            STREAM_OUTPUT,
            {
                "nodeId": event.nodeId,
                "modelName": event.modelName,
                "correlationId": event.correlationId,
                "aggregatedGradient": str(aggregated),
            },
        )

        LOGGER.info(
            "FederatedAggregator: aggregated and published",
            extra={
                "node_id": event.nodeId,
                "model_name": event.modelName,
                "gradient_count": len(event.gradientPayload),
                "aggregated_gradient": aggregated,
                "correlation_id": event.correlationId,
            },
        )


# ---------------------------------------------------------------------------
# Production entry-point
# ---------------------------------------------------------------------------

def main() -> None:
    LOGGER.info("Federated Aggregator Worker starting...")

    shutdown_event = threading.Event()

    def _shutdown(signum, frame):
        LOGGER.info("Shutdown signal received (%s)", signum)
        shutdown_event.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    publisher = RedisStreamPublisher(REDIS_URL)
    consumer = RedisStreamConsumer(
        REDIS_URL,
        STREAM_INPUT,
        CONSUMER_GROUP,
        CONSUMER_NAME,
        shutdown_event=shutdown_event,
    )

    worker = FederatedAggregatorWorker(publisher=publisher)

    try:
        LOGGER.info("Worker ready — waiting for messages")
        consumer.consume(
            lambda msg_id, data: worker.handle_message(msg_id, data),
            block_ms=5000,
            count=1,
        )
    except KeyboardInterrupt:
        LOGGER.info("Interrupted by user")
    finally:
        consumer.close()
        publisher.close()
        LOGGER.info("Federated Aggregator Worker shut down")


if __name__ == "__main__":
    main()
