"""Unit tests for face_matcher worker."""

import json
from unittest.mock import MagicMock, patch

import pytest
from pytest import approx

from services.face_matcher.worker import handle_message


VALID_EVENT = {
    "mediaId": "101",
    "postId": "55",
    "facesDetected": "2",
    "faces": json.dumps([
        {"faceId": "face-a", "embedding": [0.1] * 1024, "confidence": 0.97},
        {"faceId": "face-b", "embedding": [0.2] * 1024, "confidence": 0.88},
    ]),
    "correlationId": "corr-match-1",
    "timestamp": "2026-01-01T00:00:00Z",
    "version": "1",
}


def _make_es_hit(score=0.92, user_id=77, username="bob"):
    return {
        "_score": score,
        "_source": {"user_id": user_id, "username": username, "is_active": True},
    }


def _make_es_response(hits):
    return {"hits": {"hits": hits}}


@pytest.fixture()
def publisher():
    return MagicMock()


@pytest.fixture()
def es_client():
    client = MagicMock()
    client.search.return_value = _make_es_response([_make_es_hit(score=0.92)])
    return client


class TestFaceMatcherHappyPath:

    def test_publishes_to_face_recognition_results(self, publisher, es_client):
        """Output stream is face-recognition-results (Java FaceRecognitionConsumer)."""
        handle_message("msg-1", VALID_EVENT, publisher, es_client)

        assert publisher.publish.call_count >= 1
        for call in publisher.publish.call_args_list:
            assert call[0][0] == "face-recognition-results"

    def test_published_payload_contains_media_id(self, publisher, es_client):
        handle_message("msg-2", VALID_EVENT, publisher, es_client)

        payload = publisher.publish.call_args_list[0][0][1]
        assert payload["mediaId"] == "101"

    def test_published_payload_contains_suggested_user_id(self, publisher, es_client):
        """Field is suggestedUserId to match Java FaceRecognitionResultDTO."""
        handle_message("msg-3", VALID_EVENT, publisher, es_client)

        payload = publisher.publish.call_args_list[0][0][1]
        assert payload["suggestedUserId"] == "77"

    def test_published_payload_contains_matched_username(self, publisher, es_client):
        handle_message("msg-4", VALID_EVENT, publisher, es_client)

        payload = publisher.publish.call_args_list[0][0][1]
        assert payload["matchedUsername"] == "bob"

    def test_published_payload_contains_face_id(self, publisher, es_client):
        handle_message("msg-5", VALID_EVENT, publisher, es_client)

        payload = publisher.publish.call_args_list[0][0][1]
        assert payload["faceId"] == "face-a"

    def test_published_payload_confidence_score_is_float(self, publisher, es_client):
        """confidenceScore must be float, not str (GAP-7 fix)."""
        handle_message("msg-conf", VALID_EVENT, publisher, es_client)

        payload = publisher.publish.call_args_list[0][0][1]
        assert isinstance(payload["confidenceScore"], float)
        assert payload["confidenceScore"] == pytest.approx(0.92)

    def test_two_faces_produce_two_suggestions(self, publisher, es_client):
        handle_message("msg-6", VALID_EVENT, publisher, es_client)

        assert publisher.publish.call_count == 2


class TestFaceMatcherThreshold:

    def test_score_above_threshold_publishes(self, publisher):
        """Score 0.90 >= default 0.85 should publish."""
        es = MagicMock()
        es.search.return_value = _make_es_response([_make_es_hit(score=0.90)])

        with patch.dict("os.environ", {"KNN_CONFIDENCE_THRESHOLD": "0.85"}):
            handle_message("msg-above", VALID_EVENT, publisher, es)

        assert publisher.publish.call_count >= 1

    def test_score_below_threshold_does_not_publish(self, publisher):
        """Score 0.80 < threshold 0.85 should NOT publish."""
        es = MagicMock()
        es.search.return_value = _make_es_response([_make_es_hit(score=0.80)])

        with patch.dict("os.environ", {"KNN_CONFIDENCE_THRESHOLD": "0.85"}):
            handle_message("msg-below", VALID_EVENT, publisher, es)

        publisher.publish.assert_not_called()

    def test_no_es_hits_does_not_publish(self, publisher):
        es = MagicMock()
        es.search.return_value = _make_es_response([])

        handle_message("msg-no-hit", VALID_EVENT, publisher, es)

        publisher.publish.assert_not_called()

    def test_custom_threshold_via_env(self, publisher):
        """A threshold of 0.95 should block a hit at 0.92."""
        es = MagicMock()
        es.search.return_value = _make_es_response([_make_es_hit(score=0.92)])

        with patch.dict("os.environ", {"KNN_CONFIDENCE_THRESHOLD": "0.95"}):
            handle_message("msg-custom-thresh", VALID_EVENT, publisher, es)

        publisher.publish.assert_not_called()


class TestFaceMatcherNoFaces:

    def test_zero_faces_detected_skips_processing(self, publisher, es_client):
        event = {**VALID_EVENT, "facesDetected": "0", "faces": "[]"}
        handle_message("msg-zero", event, publisher, es_client)

        publisher.publish.assert_not_called()
        es_client.search.assert_not_called()

    def test_empty_faces_list_skips_processing(self, publisher, es_client):
        event = {**VALID_EVENT, "facesDetected": "0", "faces": "[]"}
        handle_message("msg-empty", event, publisher, es_client)

        publisher.publish.assert_not_called()


class TestFaceMatcherFailures:

    def test_es_error_routes_to_dlq(self, publisher):
        es = MagicMock()
        es.search.side_effect = RuntimeError("ES connection refused")

        handle_message("msg-es-fail", VALID_EVENT, publisher, es)

        assert publisher.publish.call_count >= 1
        assert publisher.publish.call_args[0][0] == "ai-processing-dlq"

    def test_bytes_encoded_event_handled(self, publisher, es_client):
        byte_event = {
            k.encode(): (v.encode() if isinstance(v, str) else v)
            for k, v in VALID_EVENT.items()
        }
        handle_message("msg-bytes", byte_event, publisher, es_client)

        assert publisher.publish.call_count >= 1
        assert publisher.publish.call_args_list[0][0][0] == "face-recognition-results"
