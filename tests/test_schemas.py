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
from shared.schemas.schemas import (
    PostImageEventDTO,
    MediaAiInsightsResultDTO,
    LocalMediaEventDTO,
    ModelUpdateEventDTO,
    ProfilePictureEventDTO,
    FaceTagSuggestionDTO,
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


# ---------------------------------------------------------------------------
# PostImageEventDTO — strict contract DTO matching the Java backend
# ---------------------------------------------------------------------------

class TestPostImageEventDTO:
    """Tests for PostImageEventDTO (incoming Redis event from Java backend).

    Field mediaUrl matches Java PostImageEventDTO.mediaUrl (GAP-5 fix).
    """

    VALID = {
        "postId": "post-1",
        "mediaId": "media-42",
        "mediaUrl": "https://cdn.example.com/photo.jpg",
        "correlationId": "corr-abc-123",
    }

    def test_valid_full_payload(self):
        dto = PostImageEventDTO.model_validate(self.VALID)
        assert dto.postId == "post-1"
        assert dto.mediaId == "media-42"
        assert dto.mediaUrl == "https://cdn.example.com/photo.jpg"
        assert dto.correlationId == "corr-abc-123"

    def test_missing_post_id_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "postId"}
        with pytest.raises(ValidationError):
            PostImageEventDTO.model_validate(data)

    def test_missing_media_id_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "mediaId"}
        with pytest.raises(ValidationError):
            PostImageEventDTO.model_validate(data)

    def test_missing_media_url_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "mediaUrl"}
        with pytest.raises(ValidationError):
            PostImageEventDTO.model_validate(data)

    def test_missing_correlation_id_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "correlationId"}
        with pytest.raises(ValidationError):
            PostImageEventDTO.model_validate(data)

    def test_post_id_wrong_type_rejected(self):
        data = {**self.VALID, "postId": 999}
        with pytest.raises(ValidationError):
            PostImageEventDTO.model_validate(data)


# ---------------------------------------------------------------------------
# MediaAiInsightsResultDTO — strict contract DTO matching the Java backend
# ---------------------------------------------------------------------------

