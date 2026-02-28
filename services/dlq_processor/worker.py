#!/usr/bin/env python3
"""
DLQ (Dead Letter Queue) Processor Service
Consumes failed messages from the ai-processing-dlq stream,
logs them with full context, and optionally re-publishes for retry.
"""

import json
import os
import signal
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

load_dotenv()

from shared.utils.logger import get_logger
from shared.redis_streams import RedisStreamPublisher, RedisStreamConsumer
from shared.redis_streams.utils import decode_message
from shared.utils.metrics import record_processing_time, record_success, record_failure, get_metrics
from shared.utils.health import check_health

LOGGER = get_logger("dlq-processor")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STREAM_INPUT = "ai-processing-dlq"
STREAM_RETRY = "post-image-processing"
CONSUMER_GROUP = "dlq-processor-group"
CONSUMER_NAME = "dlq-processor-worker-1"

DLQ_AUTO_RETRY = os.getenv("DLQ_AUTO_RETRY", "false").lower() in ("true", "1", "yes")

HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8080"))

_shutdown_event = threading.Event()


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            try:
                metrics = get_metrics()
                health = check_health(metrics, "dlq-processor")
                body = json.dumps(health).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def start_health_server():
    server = HTTPServer(("0.0.0.0", HEALTH_PORT), HealthHandler)
    server.timeout = 1
    LOGGER.info("Health check server started", extra={"port": HEALTH_PORT})
    while not _shutdown_event.is_set():
        server.handle_request()
    server.server_close()


def handle_message(message_id: str, data: dict, publisher: RedisStreamPublisher):
    start_time = time.time()
    decoded_data = None

    try:
        decoded_data = decode_message(data)

        service_name = decoded_data.get("service", "unknown")
        error = decoded_data.get("error", "unknown")
        error_type = decoded_data.get("errorType", "unknown")
        retry_count = decoded_data.get("retryCount", "0")
        original_message_id = decoded_data.get("originalMessageId", "unknown")
        original_data_raw = decoded_data.get("originalData", "{}")
        timestamp = decoded_data.get("timestamp", "")

        if isinstance(original_data_raw, str):
            try:
                original_data = json.loads(original_data_raw)
            except (json.JSONDecodeError, ValueError):
                original_data = {"raw": original_data_raw}
        elif isinstance(original_data_raw, dict):
            original_data = original_data_raw
        else:
            original_data = {"raw": str(original_data_raw)}

        LOGGER.error("DLQ message received", extra={
            "dlq_message_id": message_id,
            "failed_service": service_name,
            "error": error,
            "error_type": error_type,
            "retry_count": retry_count,
            "original_message_id": original_message_id,
            "original_data": original_data,
            "failure_timestamp": timestamp,
        })

        if DLQ_AUTO_RETRY:
            LOGGER.info("Auto-retry enabled, re-publishing to retry stream", extra={
                "original_message_id": original_message_id,
                "retry_stream": STREAM_RETRY,
                "failed_service": service_name,
            })

            retry_message = {}
            if isinstance(original_data, dict):
                retry_message = {k: str(v) if not isinstance(v, str) else v for k, v in original_data.items()}
            retry_message["dlqRetry"] = "true"
            retry_message["dlqOriginalService"] = service_name
            retry_message["dlqOriginalMessageId"] = str(original_message_id)

            publisher.publish(STREAM_RETRY, retry_message)
            LOGGER.info("Message re-published for retry", extra={
                "retry_stream": STREAM_RETRY,
                "original_message_id": original_message_id,
                "failed_service": service_name,
            })
        else:
            LOGGER.info("Auto-retry disabled, message logged only", extra={
                "original_message_id": original_message_id,
                "failed_service": service_name,
            })

        processing_time = time.time() - start_time
        record_processing_time(processing_time)
        record_success()

    except Exception as e:
        processing_time = time.time() - start_time
        record_processing_time(processing_time)
        record_failure(str(e))
        LOGGER.exception("Error processing DLQ message", extra={
            "error": str(e),
            "message_id": message_id,
        })


def _signal_handler(signum, frame):
    sig_name = signal.Signals(signum).name
    LOGGER.info(f"Received {sig_name}, shutting down gracefully...")
    _shutdown_event.set()


def main():
    LOGGER.info("DLQ Processor Worker starting")
    LOGGER.info("Configuration", extra={
        "redis_url": REDIS_URL,
        "input_stream": STREAM_INPUT,
        "auto_retry": DLQ_AUTO_RETRY,
        "retry_stream": STREAM_RETRY if DLQ_AUTO_RETRY else "N/A",
    })

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    try:
        publisher = RedisStreamPublisher(REDIS_URL)
        consumer = RedisStreamConsumer(
            REDIS_URL,
            STREAM_INPUT,
            CONSUMER_GROUP,
            CONSUMER_NAME
        )

        LOGGER.info("Connected to Redis Streams", extra={
            "input_stream": STREAM_INPUT,
            "consumer_group": CONSUMER_GROUP,
        })

        def message_handler(message_id: str, data: dict):
            handle_message(message_id, data, publisher)

        def health_check_loop():
            while not _shutdown_event.is_set():
                _shutdown_event.wait(300)
                if _shutdown_event.is_set():
                    break
                try:
                    metrics = get_metrics()
                    health = check_health(metrics, "dlq-processor")
                    LOGGER.info("Health check", extra={
                        "health_status": health["status"],
                        "metrics": metrics,
                        "health_checks": health["checks"],
                    })
                except Exception as e:
                    LOGGER.exception("Error in health check", extra={"error": str(e)})

        health_log_thread = threading.Thread(target=health_check_loop, daemon=True)
        health_log_thread.start()

        LOGGER.info("Worker ready - waiting for DLQ messages")

        consumer.consume(message_handler, block_ms=5000, count=1)

    except KeyboardInterrupt:
        LOGGER.warning("Interrupted by user")
    except Exception as e:
        LOGGER.exception("Unexpected error in main loop", extra={"error": str(e)})
    finally:
        _shutdown_event.set()
        LOGGER.info("Worker shutting down")


if __name__ == "__main__":
    main()
