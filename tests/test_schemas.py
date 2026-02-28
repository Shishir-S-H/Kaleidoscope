"""Tests for Pydantic message schemas."""

import pytest
from pydantic import ValidationError

from shared.schemas.message_schemas import (
    PostImageProcessingMessage,
    MLInsightsResultMessage,
    ESSyncEventMessage,
    validate_incoming,
    validate_outgoing,
)


class TestPostImageProcessingMessage:
    def test_valid_message(self):
        msg = validate_incoming({
            "mediaId": "123",
            "postId": "456",
            "mediaUrl": "https://example.com/img.jpg",
        }, PostImageProcessingMessage)
        assert msg.mediaId == "123"

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            validate_incoming({"mediaId": "123"}, PostImageProcessingMessage)


class TestMLInsightsResultMessage:
    def test_moderation_result(self):
        data = {
            "mediaId": "1",
            "postId": "2",
            "service": "moderation",
            "timestamp": "2025-01-01T00:00:00Z",
            "isSafe": "true",
            "moderationConfidence": "0.95",
        }
        msg = validate_incoming(data, MLInsightsResultMessage)
        assert msg.version == "1"

    def test_validate_outgoing_passes(self):
        data = {
            "mediaId": "1", "postId": "2", "service": "tagging",
            "timestamp": "2025-01-01T00:00:00Z", "tags": '["a","b"]',
        }
        assert validate_outgoing(data, MLInsightsResultMessage) == data
