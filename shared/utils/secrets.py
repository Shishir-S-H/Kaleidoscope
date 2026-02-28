"""
Utility for loading secrets from Docker secrets files or environment variables.
Supports Docker Swarm secrets (/run/secrets/) with env var fallback.
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DOCKER_SECRETS_DIR = Path("/run/secrets")


def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Load a secret value. Checks Docker secrets first, then environment variables.

    Resolution order:
      1. /run/secrets/<name_lowercase>  (Docker Swarm / Compose secrets)
      2. os.environ[name]
      3. default

    Args:
        name: Secret name, e.g. "HF_API_TOKEN"
        default: Fallback value if not found anywhere

    Returns:
        The secret value, or *default* if not found.
    """
    secret_file = DOCKER_SECRETS_DIR / name.lower()
    if secret_file.is_file():
        try:
            value = secret_file.read_text().strip()
            if value:
                logger.debug("Loaded secret '%s' from Docker secrets file", name)
                return value
        except OSError as exc:
            logger.warning("Failed to read Docker secret file %s: %s", secret_file, exc)

    env_value = os.getenv(name)
    if env_value is not None:
        logger.debug("Loaded secret '%s' from environment variable", name)
        return env_value

    if default is not None:
        logger.debug("Using default value for secret '%s'", name)
    else:
        logger.warning("Secret '%s' not found in Docker secrets or environment", name)

    return default
