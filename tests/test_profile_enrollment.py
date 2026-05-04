"""Unit tests for profile_enrollment worker."""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.profile_enrollment.worker import handle_message


VALID_EVENT = {
    "userId": "42",
    "imageUrl": "https://cdn.example.com/alice.jpg",
    "correlationId": "corr-enroll-1",
}


def _make_face(embedding=None, confidence=0.95):
    face = MagicMock()
    face.confidence = confidence
    face.embedding = embedding or [0.1] * 1408
    face.face_id = "face-uuid-1"
    return face


def _make_result(faces=None):
    r = MagicMock()
    r.faces = faces if faces is not None else [_make_face()]
    r.faces_detected = len(r.faces)
    return r


@pytest.fixture()
def publisher():
    return MagicMock()


@pytest.fixture()
def mock_provider():
    provider = MagicMock()
    provider.detect.return_value = _make_result()
    return provider


@pytest.fixture()
def mock_image_bytes():
    return b"fakeimagebytes"


class TestProfileEnrollmentHappyPath:

    def test_publishes_to_face_embedding_results(self, publisher, mock_provider, mock_image_bytes):
        """Output stream is user-profile-face-embedding-results (Java consumer, GAP-2 fix)."""
        with patch("services.profile_enrollment.worker.get_provider", return_value=mock_provider), \
             patch("services.profile_enrollment.worker.download_image", return_value=mock_image_bytes), \
             patch("services.profile_enrollment.worker.get_http_session", return_value=MagicMock()):
            handle_message("msg-1", VALID_EVENT, publisher)

        publisher.publish.assert_called_once()
        assert publisher.publish.call_args[0][0] == "user-profile-face-embedding-results"

    def test_payload_contains_user_id(self, publisher, mock_provider, mock_image_bytes):
        with patch("services.profile_enrollment.worker.get_provider", return_value=mock_provider), \
             patch("services.profile_enrollment.worker.download_image", return_value=mock_image_bytes), \
             patch("services.profile_enrollment.worker.get_http_session", return_value=MagicMock()):
            handle_message("msg-2", VALID_EVENT, publisher)

        payload = publisher.publish.call_args[0][1]
        assert payload["userId"] == "42"

    def test_payload_contains_face_embedding(self, publisher, mock_provider, mock_image_bytes):
        with patch("services.profile_enrollment.worker.get_provider", return_value=mock_provider), \
             patch("services.profile_enrollment.worker.download_image", return_value=mock_image_bytes), \
             patch("services.profile_enrollment.worker.get_http_session", return_value=MagicMock()):
            handle_message("msg-3", VALID_EVENT, publisher)

        payload = publisher.publish.call_args[0][1]
        embedding = json.loads(payload["faceEmbedding"])
        assert len(embedding) == 1408

    def test_payload_contains_correlation_id(self, publisher, mock_provider, mock_image_bytes):
        with patch("services.profile_enrollment.worker.get_provider", return_value=mock_provider), \
             patch("services.profile_enrollment.worker.download_image", return_value=mock_image_bytes), \
             patch("services.profile_enrollment.worker.get_http_session", return_value=MagicMock()):
            handle_message("msg-4", VALID_EVENT, publisher)

        assert publisher.publish.call_args[0][1]["correlationId"] == "corr-enroll-1"

    def test_selects_highest_confidence_face(self, publisher, mock_image_bytes):
        low = _make_face(embedding=[0.2] * 1408, confidence=0.6)
        high = _make_face(embedding=[0.9] * 1408, confidence=0.98)
        provider = MagicMock()
        provider.detect.return_value = _make_result(faces=[low, high])

        with patch("services.profile_enrollment.worker.get_provider", return_value=provider), \
             patch("services.profile_enrollment.worker.download_image", return_value=mock_image_bytes), \
             patch("services.profile_enrollment.worker.get_http_session", return_value=MagicMock()):
            handle_message("msg-5", VALID_EVENT, publisher)

        embedding = json.loads(publisher.publish.call_args[0][1]["faceEmbedding"])
        assert embedding[0] == pytest.approx(0.9)


class TestProfileEnrollmentNoFace:

    def test_no_faces_does_not_publish(self, publisher, mock_image_bytes):
        """When provider finds no faces, skip enrollment silently."""
        provider = MagicMock()
        provider.detect.return_value = _make_result(faces=[])

        with patch("services.profile_enrollment.worker.get_provider", return_value=provider), \
             patch("services.profile_enrollment.worker.download_image", return_value=mock_image_bytes), \
             patch("services.profile_enrollment.worker.get_http_session", return_value=MagicMock()):
            handle_message("msg-no-face", VALID_EVENT, publisher)

        publisher.publish.assert_not_called()


class TestProfileEnrollmentFailures:

    def test_download_failure_routes_to_dlq(self, publisher):
        with patch("services.profile_enrollment.worker.download_image",
                   side_effect=ConnectionError("timeout")), \
             patch("services.profile_enrollment.worker.get_http_session", return_value=MagicMock()):
            handle_message("msg-fail", VALID_EVENT, publisher)

        publisher.publish.assert_called_once()
        assert publisher.publish.call_args[0][0] == "ai-processing-dlq"

    def test_invalid_payload_routes_to_dlq(self, publisher):
        with patch("services.profile_enrollment.worker.download_image", return_value=b"bytes"), \
             patch("services.profile_enrollment.worker.get_http_session", return_value=MagicMock()):
            handle_message("msg-bad", {"userId": "x"}, publisher)

        publisher.publish.assert_called_once()
        assert publisher.publish.call_args[0][0] == "ai-processing-dlq"

    def test_bytes_encoded_event_handled(self, publisher, mock_provider, mock_image_bytes):
        byte_event = {k.encode(): v.encode() for k, v in VALID_EVENT.items()}

        with patch("services.profile_enrollment.worker.get_provider", return_value=mock_provider), \
             patch("services.profile_enrollment.worker.download_image", return_value=mock_image_bytes), \
             patch("services.profile_enrollment.worker.get_http_session", return_value=MagicMock()):
            handle_message("msg-bytes", byte_event, publisher)

        publisher.publish.assert_called_once()
        assert publisher.publish.call_args[0][0] == "user-profile-face-embedding-results"
