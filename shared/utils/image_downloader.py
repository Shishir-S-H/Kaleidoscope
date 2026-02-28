"""Shared image downloader with retry logic for all AI services."""

import logging
import time
from typing import Optional
from requests import Session

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_DELAY = 1.0
DEFAULT_MAX_DELAY = 30.0
DEFAULT_BACKOFF_MULTIPLIER = 2.0
DEFAULT_TIMEOUT = 30


def download_image(
    url: str,
    session: Session,
    max_retries: int = DEFAULT_MAX_RETRIES,
    timeout: int = DEFAULT_TIMEOUT,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
    correlation_id: str = "",
) -> bytes:
    """Download image bytes from a URL with retry logic.
    
    Args:
        url: Image URL to download from.
        session: requests.Session to use (from get_http_session()).
        max_retries: Maximum retry attempts.
        timeout: HTTP request timeout in seconds.
        initial_delay: Initial backoff delay.
        max_delay: Maximum backoff delay.
        backoff_multiplier: Multiplier for exponential backoff.
        correlation_id: For log tracing.
    
    Returns:
        Raw image bytes.
    
    Raises:
        requests.RequestException: If all retries are exhausted.
    """
    import requests as _requests
    
    last_exception = None
    delay = initial_delay
    
    for attempt in range(max_retries + 1):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            logger.info("Image downloaded successfully", extra={
                "url": url[:100],
                "size_bytes": len(response.content),
                "correlation_id": correlation_id,
            })
            return response.content
        except (_requests.RequestException, _requests.Timeout, ConnectionError) as exc:
            last_exception = exc
            if attempt < max_retries:
                logger.warning(
                    "Image download failed (attempt %d/%d): %s — retrying in %.2fs",
                    attempt + 1, max_retries + 1, exc, delay,
                    extra={"url": url[:100], "correlation_id": correlation_id},
                )
                time.sleep(delay)
                delay = min(delay * backoff_multiplier, max_delay)
            else:
                logger.error(
                    "Image download failed after %d attempts: %s",
                    max_retries + 1, exc,
                    extra={"url": url[:100], "correlation_id": correlation_id},
                )
    
    raise last_exception
