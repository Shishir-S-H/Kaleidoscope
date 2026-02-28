"""
URL validation utility for SSRF prevention.
Validates image URLs before downloading to prevent server-side request forgery.
"""

import ipaddress
import logging
import os
import socket
from typing import Set
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_ALLOWED_DOMAINS: Set[str] = set()
_SSRF_CHECK_ENABLED = True


def _load_config():
    global _ALLOWED_DOMAINS, _SSRF_CHECK_ENABLED
    raw = os.getenv("ALLOWED_IMAGE_DOMAINS", "res.cloudinary.com,res-console.cloudinary.com")
    _ALLOWED_DOMAINS = {d.strip().lower() for d in raw.split(",") if d.strip()}
    _SSRF_CHECK_ENABLED = os.getenv("SSRF_CHECK_ENABLED", "true").lower() in ("true", "1", "yes")


_load_config()


def _is_private_ip(hostname: str) -> bool:
    """Return True if *hostname* resolves to a private / loopback / link-local address."""
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        return True  # cannot resolve — treat as unsafe

    for _family, _type, _proto, _canonname, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            return True
    return False


class URLValidationError(Exception):
    """Raised when a URL fails validation."""


def validate_url(url: str) -> str:
    """
    Validate that *url* is safe to fetch.

    Checks:
      - Must be http or https scheme
      - Hostname must not resolve to a private/loopback/link-local IP
      - If ALLOWED_IMAGE_DOMAINS is configured, hostname must be in the allow-list

    Args:
        url: The URL to validate.

    Returns:
        The validated URL (unchanged).

    Raises:
        URLValidationError: If the URL fails any check.
    """
    if not url or not url.strip():
        raise URLValidationError("URL is empty")

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise URLValidationError(f"Invalid scheme '{parsed.scheme}' — only http/https allowed")

    hostname = parsed.hostname
    if not hostname:
        raise URLValidationError("URL has no hostname")

    hostname_lower = hostname.lower()

    if _SSRF_CHECK_ENABLED and _is_private_ip(hostname_lower):
        raise URLValidationError(f"Hostname '{hostname}' resolves to a private/reserved IP address")

    if _ALLOWED_DOMAINS and hostname_lower not in _ALLOWED_DOMAINS:
        raise URLValidationError(
            f"Hostname '{hostname}' is not in the allowed domains list: {_ALLOWED_DOMAINS}"
        )

    return url
