"""
Health check utility for AI services.
"""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Health check thresholds
MAX_TIME_SINCE_LAST_PROCESSED = timedelta(minutes=10)  # Consider unhealthy if no processing in 10 minutes
MAX_ERROR_RATE = 50.0  # Consider unhealthy if error rate > 50%
MAX_AVG_LATENCY_SECONDS = 60.0  # Consider unhealthy if avg latency > 60 seconds


def check_health(metrics: Dict[str, Any], service_name: str) -> Dict[str, Any]:
    """
    Check service health based on metrics.
    
    Args:
        metrics: Metrics dictionary from get_metrics()
        service_name: Name of the service
        
    Returns:
        Dictionary with health status
    """
    health_status = {
        "service": service_name,
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": {}
    }
    
    # Check 1: Last processed time
    if metrics.get("last_processed_at"):
        last_processed = datetime.fromisoformat(metrics["last_processed_at"].replace("Z", "+00:00"))
        time_since_last = datetime.utcnow() - last_processed.replace(tzinfo=None)
        
        if time_since_last > MAX_TIME_SINCE_LAST_PROCESSED:
            health_status["status"] = "unhealthy"
            health_status["checks"]["last_processed"] = {
                "status": "unhealthy",
                "message": f"No processing in {time_since_last.total_seconds():.0f} seconds"
            }
        else:
            health_status["checks"]["last_processed"] = {
                "status": "healthy",
                "message": f"Last processed {time_since_last.total_seconds():.0f} seconds ago"
            }
    else:
        # No processing yet - consider as starting up
        health_status["checks"]["last_processed"] = {
            "status": "starting",
            "message": "No processing recorded yet"
        }
    
    # Check 2: Success rate
    success_rate = metrics.get("success_rate", 100.0)
    if success_rate < (100.0 - MAX_ERROR_RATE):
        health_status["status"] = "unhealthy"
        health_status["checks"]["success_rate"] = {
            "status": "unhealthy",
            "message": f"Success rate {success_rate:.2f}% is below threshold"
        }
    else:
        health_status["checks"]["success_rate"] = {
            "status": "healthy",
            "message": f"Success rate {success_rate:.2f}%"
        }
    
    # Check 3: Average latency
    avg_latency = metrics.get("latency", {}).get("avg_seconds", 0.0)
    if avg_latency > MAX_AVG_LATENCY_SECONDS:
        health_status["status"] = "unhealthy"
        health_status["checks"]["latency"] = {
            "status": "unhealthy",
            "message": f"Average latency {avg_latency:.2f}s exceeds threshold"
        }
    else:
        health_status["checks"]["latency"] = {
            "status": "healthy",
            "message": f"Average latency {avg_latency:.2f}s"
        }
    
    # Check 4: DLQ count
    dlq_count = metrics.get("dlq_count", 0)
    if dlq_count > 0:
        health_status["checks"]["dlq"] = {
            "status": "warning",
            "message": f"{dlq_count} messages in dead letter queue"
        }
    else:
        health_status["checks"]["dlq"] = {
            "status": "healthy",
            "message": "No messages in dead letter queue"
        }
    
    return health_status

