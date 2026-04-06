"""Unit tests for MediaPreprocessorWorker — Phase 3 TDD.

All Redis I/O and HTTP downloads are replaced with MagicMock / simple callables
so no network or filesystem side-effects occur during the test run.
"""

import os
from unittest.mock import MagicMock, call

import pytest

from services.media_preprocessor.worker import MediaPreprocessorWorker

# ---------------------------------------------------------------------------
# Shared fixtures & constants
# ---------------------------------------------------------------------------

VALID_EVENT = {
    "postId": "p1",
    "mediaId": "m42",
    "mediaUrl": "https://cdn.example.com/img.jpg",
    "correlationId": "corr-1",
}

DEFAULT_MEDIA_DIR = "/tmp/kaleidoscope_media"
EXPECTED_LOCAL_PATH = os.path.join(DEFAULT_MEDIA_DIR, "m42.jpg")


@pytest.fixture()
def publisher():
    return MagicMock()


@pytest.fixture()
def mock_downloader():
    """Returns a callable that simulates a successful download."""
    dl = MagicMock(return_value=EXPECTED_LOCAL_PATH)
    return dl


@pytest.fixture()
def worker(publisher, mock_downloader, monkeypatch):
    monkeypatch.setenv("SHARED_MEDIA_DIR", DEFAULT_MEDIA_DIR)
    return MediaPreprocessorWorker(publisher=publisher, downloader=mock_downloader)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestMediaPreprocessorWorkerHappyPath:

    def test_publishes_to_ml_inference_tasks(self, worker, publisher, mock_downloader):
        """A valid event should result in a publish to ml-inference-tasks."""
        worker.handle_message("msg-1", VALID_EVENT)

        publisher.publish.assert_called_once()
        stream = publisher.publish.call_args[0][0]
        assert stream == "ml-inference-tasks"

    def test_published_payload_contains_media_id(self, worker, publisher):
        worker.handle_message("msg-2", VALID_EVENT)

        payload = publisher.publish.call_args[0][1]
        assert payload["mediaId"] == "m42"

    def test_published_payload_contains_correlation_id(self, worker, publisher):
        worker.handle_message("msg-3", VALID_EVENT)

        payload = publisher.publish.call_args[0][1]
        assert payload["correlationId"] == "corr-1"

    def test_published_payload_contains_post_id(self, worker, publisher):
        worker.handle_message("msg-3b", VALID_EVENT)

        payload = publisher.publish.call_args[0][1]
        assert payload["postId"] == "p1"

    def test_published_payload_contains_local_file_path(self, worker, publisher):
        """The local path returned by the downloader must appear in the published event."""
        worker.handle_message("msg-4", VALID_EVENT)

        payload = publisher.publish.call_args[0][1]
        assert payload["localFilePath"] == EXPECTED_LOCAL_PATH

    def test_downloader_called_with_media_url(self, worker, mock_downloader):
        """The downloader must receive the mediaUrl from the validated event."""
        worker.handle_message("msg-5", VALID_EVENT)

        called_url = mock_downloader.call_args[0][0]
        assert called_url == "https://cdn.example.com/img.jpg"

    def test_downloader_called_with_correct_dest_path(self, worker, mock_downloader):
        """The destination path must be {SHARED_MEDIA_DIR}/{mediaId}.jpg."""
        worker.handle_message("msg-6", VALID_EVENT)

        called_dest = mock_downloader.call_args[0][1]
        assert called_dest == EXPECTED_LOCAL_PATH


# ---------------------------------------------------------------------------
# Failure routing tests
# ---------------------------------------------------------------------------

