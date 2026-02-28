"""Shared HTTP client with connection pooling for all AI services."""

import logging
import os
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_session = None

def get_http_session(
    pool_connections: int = 10,
    pool_maxsize: int = 10,
    max_retries: int = 0,
    backoff_factor: float = 0.3,
) -> Session:
    """Get or create a shared requests.Session with connection pooling.
    
    The session is created once (singleton) and reused across calls.
    Transport-level retries are disabled by default since workers
    handle retries at the application level.
    """
    global _session
    if _session is not None:
        return _session

    session = Session()
    
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    
    adapter = HTTPAdapter(
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
        max_retries=retry_strategy,
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    default_timeout = float(os.getenv("HTTP_DEFAULT_TIMEOUT", "60"))
    # Store default timeout on session for callers to reference
    session.default_timeout = default_timeout
    
    _session = session
    logger.info("Created shared HTTP session (pool_connections=%d, pool_maxsize=%d)", pool_connections, pool_maxsize)
    return _session


def close_http_session():
    """Close the shared HTTP session."""
    global _session
    if _session is not None:
        _session.close()
        _session = None
        logger.info("Closed shared HTTP session")
