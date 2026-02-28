"""
Thread-safe circuit breaker for protecting external API calls.

States:
  CLOSED   — requests flow through normally
  OPEN     — requests are immediately rejected (fast-fail)
  HALF_OPEN — a single probe request is allowed through to test recovery
"""

import logging
import threading
import time
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the circuit is open."""


class CircuitBreaker:
    """Circuit breaker that wraps a callable and tracks failures."""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.Lock()
    
    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._last_failure_time and (time.time() - self._last_failure_time) >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("Circuit '%s' transitioned OPEN -> HALF_OPEN", self.name)
            return self._state
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute func through the circuit breaker.
        
        Raises CircuitOpenError if the circuit is open.
        """
        current_state = self.state
        
        if current_state == CircuitState.OPEN:
            raise CircuitOpenError(f"Circuit '{self.name}' is OPEN — call rejected")
        
        if current_state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitOpenError(f"Circuit '{self.name}' is HALF_OPEN — max probe calls reached")
                self._half_open_calls += 1
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise
    
    def _on_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
                logger.info("Circuit '%s' transitioned HALF_OPEN -> CLOSED", self.name)
            self._failure_count = 0
            self._success_count += 1
    
    def _on_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning("Circuit '%s' transitioned HALF_OPEN -> OPEN", self.name)
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit '%s' transitioned CLOSED -> OPEN after %d consecutive failures",
                    self.name, self._failure_count,
                )
    
    def reset(self):
        """Manually reset the circuit to CLOSED."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None
