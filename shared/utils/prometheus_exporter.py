"""Prometheus metrics exporter for AI services.

Exposes counters and histograms on the health server's /metrics endpoint
in Prometheus text exposition format.
"""

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

_PROMETHEUS_AVAILABLE = False

try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    logger.info("prometheus_client not installed — Prometheus metrics disabled")

# Metrics (only created if prometheus_client is available)
if _PROMETHEUS_AVAILABLE:
    MESSAGES_PROCESSED = Counter(
        "ai_messages_processed_total",
        "Total messages processed",
        ["service", "status"],
    )
    PROCESSING_DURATION = Histogram(
        "ai_processing_duration_seconds",
        "Time spent processing each message",
        ["service"],
        buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120],
    )
    DLQ_MESSAGES = Counter(
        "ai_dlq_messages_total",
        "Messages sent to the dead-letter queue",
        ["service"],
    )
    RETRY_COUNT = Counter(
        "ai_retries_total",
        "Number of processing retries",
        ["service"],
    )


def observe_success(service: str, duration: float):
    if _PROMETHEUS_AVAILABLE:
        MESSAGES_PROCESSED.labels(service=service, status="success").inc()
        PROCESSING_DURATION.labels(service=service).observe(duration)


def observe_failure(service: str, duration: float):
    if _PROMETHEUS_AVAILABLE:
        MESSAGES_PROCESSED.labels(service=service, status="failure").inc()
        PROCESSING_DURATION.labels(service=service).observe(duration)


def observe_dlq(service: str):
    if _PROMETHEUS_AVAILABLE:
        DLQ_MESSAGES.labels(service=service).inc()


def observe_retry(service: str):
    if _PROMETHEUS_AVAILABLE:
        RETRY_COUNT.labels(service=service).inc()


def get_prometheus_metrics() -> Optional[bytes]:
    """Return Prometheus text format metrics, or None if unavailable."""
    if _PROMETHEUS_AVAILABLE:
        return generate_latest()
    return None
