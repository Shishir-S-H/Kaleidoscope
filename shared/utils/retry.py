"""
Retry utility for AI workers with exponential backoff and dead letter queue support.
"""

import time
import logging
from typing import Callable, Any, Optional, Dict
from functools import wraps

logger = logging.getLogger(__name__)

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_DELAY = 1.0  # seconds
DEFAULT_MAX_DELAY = 30.0  # seconds
DEFAULT_BACKOFF_MULTIPLIER = 2.0


def retry_with_backoff(
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
    retryable_exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay in seconds between retries
        backoff_multiplier: Multiplier for exponential backoff
        retryable_exceptions: Tuple of exceptions that should trigger retry
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {str(e)}. "
                            f"Retrying in {delay:.2f} seconds...",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "max_retries": max_retries + 1,
                                "delay": delay,
                                "error": str(e)
                            }
                        )
                        time.sleep(delay)
                        delay = min(delay * backoff_multiplier, max_delay)
                    else:
                        logger.error(
                            f"All {max_retries + 1} attempts failed for {func.__name__}: {str(e)}",
                            extra={
                                "function": func.__name__,
                                "attempts": max_retries + 1,
                                "error": str(e)
                            }
                        )
            
            # All retries exhausted, raise the last exception
            raise last_exception
        
        return wrapper
    return decorator


def publish_to_dlq(
    publisher,
    dlq_stream: str,
    original_message_id: str,
    original_data: Dict[str, Any],
    error: Exception,
    service_name: str,
    retry_count: int
):
    """
    Publish a failed message to the dead letter queue.
    
    Args:
        publisher: RedisStreamPublisher instance
        dlq_stream: Name of the dead letter queue stream
        original_message_id: Original Redis Stream message ID
        original_data: Original message data
        error: Exception that caused the failure
        service_name: Name of the service that failed
        retry_count: Number of retry attempts made
    """
    try:
        dlq_message = {
            "originalMessageId": original_message_id,
            "originalData": original_data,
            "service": service_name,
            "error": str(error),
            "errorType": type(error).__name__,
            "retryCount": str(retry_count),
            "timestamp": time.time()
        }
        
        publisher.publish(dlq_stream, dlq_message)
        
        logger.error(
            f"Published message to dead letter queue: {dlq_stream}",
            extra={
                "dlq_stream": dlq_stream,
                "original_message_id": original_message_id,
                "service": service_name,
                "retry_count": retry_count,
                "error": str(error)
            }
        )
    except Exception as dlq_error:
        logger.exception(
            f"Failed to publish to dead letter queue: {dlq_error}",
            extra={
                "dlq_stream": dlq_stream,
                "original_message_id": original_message_id,
                "dlq_error": str(dlq_error)
            }
        )

