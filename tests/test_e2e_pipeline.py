"""End-to-End integration tests for the Kaleidoscope AI pipeline.

These tests connect to a LIVE Redis instance and verify the real event flow
across the distributed Docker microservices (consent_gateway,
media_preprocessor, federated_aggregator).

Prerequisites
-------------
- Docker Compose stack is running:
    docker compose up consent_gateway media_preprocessor federated_aggregator redis

Run command
-----------
    pytest tests/test_e2e_pipeline.py -v -m integration

If Redis requires a password (full Docker stack with REDIS_PASSWORD):
    REDIS_URL="redis://:yourpassword@localhost:6379" pytest tests/test_e2e_pipeline.py -v -m integration

These tests are intentionally excluded from the standard unit-test run.
They will be SKIPPED automatically if Redis is not reachable.
"""

import json
import math
import os
import time
import uuid
from typing import Dict, Optional

import pytest
import redis

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Public placeholder image that always returns a JPEG — used so the
# media_preprocessor HTTP downloader succeeds rather than routing to DLQ.
PUBLIC_IMAGE_URL = "https://httpbin.org/image/jpeg"


def _get_stream_tip(r: redis.Redis, stream: str) -> str:
    """Return the last message ID currently in *stream*, or '0-0' if empty.

    Used as a watermark so each test only reads messages published after it
    starts, preventing cross-test noise.
    """
    try:
        info = r.xinfo_stream(stream)
        last_id = info.get("last-generated-id") or info.get("last-entry", [None])[0]
        if last_id:
            return last_id.decode("utf-8") if isinstance(last_id, bytes) else last_id
    except redis.exceptions.ResponseError:
        pass  # stream does not exist yet
    return "0-0"


def poll_stream(
    r: redis.Redis,
    stream: str,
    after_id: str,
    correlation_id: str,
    timeout: float = 8.0,
) -> Optional[Dict[str, str]]:
    """Poll *stream* for a message whose ``correlationId`` matches *correlation_id*.

    Reads messages added strictly after *after_id*, blocking in 500 ms
    increments until *timeout* seconds elapse.

    Returns the decoded field dict if found, or ``None`` on timeout.
    """
    deadline = time.monotonic() + timeout
    last_seen_id = after_id

    while time.monotonic() < deadline:
        remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
        block_ms = min(500, remaining_ms)

        try:
            results = r.xread({stream: last_seen_id}, count=50, block=block_ms)
        except redis.exceptions.ResponseError:
            time.sleep(0.2)
            continue

        if not results:
            continue

        for _stream_name, entries in results:
            for msg_id, fields in entries:
                raw_id = msg_id.decode("utf-8") if isinstance(msg_id, bytes) else msg_id
                last_seen_id = raw_id

                decoded = {
                    (k.decode("utf-8") if isinstance(k, bytes) else k): (
                        v.decode("utf-8") if isinstance(v, bytes) else v
                    )
                    for k, v in fields.items()
                }

                if decoded.get("correlationId") == correlation_id:
                    return decoded

    return None


# ---------------------------------------------------------------------------
# Session-scoped Redis fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def redis_client():
    """Connect to the live Redis instance, or skip the entire session if unavailable."""
    r = redis.from_url(REDIS_URL, decode_responses=False, socket_connect_timeout=3)
    try:
        r.ping()
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as exc:
        pytest.skip(
            f"Redis not reachable at {REDIS_URL} — start the Docker stack first. ({exc})"
        )
    yield r
    r.close()


