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


class TestModerationInferenceProviders:
    """Test moderation provider with InferenceClient (model ID)."""

    def setup_method(self):
        clear_cache()

    def test_uses_inference_client_path(self, monkeypatch):
        monkeypatch.setenv(
            "HF_MODERATION_API_URL",
            "Falconsai/nsfw_image_detection",
        )
        provider = get_provider("moderation")
        assert provider._use_inference_first is True

    def test_uses_spaces_path(self, monkeypatch):
        monkeypatch.setenv(
            "HF_MODERATION_API_URL",
            "https://my-space.hf.space/classify",
        )
        provider = get_provider("moderation")
        assert provider._use_inference_first is False

    @patch("shared.providers.huggingface.moderation.inference_client_image_classification")
    def test_inference_client_call(self, mock_inference, monkeypatch):
        monkeypatch.setenv(
            "HF_MODERATION_API_URL",
            "Falconsai/nsfw_image_detection",
        )
        mock_inference.return_value = [
            {"label": "normal", "score": 0.95},
            {"label": "nsfw", "score": 0.05},
        ]
        provider = get_provider("moderation")
        result = provider.analyze(b"fake-image-bytes")
        assert result.is_safe is True
        assert result.top_label == "normal"
        mock_inference.assert_called_once()


class TestTaggerInferenceProviders:
    """Test tagger provider with image-classification (model ID)."""

    def setup_method(self):
        clear_cache()

    @patch("shared.providers.huggingface.tagger.inference_client_image_classification")
    def test_inference_client_call(self, mock_inference, monkeypatch):
        monkeypatch.setenv(
            "HF_TAGGER_API_URL",
            "google/vit-base-patch16-224",
        )
        mock_inference.return_value = [
            {"label": "golden retriever", "score": 0.8},
            {"label": "tennis ball", "score": 0.6},
            {"label": "grass", "score": 0.4},
        ]
        provider = get_provider("tagging")
        result = provider.tag(b"fake-image-bytes", top_n=3)
        assert "golden retriever" in result.tags
        assert len(result.tags) <= 3
        mock_inference.assert_called_once()


class TestSceneInferenceProviders:
    """Test scene provider with image-classification (model ID)."""

    def setup_method(self):
        clear_cache()

    @patch("shared.providers.huggingface.scene.inference_client_image_classification")
    def test_inference_client_call(self, mock_inference, monkeypatch):
        monkeypatch.setenv(
            "HF_SCENE_API_URL",
            "google/vit-base-patch16-224",
        )
        mock_inference.return_value = [
            {"label": "beach", "score": 0.7},
            {"label": "seashore", "score": 0.5},
        ]
        provider = get_provider("scene")
        result = provider.recognize(b"fake-image-bytes")
        assert result.scene == "beach"
        mock_inference.assert_called_once()


class TestCaptioningInferenceProviders:
    """Test captioning provider with InferenceClient (model ID)."""

    def setup_method(self):
        clear_cache()

    @patch("shared.providers.huggingface.captioning.inference_client_image_to_text")
    def test_inference_client_call(self, mock_inference, monkeypatch):
        monkeypatch.setenv(
            "HF_CAPTIONING_API_URL",
            "Salesforce/blip-image-captioning-large",
        )
        mock_inference.return_value = "a dog playing on a beach"
        provider = get_provider("captioning")
        result = provider.caption(b"fake-image-bytes")
        assert result.caption == "a dog playing on a beach"
        mock_inference.assert_called_once()