class TestMediaAiInsightsResultDTO:
    """Tests for MediaAiInsightsResultDTO (outgoing Redis event to Java backend)."""

    VALID_FULL = {
        "mediaId": "media-42",
        "correlationId": "corr-abc-123",
        "isSafe": True,
        "caption": "A dog playing in the park",
        "tags": ["dog", "park", "outdoor"],
        "scenes": ["nature", "outdoor"],
        "imageEmbedding": [0.1, 0.2, 0.3, 0.4],
    }

    VALID_MINIMAL = {
        "mediaId": "media-42",
        "correlationId": "corr-abc-123",
        "isSafe": False,
    }

    def test_valid_full_payload(self):
        dto = MediaAiInsightsResultDTO.model_validate(self.VALID_FULL)
        assert dto.mediaId == "media-42"
        assert dto.correlationId == "corr-abc-123"
        assert dto.isSafe is True
        assert dto.caption == "A dog playing in the park"
        assert dto.tags == ["dog", "park", "outdoor"]
        assert dto.scenes == ["nature", "outdoor"]
        assert dto.imageEmbedding == [0.1, 0.2, 0.3, 0.4]

    def test_valid_minimal_payload_optional_fields_default_to_none(self):
        dto = MediaAiInsightsResultDTO.model_validate(self.VALID_MINIMAL)
        assert dto.isSafe is False
        assert dto.caption is None
        assert dto.tags is None
        assert dto.scenes is None
        assert dto.imageEmbedding is None

    def test_missing_media_id_raises(self):
        data = {k: v for k, v in self.VALID_MINIMAL.items() if k != "mediaId"}
        with pytest.raises(ValidationError):
            MediaAiInsightsResultDTO.model_validate(data)

    def test_missing_correlation_id_raises(self):
        data = {k: v for k, v in self.VALID_MINIMAL.items() if k != "correlationId"}
        with pytest.raises(ValidationError):
            MediaAiInsightsResultDTO.model_validate(data)

    def test_missing_is_safe_raises(self):
        data = {k: v for k, v in self.VALID_MINIMAL.items() if k != "isSafe"}
        with pytest.raises(ValidationError):
            MediaAiInsightsResultDTO.model_validate(data)

    def test_is_safe_string_rejected_under_strict_mode(self):
        data = {**self.VALID_MINIMAL, "isSafe": "true"}
        with pytest.raises(ValidationError):
            MediaAiInsightsResultDTO.model_validate(data)

    def test_is_safe_integer_rejected_under_strict_mode(self):
        data = {**self.VALID_MINIMAL, "isSafe": 0}
        with pytest.raises(ValidationError):
            MediaAiInsightsResultDTO.model_validate(data)

    def test_is_safe_none_rejected(self):
        data = {**self.VALID_MINIMAL, "isSafe": None}
        with pytest.raises(ValidationError):
            MediaAiInsightsResultDTO.model_validate(data)

    def test_tags_empty_list_is_valid(self):
        dto = MediaAiInsightsResultDTO.model_validate({**self.VALID_MINIMAL, "tags": []})
        assert dto.tags == []

    def test_tags_wrong_inner_type_rejected(self):
        """Tags must be List[str]; a list of ints should be rejected."""
        data = {**self.VALID_MINIMAL, "tags": [1, 2, 3]}
        with pytest.raises(ValidationError):
            MediaAiInsightsResultDTO.model_validate(data)

    def test_scenes_empty_list_is_valid(self):
        dto = MediaAiInsightsResultDTO.model_validate({**self.VALID_MINIMAL, "scenes": []})
        assert dto.scenes == []

    def test_image_embedding_valid_float_list(self):
        data = {**self.VALID_MINIMAL, "imageEmbedding": [0.0, -1.5, 3.14]}
        dto = MediaAiInsightsResultDTO.model_validate(data)
        assert dto.imageEmbedding == [0.0, -1.5, 3.14]

    def test_image_embedding_list_of_strings_rejected(self):
        data = {**self.VALID_MINIMAL, "imageEmbedding": ["a", "b"]}
        with pytest.raises(ValidationError):
            MediaAiInsightsResultDTO.model_validate(data)

    def test_image_embedding_empty_list_is_valid(self):
        dto = MediaAiInsightsResultDTO.model_validate({**self.VALID_MINIMAL, "imageEmbedding": []})
        assert dto.imageEmbedding == []

    def test_media_id_wrong_type_rejected(self):
        data = {**self.VALID_MINIMAL, "mediaId": 42}
        with pytest.raises(ValidationError):
            MediaAiInsightsResultDTO.model_validate(data)


# ---------------------------------------------------------------------------
# LocalMediaEventDTO — internal pipeline event after image download
# ---------------------------------------------------------------------------

class TestLocalMediaEventDTO:
    """Tests for LocalMediaEventDTO (internal event carrying the local file path)."""

    VALID = {
        "postId": "p42",
        "mediaId": "m42",
        "localFilePath": "/tmp/kaleidoscope_media/m42.jpg",
        "correlationId": "corr-xyz-789",
    }

    def test_valid_payload_parses_cleanly(self):
        dto = LocalMediaEventDTO.model_validate(self.VALID)
        assert dto.postId == "p42"
        assert dto.mediaId == "m42"
        assert dto.localFilePath == "/tmp/kaleidoscope_media/m42.jpg"
        assert dto.correlationId == "corr-xyz-789"

    def test_missing_post_id_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "postId"}
        with pytest.raises(ValidationError):
            LocalMediaEventDTO.model_validate(data)

    def test_missing_media_id_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "mediaId"}
        with pytest.raises(ValidationError):
            LocalMediaEventDTO.model_validate(data)

    def test_missing_local_file_path_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "localFilePath"}
        with pytest.raises(ValidationError):
            LocalMediaEventDTO.model_validate(data)

    def test_missing_correlation_id_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "correlationId"}
        with pytest.raises(ValidationError):
            LocalMediaEventDTO.model_validate(data)

    def test_media_id_wrong_type_rejected(self):
        data = {**self.VALID, "mediaId": 99}
        with pytest.raises(ValidationError):
            LocalMediaEventDTO.model_validate(data)

    def test_local_file_path_wrong_type_rejected(self):
        data = {**self.VALID, "localFilePath": 42}
        with pytest.raises(ValidationError):
            LocalMediaEventDTO.model_validate(data)

    def test_correlation_id_wrong_type_rejected(self):
        data = {**self.VALID, "correlationId": ["not", "a", "string"]}
        with pytest.raises(ValidationError):
            LocalMediaEventDTO.model_validate(data)