# ---------------------------------------------------------------------------
# Integration test suite
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestE2EPipeline:
    """Live end-to-end tests that exercise the full Docker microservice pipeline."""

    # ------------------------------------------------------------------
    # Test 1 — Privacy Enforcement (hasConsent = false)
    # ------------------------------------------------------------------

    def test_privacy_enforcement_no_consent(self, redis_client):
        """An event with hasConsent=false must arrive on privacy-audit-queue.

        Flow: post-image-processing → consent_gateway → privacy-audit-queue
        """
        corr_id = f"e2e-privacy-{uuid.uuid4().hex[:8]}"
        output_stream = "privacy-audit-queue"

        # Record the stream tip BEFORE publishing so we only read new messages
        watermark = _get_stream_tip(redis_client, output_stream)

        redis_client.xadd(
            "post-image-processing",
            {
                "postId": "e2e-post-privacy",
                "mediaId": f"e2e-media-{corr_id}",
                "imageUrl": PUBLIC_IMAGE_URL,
                "correlationId": corr_id,
                "hasConsent": "false",
            },
        )

        result = poll_stream(
            redis_client,
            output_stream,
            watermark,
            corr_id,
            timeout=8.0,
        )

        assert result is not None, (
            f"Timed out waiting for correlationId={corr_id!r} on {output_stream!r}. "
            "Is the consent_gateway container running?"
        )
        assert result.get("correlationId") == corr_id

    # ------------------------------------------------------------------
    # Test 2 — Media Preprocessor Flow (hasConsent = true)
    # ------------------------------------------------------------------

    def test_media_preprocessor_flow_with_consent(self, redis_client):
        """An event with hasConsent=true must ultimately appear on ml-inference-tasks
        with a non-empty localFilePath.

        Flow:
          post-image-processing
            → consent_gateway  (ml-processing-queue)
            → media_preprocessor (downloads image)
            → ml-inference-tasks
        """
        corr_id = f"e2e-preprocess-{uuid.uuid4().hex[:8]}"
        media_id = f"e2e-m-{corr_id}"
        output_stream = "ml-inference-tasks"

        watermark = _get_stream_tip(redis_client, output_stream)

        redis_client.xadd(
            "post-image-processing",
            {
                "postId": "e2e-post-preprocess",
                "mediaId": media_id,
                "imageUrl": PUBLIC_IMAGE_URL,
                "correlationId": corr_id,
                "hasConsent": "true",
            },
        )

        # Allow extra time for two hops + HTTP image download
        result = poll_stream(
            redis_client,
            output_stream,
            watermark,
            corr_id,
            timeout=15.0,
        )

        assert result is not None, (
            f"Timed out waiting for correlationId={corr_id!r} on {output_stream!r}. "
            "Is the media_preprocessor container running and able to reach the internet?"
        )
        assert result.get("correlationId") == corr_id
        assert result.get("mediaId") == media_id

        local_path = result.get("localFilePath", "")
        assert local_path, (
            "localFilePath is empty — the media_preprocessor did not record the download path."
        )
        assert media_id in local_path, (
            f"Expected mediaId {media_id!r} to appear in localFilePath {local_path!r}."
        )

    # ------------------------------------------------------------------
    # Test 3 — Federated Aggregator (gradient averaging)
    # ------------------------------------------------------------------

    def test_federated_aggregator_gradient_averaging(self, redis_client):
        """A ModelUpdateEventDTO payload must produce the correct arithmetic mean
        on global-model-state.

        Flow: federated-gradient-updates → federated_aggregator → global-model-state
        """
        corr_id = f"e2e-federated-{uuid.uuid4().hex[:8]}"
        gradients = [0.2, 0.4, 0.6]
        expected_mean = sum(gradients) / len(gradients)  # 0.4
        output_stream = "global-model-state"

        watermark = _get_stream_tip(redis_client, output_stream)

        # gradientPayload must be JSON-encoded on the wire; the worker's
        # _decode_event calls json.loads before passing to Pydantic.
        redis_client.xadd(
            "federated-gradient-updates",
            {
                "nodeId": "e2e-node-1",
                "modelName": "e2e-resnet",
                "gradientPayload": json.dumps(gradients),
                "correlationId": corr_id,
            },
        )

        result = poll_stream(
            redis_client,
            output_stream,
            watermark,
            corr_id,
            timeout=8.0,
        )

        assert result is not None, (
            f"Timed out waiting for correlationId={corr_id!r} on {output_stream!r}. "
            "Is the federated_aggregator container running?"
        )
        assert result.get("correlationId") == corr_id
        assert result.get("nodeId") == "e2e-node-1"

        raw_agg = result.get("aggregatedGradient")
        assert raw_agg is not None, "aggregatedGradient field missing from published event."

        actual_mean = float(raw_agg)
        assert math.isclose(actual_mean, expected_mean, rel_tol=1e-6), (
            f"Expected aggregatedGradient ≈ {expected_mean}, got {actual_mean}."
        )
