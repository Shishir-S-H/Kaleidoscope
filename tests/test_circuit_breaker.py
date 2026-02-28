"""Tests for circuit breaker."""

import time
import pytest
from shared.utils.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(self._failing_fn)
        assert cb.state == CircuitState.OPEN

    def test_open_rejects_calls(self):
        cb = CircuitBreaker("test", failure_threshold=1)
        with pytest.raises(ValueError):
            cb.call(self._failing_fn)
        with pytest.raises(CircuitOpenError):
            cb.call(self._succeeding_fn)

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        with pytest.raises(ValueError):
            cb.call(self._failing_fn)
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_closes_after_half_open_success(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        with pytest.raises(ValueError):
            cb.call(self._failing_fn)
        time.sleep(0.15)
        result = cb.call(self._succeeding_fn)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    def test_reset(self):
        cb = CircuitBreaker("test", failure_threshold=1)
        with pytest.raises(ValueError):
            cb.call(self._failing_fn)
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    @staticmethod
    def _failing_fn():
        raise ValueError("boom")

    @staticmethod
    def _succeeding_fn():
        return "ok"
