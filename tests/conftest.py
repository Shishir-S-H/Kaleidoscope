"""Shared pytest fixtures for kaleidoscope-ai tests."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure shared modules are importable
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    return MagicMock()


@pytest.fixture
def mock_publisher():
    """Mock RedisStreamPublisher."""
    publisher = MagicMock()
    publisher.publish.return_value = "mock-message-id"
    return publisher


@pytest.fixture
def mock_consumer():
    """Mock RedisStreamConsumer."""
    return MagicMock()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Set default env vars for tests."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("AI_PLATFORM", "huggingface")
    monkeypatch.setenv("HF_API_TOKEN", "test-token")
    monkeypatch.setenv("HF_MODERATION_API_URL", "https://test.hf.space/classify")
    monkeypatch.setenv("HF_TAGGING_API_URL", "https://test.hf.space/tag")
    monkeypatch.setenv("HF_SCENE_API_URL", "https://test.hf.space/recognize")
    monkeypatch.setenv("HF_CAPTIONING_API_URL", "https://test.hf.space/caption")
    monkeypatch.setenv("HF_FACE_API_URL", "https://test.hf.space/detect")
