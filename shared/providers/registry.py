"""Provider registry — maps (task, platform) to concrete provider classes."""

import logging
import os
from typing import Any, Dict, Optional, Tuple, Type

from shared.providers.base import (
    BaseCaptioningProvider,
    BaseFaceProvider,
    BaseModerationProvider,
    BaseSceneProvider,
    BaseTaggerProvider,
)

logger = logging.getLogger(__name__)

# Task name constants
TASK_MODERATION = "moderation"
TASK_TAGGING = "tagging"
TASK_SCENE = "scene"
TASK_CAPTIONING = "captioning"
TASK_FACE = "face"

# Maps (task, platform) -> provider class
_REGISTRY: Dict[Tuple[str, str], Type] = {}

# Cache of instantiated providers
_INSTANCES: Dict[Tuple[str, str], Any] = {}


def register(task: str, platform: str, provider_cls: Type) -> None:
    """Register a provider class for a (task, platform) pair."""
    key = (task.lower(), platform.lower())
    _REGISTRY[key] = provider_cls
    logger.debug(
        "Registered provider %s for task=%s, platform=%s",
        provider_cls.__name__,
        task,
        platform,
    )


def get_provider(task: str, platform: str = None, **kwargs: Any) -> Any:
    """Get a provider instance for the given task and platform.

    Platform resolution order:
      1. Explicit *platform* argument
      2. ``{TASK}_PLATFORM`` env var (e.g. ``MODERATION_PLATFORM``)
      3. ``AI_PLATFORM`` env var
      4. ``"huggingface"`` (default)

    Provider instances are cached (singleton per task+platform).
    """
    if platform is None:
        env_key = f"{task.upper()}_PLATFORM"
        platform = os.getenv(env_key, os.getenv("AI_PLATFORM", "huggingface"))

    platform = platform.lower()
    key = (task.lower(), platform)

    if key in _INSTANCES:
        return _INSTANCES[key]

    provider_cls = _REGISTRY.get(key)
    if provider_cls is None:
        available = [f"{t}:{p}" for t, p in _REGISTRY.keys()]
        raise ValueError(
            f"No provider registered for task='{task}', platform='{platform}'. "
            f"Available: {available}"
        )

    instance = provider_cls(**kwargs)
    _INSTANCES[key] = instance
    logger.info(
        "Created provider %s for task=%s, platform=%s",
        provider_cls.__name__,
        task,
        platform,
    )
    return instance


def clear_cache() -> None:
    """Clear the provider instance cache (mainly for testing)."""
    _INSTANCES.clear()


# ---------------------------------------------------------------------------
# Public alias so callers can ``from shared.providers import ProviderRegistry``
# ---------------------------------------------------------------------------
class ProviderRegistry:
    """Convenience namespace that exposes registry functions as class methods."""

    register = staticmethod(register)
    get_provider = staticmethod(get_provider)
    clear_cache = staticmethod(clear_cache)


# ---------------------------------------------------------------------------
# Auto-register built-in HuggingFace providers
# ---------------------------------------------------------------------------

def _register_defaults() -> None:
    """Auto-register built-in providers."""
    try:
        from shared.providers.huggingface.moderation import HFModerationProvider
        from shared.providers.huggingface.tagger import HFTaggerProvider
        from shared.providers.huggingface.scene import HFSceneProvider
        from shared.providers.huggingface.captioning import HFCaptioningProvider
        from shared.providers.huggingface.face import HFFaceProvider

        register(TASK_MODERATION, "huggingface", HFModerationProvider)
        register(TASK_TAGGING, "huggingface", HFTaggerProvider)
        register(TASK_SCENE, "huggingface", HFSceneProvider)
        register(TASK_CAPTIONING, "huggingface", HFCaptioningProvider)
        register(TASK_FACE, "huggingface", HFFaceProvider)
    except ImportError as e:
        logger.warning("Failed to register default HuggingFace providers: %s", e)


_register_defaults()
