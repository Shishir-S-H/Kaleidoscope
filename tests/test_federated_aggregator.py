"""Unit tests for FederatedAggregatorWorker — Phase 4 TDD.

All Redis I/O is replaced with a MagicMock publisher so no network or
real Redis connection is needed during the test run.
"""

import json
import math
from unittest.mock import MagicMock

import pytest

from services.federated_aggregator.worker import FederatedAggregatorWorker

# ---------------------------------------------------------------------------
# Shared fixtures & constants
# ---------------------------------------------------------------------------

VALID_EVENT = {
    "nodeId": "edge-node-7",
    "modelName": "resnet-v2",
    "gradientPayload": [0.1, 0.2, 0.3],
    "correlationId": "corr-fed-1",
}

EXPECTED_MEAN = sum([0.1, 0.2, 0.3]) / 3  # ≈ 0.2


@pytest.fixture()
def publisher():
    return MagicMock()


@pytest.fixture()
def worker(publisher):
    return FederatedAggregatorWorker(publisher=publisher)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestFederatedAggregatorWorkerHappyPath:

    def test_publishes_to_global_model_state(self, worker, publisher):
        """A valid event must result in a publish to global-model-state."""
        worker.handle_message("msg-1", VALID_EVENT)

        publisher.publish.assert_called_once()
        stream = publisher.publish.call_args[0][0]
        assert stream == "global-model-state"

    def test_published_payload_contains_node_id(self, worker, publisher):
        worker.handle_message("msg-2", VALID_EVENT)

        payload = publisher.publish.call_args[0][1]
        assert payload["nodeId"] == "edge-node-7"

    def test_published_payload_contains_model_name(self, worker, publisher):
        worker.handle_message("msg-3", VALID_EVENT)

        payload = publisher.publish.call_args[0][1]
        assert payload["modelName"] == "resnet-v2"

    def test_published_payload_contains_correlation_id(self, worker, publisher):
        worker.handle_message("msg-4", VALID_EVENT)

        payload = publisher.publish.call_args[0][1]
        assert payload["correlationId"] == "corr-fed-1"

    def test_aggregated_gradient_is_mean_of_payload(self, worker, publisher):
        """aggregatedGradient must equal the arithmetic mean of gradientPayload."""
        worker.handle_message("msg-5", VALID_EVENT)

        payload = publisher.publish.call_args[0][1]
        assert math.isclose(float(payload["aggregatedGradient"]), EXPECTED_MEAN, rel_tol=1e-9)

    def test_single_element_payload_mean_equals_value(self, publisher):
        """Mean of a single-element list equals that element."""
        event = {**VALID_EVENT, "gradientPayload": [0.75]}
        w = FederatedAggregatorWorker(publisher=publisher)
        w.handle_message("msg-6", event)

        payload = publisher.publish.call_args[0][1]
        assert math.isclose(float(payload["aggregatedGradient"]), 0.75, rel_tol=1e-9)

    def test_negative_gradients_averaged_correctly(self, publisher):
        event = {**VALID_EVENT, "gradientPayload": [-1.0, -0.5, 0.0, 0.5, 1.0]}
        w = FederatedAggregatorWorker(publisher=publisher)
        w.handle_message("msg-7", event)

        payload = publisher.publish.call_args[0][1]
        assert math.isclose(float(payload["aggregatedGradient"]), 0.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# Failure routing tests
# ---------------------------------------------------------------------------

class TestFederatedAggregatorWorkerFailures:

    def test_missing_required_field_routes_to_dlq(self, publisher):
        """A payload missing a required field must land in ai-processing-dlq."""
        w = FederatedAggregatorWorker(publisher=publisher)
        w.handle_message("msg-bad", {"nodeId": "n1"})  # missing modelName, gradientPayload, correlationId

        publisher.publish.assert_called_once()
        stream = publisher.publish.call_args[0][0]
        assert stream == "ai-processing-dlq"

    def test_dlq_payload_contains_original_message_id(self, publisher):
        w = FederatedAggregatorWorker(publisher=publisher)
        w.handle_message("msg-schema-err", {"nodeId": "n1"})

        payload = publisher.publish.call_args[0][1]
        assert payload.get("originalMessageId") == "msg-schema-err"

    def test_empty_gradient_payload_routes_to_dlq(self, publisher):
        """An empty gradientPayload passes schema validation but must be rejected
        at aggregation time (cannot compute mean of empty sequence)."""
        event = {**VALID_EVENT, "gradientPayload": []}
        w = FederatedAggregatorWorker(publisher=publisher)
        w.handle_message("msg-empty", event)

        publisher.publish.assert_called_once()
        stream = publisher.publish.call_args[0][0]
        assert stream == "ai-processing-dlq"

    def test_empty_gradient_dlq_contains_original_message_id(self, publisher):
        event = {**VALID_EVENT, "gradientPayload": []}
        w = FederatedAggregatorWorker(publisher=publisher)
        w.handle_message("msg-empty-id", event)

        payload = publisher.publish.call_args[0][1]
        assert payload.get("originalMessageId") == "msg-empty-id"


# ---------------------------------------------------------------------------
# Wire-format (bytes + JSON-string gradientPayload) tests
# ---------------------------------------------------------------------------

class TestFederatedAggregatorWorkerBytesEncoding:

    def test_bytes_encoded_event_with_json_string_gradient_processed_correctly(
        self, publisher
    ):
        """Redis stores list values as JSON strings on the wire; the worker must
        json.loads the gradientPayload field before Pydantic validation."""
        byte_event = {
            b"nodeId": b"edge-node-7",
            b"modelName": b"resnet-v2",
            b"gradientPayload": json.dumps([0.1, 0.2, 0.3]).encode(),
            b"correlationId": b"corr-fed-1",
        }
        w = FederatedAggregatorWorker(publisher=publisher)
        w.handle_message("msg-bytes", byte_event)

        publisher.publish.assert_called_once()
        stream = publisher.publish.call_args[0][0]
        assert stream == "global-model-state"

    def test_bytes_event_aggregated_gradient_is_correct(self, publisher):
        byte_event = {
            b"nodeId": b"edge-node-7",
            b"modelName": b"resnet-v2",
            b"gradientPayload": json.dumps([0.1, 0.2, 0.3]).encode(),
            b"correlationId": b"corr-fed-1",
        }
        w = FederatedAggregatorWorker(publisher=publisher)
        w.handle_message("msg-bytes-agg", byte_event)

        payload = publisher.publish.call_args[0][1]
        assert math.isclose(float(payload["aggregatedGradient"]), EXPECTED_MEAN, rel_tol=1e-9)