class TestMediaPreprocessorWorkerFailures:

    def test_download_failure_routes_to_dlq(self, publisher, monkeypatch):
        """When the downloader raises, the message must land in ai-processing-dlq."""
        monkeypatch.setenv("SHARED_MEDIA_DIR", DEFAULT_MEDIA_DIR)

        def failing_downloader(url, dest):
            raise ConnectionError("timeout")

        w = MediaPreprocessorWorker(publisher=publisher, downloader=failing_downloader)
        w.handle_message("msg-fail", VALID_EVENT)

        publisher.publish.assert_called_once()
        stream = publisher.publish.call_args[0][0]
        assert stream == "ai-processing-dlq"

    def test_download_failure_dlq_contains_original_message_id(self, publisher, monkeypatch):
        monkeypatch.setenv("SHARED_MEDIA_DIR", DEFAULT_MEDIA_DIR)

        def failing_downloader(url, dest):
            raise RuntimeError("DNS failure")

        w = MediaPreprocessorWorker(publisher=publisher, downloader=failing_downloader)
        w.handle_message("msg-bad", VALID_EVENT)

        payload = publisher.publish.call_args[0][1]
        assert payload.get("originalMessageId") == "msg-bad"

    def test_invalid_payload_routes_to_dlq_without_calling_downloader(
        self, publisher, mock_downloader, monkeypatch
    ):
        """Schema validation failure must short-circuit before the downloader is invoked."""
        monkeypatch.setenv("SHARED_MEDIA_DIR", DEFAULT_MEDIA_DIR)
        w = MediaPreprocessorWorker(publisher=publisher, downloader=mock_downloader)

        w.handle_message("msg-invalid", {"postId": "p1"})  # missing required fields

        mock_downloader.assert_not_called()
        publisher.publish.assert_called_once()
        stream = publisher.publish.call_args[0][0]
        assert stream == "ai-processing-dlq"

    def test_invalid_payload_dlq_contains_original_message_id(
        self, publisher, mock_downloader, monkeypatch
    ):
        monkeypatch.setenv("SHARED_MEDIA_DIR", DEFAULT_MEDIA_DIR)
        w = MediaPreprocessorWorker(publisher=publisher, downloader=mock_downloader)

        w.handle_message("msg-schema-err", {"onlyThis": "field"})

        payload = publisher.publish.call_args[0][1]
        assert payload.get("originalMessageId") == "msg-schema-err"


# ---------------------------------------------------------------------------
# Environment variable tests
# ---------------------------------------------------------------------------

class TestMediaPreprocessorWorkerEnvConfig:

    def test_shared_media_dir_env_var_controls_destination_prefix(
        self, publisher, mock_downloader, monkeypatch
    ):
        """SHARED_MEDIA_DIR must be respected as the download root."""
        custom_dir = "/data/shared_images"
        monkeypatch.setenv("SHARED_MEDIA_DIR", custom_dir)
        mock_downloader.return_value = f"{custom_dir}/m42.jpg"

        w = MediaPreprocessorWorker(publisher=publisher, downloader=mock_downloader)
        w.handle_message("msg-env", VALID_EVENT)

        called_dest = mock_downloader.call_args[0][1]
        assert called_dest.startswith(custom_dir)

    def test_default_media_dir_used_when_env_var_absent(
        self, publisher, mock_downloader, monkeypatch
    ):
        """When SHARED_MEDIA_DIR is unset the default /tmp/kaleidoscope_media is used."""
        monkeypatch.delenv("SHARED_MEDIA_DIR", raising=False)
        mock_downloader.return_value = f"/tmp/kaleidoscope_media/m42.jpg"

        w = MediaPreprocessorWorker(publisher=publisher, downloader=mock_downloader)
        w.handle_message("msg-default", VALID_EVENT)

        called_dest = mock_downloader.call_args[0][1]
        assert called_dest.startswith("/tmp/kaleidoscope_media")


# ---------------------------------------------------------------------------
# Wire-format (bytes) tests
# ---------------------------------------------------------------------------

class TestMediaPreprocessorWorkerBytesEncoding:

    def test_bytes_encoded_event_processed_correctly(
        self, publisher, mock_downloader, monkeypatch
    ):
        """Raw Redis byte dicts must be decoded before validation."""
        monkeypatch.setenv("SHARED_MEDIA_DIR", DEFAULT_MEDIA_DIR)
        byte_event = {
            k.encode(): v.encode() if isinstance(v, str) else v
            for k, v in VALID_EVENT.items()
        }

        w = MediaPreprocessorWorker(publisher=publisher, downloader=mock_downloader)
        w.handle_message("msg-bytes", byte_event)

        publisher.publish.assert_called_once()
        stream = publisher.publish.call_args[0][0]
        assert stream == "ml-inference-tasks"