# ---------------------------------------------------------------------------
# ModelUpdateEventDTO — federated-learning gradient update from an edge node
# ---------------------------------------------------------------------------

class TestModelUpdateEventDTO:
    """Tests for ModelUpdateEventDTO (incoming gradient update event)."""

    VALID = {
        "nodeId": "edge-node-7",
        "modelName": "resnet-v2",
        "gradientPayload": [0.1, 0.2, 0.3],
        "correlationId": "corr-fed-1",
    }

    def test_valid_payload_parses_cleanly(self):
        dto = ModelUpdateEventDTO.model_validate(self.VALID)
        assert dto.nodeId == "edge-node-7"
        assert dto.modelName == "resnet-v2"
        assert dto.gradientPayload == [0.1, 0.2, 0.3]
        assert dto.correlationId == "corr-fed-1"

    def test_single_element_gradient_payload_valid(self):
        dto = ModelUpdateEventDTO.model_validate({**self.VALID, "gradientPayload": [0.5]})
        assert dto.gradientPayload == [0.5]

    def test_empty_gradient_payload_is_valid_schema(self):
        """Empty list is structurally valid — business-level rejection is in the worker."""
        dto = ModelUpdateEventDTO.model_validate({**self.VALID, "gradientPayload": []})
        assert dto.gradientPayload == []

    def test_missing_node_id_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "nodeId"}
        with pytest.raises(ValidationError):
            ModelUpdateEventDTO.model_validate(data)

    def test_missing_model_name_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "modelName"}
        with pytest.raises(ValidationError):
            ModelUpdateEventDTO.model_validate(data)

    def test_missing_gradient_payload_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "gradientPayload"}
        with pytest.raises(ValidationError):
            ModelUpdateEventDTO.model_validate(data)

    def test_missing_correlation_id_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "correlationId"}
        with pytest.raises(ValidationError):
            ModelUpdateEventDTO.model_validate(data)

    def test_gradient_payload_list_of_strings_rejected(self):
        """Strict mode must not coerce string numerics to floats."""
        data = {**self.VALID, "gradientPayload": ["0.1", "0.2"]}
        with pytest.raises(ValidationError):
            ModelUpdateEventDTO.model_validate(data)

    def test_gradient_payload_as_plain_string_rejected(self):
        data = {**self.VALID, "gradientPayload": "[0.1, 0.2]"}
        with pytest.raises(ValidationError):
            ModelUpdateEventDTO.model_validate(data)

    def test_gradient_payload_list_of_ints_accepted(self):
        """Pydantic v2 accepts int values for float fields (int is a numeric subtype
        of float in Python's numeric tower). This is correct strict-mode behaviour."""
        dto = ModelUpdateEventDTO.model_validate({**self.VALID, "gradientPayload": [1, 2, 3]})
        assert dto.gradientPayload == [1, 2, 3]

    def test_node_id_wrong_type_rejected(self):
        data = {**self.VALID, "nodeId": 7}
        with pytest.raises(ValidationError):
            ModelUpdateEventDTO.model_validate(data)

    def test_model_name_wrong_type_rejected(self):
        data = {**self.VALID, "modelName": 42}
        with pytest.raises(ValidationError):
            ModelUpdateEventDTO.model_validate(data)


