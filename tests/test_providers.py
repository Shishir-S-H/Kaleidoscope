"""Tests for provider abstraction layer."""

import pytest
from unittest.mock import patch, MagicMock
from shared.providers.registry import get_provider, clear_cache, _REGISTRY
from shared.providers.types import ModerationResult, TaggingResult


class TestProviderRegistry:
    def setup_method(self):
        clear_cache()

    def test_get_provider_returns_hf_by_default(self):
        provider = get_provider("moderation")
        assert provider.name == "huggingface"

    def test_get_provider_caches_instances(self):
        p1 = get_provider("moderation")
        p2 = get_provider("moderation")
        assert p1 is p2

    def test_unknown_platform_raises(self):
        with pytest.raises(ValueError, match="No provider registered"):
            get_provider("moderation", platform="nonexistent")

    def test_env_var_platform_override(self, monkeypatch):
        monkeypatch.setenv("MODERATION_PLATFORM", "huggingface")
        provider = get_provider("moderation")
        assert provider.name == "huggingface"
