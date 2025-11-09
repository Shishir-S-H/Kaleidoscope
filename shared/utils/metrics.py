"""
Metrics utility for AI services - tracks processing latency, success rates, and health.
"""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
from threading import Lock

logger = logging.getLogger(__name__)

# Thread-safe metrics storage
_metrics_lock = Lock()
_metrics = {
    "processing_times": [],  # List of processing times in seconds
    "success_count": 0,
    "failure_count": 0,
    "retry_count": 0,
    "dlq_count": 0,
    "last_processed_at": None,
    "last_error_at": None,
    "last_error": None
}


def record_processing_time(processing_time: float):
    """
    Record processing time for a message.
    
    Args:
        processing_time: Processing time in seconds
    """
    with _metrics_lock:
        _metrics["processing_times"].append(processing_time)
        # Keep only last 1000 processing times
        if len(_metrics["processing_times"]) > 1000:
            _metrics["processing_times"] = _metrics["processing_times"][-1000:]


def record_success():
    """Record a successful processing."""
    with _metrics_lock:
        _metrics["success_count"] += 1
        _metrics["last_processed_at"] = datetime.utcnow().isoformat() + "Z"


def record_failure(error: Optional[str] = None):
    """
    Record a failed processing.
    
    Args:
        error: Error message (optional)
    """
    with _metrics_lock:
        _metrics["failure_count"] += 1
        _metrics["last_error_at"] = datetime.utcnow().isoformat() + "Z"
        if error:
            _metrics["last_error"] = error


def record_retry():
    """Record a retry attempt."""
    with _metrics_lock:
        _metrics["retry_count"] += 1


def record_dlq():
    """Record a message sent to dead letter queue."""
    with _metrics_lock:
        _metrics["dlq_count"] += 1


def get_metrics() -> Dict[str, Any]:
    """
    Get current metrics.
    
    Returns:
        Dictionary with metrics
    """
    with _metrics_lock:
        processing_times = _metrics["processing_times"].copy()
        success_count = _metrics["success_count"]
        failure_count = _metrics["failure_count"]
        retry_count = _metrics["retry_count"]
        dlq_count = _metrics["dlq_count"]
        last_processed_at = _metrics["last_processed_at"]
        last_error_at = _metrics["last_error_at"]
        last_error = _metrics["last_error"]
    
    # Calculate statistics
    total_processed = success_count + failure_count
    success_rate = (success_count / total_processed * 100) if total_processed > 0 else 0.0
    
    # Calculate latency statistics
    if processing_times:
        avg_latency = sum(processing_times) / len(processing_times)
        min_latency = min(processing_times)
        max_latency = max(processing_times)
        # Calculate p50, p95, p99 percentiles
        sorted_times = sorted(processing_times)
        p50 = sorted_times[int(len(sorted_times) * 0.5)] if sorted_times else 0.0
        p95 = sorted_times[int(len(sorted_times) * 0.95)] if sorted_times else 0.0
        p99 = sorted_times[int(len(sorted_times) * 0.99)] if sorted_times else 0.0
    else:
        avg_latency = 0.0
        min_latency = 0.0
        max_latency = 0.0
        p50 = 0.0
        p95 = 0.0
        p99 = 0.0
    
    return {
        "total_processed": total_processed,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": round(success_rate, 2),
        "retry_count": retry_count,
        "dlq_count": dlq_count,
        "latency": {
            "avg_seconds": round(avg_latency, 3),
            "min_seconds": round(min_latency, 3),
            "max_seconds": round(max_latency, 3),
            "p50_seconds": round(p50, 3),
            "p95_seconds": round(p95, 3),
            "p99_seconds": round(p99, 3)
        },
        "last_processed_at": last_processed_at,
        "last_error_at": last_error_at,
        "last_error": last_error
    }


def reset_metrics():
    """Reset all metrics."""
    with _metrics_lock:
        _metrics["processing_times"] = []
        _metrics["success_count"] = 0
        _metrics["failure_count"] = 0
        _metrics["retry_count"] = 0
        _metrics["dlq_count"] = 0
        _metrics["last_processed_at"] = None
        _metrics["last_error_at"] = None
        _metrics["last_error"] = None


class ProcessingTimer:
    """Context manager for measuring processing time."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        processing_time = self.end_time - self.start_time
        record_processing_time(processing_time)
        return False  # Don't suppress exceptions