# ---------------------------------------------------------------------------
# ProfilePictureEventDTO ? profile picture enrollment event
# ---------------------------------------------------------------------------

class TestProfilePictureEventDTO:
    """Tests for ProfilePictureEventDTO (profile picture enrollment trigger).

    Matches Java ProfilePictureEventDTO exactly (GAP-4 fix):
      - username removed (Java does not publish this field)
      - profilePicUrl renamed to imageUrl
    """

    VALID = {
        "userId": "user-99",
        "imageUrl": "https://cdn.example.com/alice.jpg",
        "correlationId": "corr-enroll-1",
    }

    def test_valid_payload_parses_cleanly(self):
        dto = ProfilePictureEventDTO.model_validate(self.VALID)
        assert dto.userId == "user-99"
        assert dto.imageUrl == "https://cdn.example.com/alice.jpg"
        assert dto.correlationId == "corr-enroll-1"

    def test_missing_user_id_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "userId"}
        with pytest.raises(ValidationError):
            ProfilePictureEventDTO.model_validate(data)

    def test_missing_image_url_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "imageUrl"}
        with pytest.raises(ValidationError):
            ProfilePictureEventDTO.model_validate(data)

    def test_missing_correlation_id_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "correlationId"}
        with pytest.raises(ValidationError):
            ProfilePictureEventDTO.model_validate(data)

    def test_user_id_wrong_type_rejected(self):
        data = {**self.VALID, "userId": 99}
        with pytest.raises(ValidationError):
            ProfilePictureEventDTO.model_validate(data)

    def test_username_field_not_accepted_in_strict_mode(self):
        """Java does not send username; extra fields must not silently populate the DTO."""
        data = {**self.VALID, "username": "alice"}
        dto = ProfilePictureEventDTO.model_validate(data)
        assert not hasattr(dto, "username")


# ---------------------------------------------------------------------------
# FaceTagSuggestionDTO ? face-match result published to Java backend
# ---------------------------------------------------------------------------

class TestFaceTagSuggestionDTO:
    """Tests for FaceTagSuggestionDTO (face match event to face-recognition-results).

    Field names match Java FaceRecognitionResultDTO (GAP-1/GAP-3/GAP-7 fix):
      - matchedUserId renamed to suggestedUserId
      - confidence renamed to confidenceScore (type: float, published as float not str)
    """

    VALID = {
        "mediaId": "media-10",
        "postId": "post-5",
        "faceId": "face-uuid-abc",
        "suggestedUserId": "user-77",
        "matchedUsername": "bob",
        "confidenceScore": 0.92,
        "correlationId": "corr-match-1",
    }

    def test_valid_payload_parses_cleanly(self):
        dto = FaceTagSuggestionDTO.model_validate(self.VALID)
        assert dto.mediaId == "media-10"
        assert dto.postId == "post-5"
        assert dto.faceId == "face-uuid-abc"
        assert dto.suggestedUserId == "user-77"
        assert dto.matchedUsername == "bob"
        assert dto.confidenceScore == 0.92
        assert dto.correlationId == "corr-match-1"

    def test_confidence_score_as_int_accepted(self):
        """Pydantic coerces int to float for float fields in strict mode."""
        dto = FaceTagSuggestionDTO.model_validate({**self.VALID, "confidenceScore": 1})
        assert dto.confidenceScore == 1.0

    def test_missing_media_id_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "mediaId"}
        with pytest.raises(ValidationError):
            FaceTagSuggestionDTO.model_validate(data)

    def test_missing_confidence_score_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "confidenceScore"}
        with pytest.raises(ValidationError):
            FaceTagSuggestionDTO.model_validate(data)

    def test_confidence_score_as_string_rejected(self):
        data = {**self.VALID, "confidenceScore": "0.9"}
        with pytest.raises(ValidationError):
            FaceTagSuggestionDTO.model_validate(data)

    def test_suggested_user_id_wrong_type_rejected(self):
        data = {**self.VALID, "suggestedUserId": 77}
        with pytest.raises(ValidationError):
            FaceTagSuggestionDTO.model_validate(data)
