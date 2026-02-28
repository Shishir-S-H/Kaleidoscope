"""Lightweight HTTP health-check server for AI services.

Starts a small HTTP server in a daemon thread that exposes:
  GET /health  — liveness probe  (returns service health JSON)
  GET /ready   — readiness probe (returns 200 when consuming)
  GET /metrics — basic metrics JSON
"""

import json
import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Callable, Dict, Any, Optional

logger = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for health/ready/metrics endpoints."""
    
    # Set at class level by start_health_server()
    health_fn: Optional[Callable[[], Dict[str, Any]]] = None
    metrics_fn: Optional[Callable[[], Dict[str, Any]]] = None
    _ready = False
    
    def do_GET(self):
        if self.path == "/health":
            self._respond_json(self._get_health(), 200)
        elif self.path == "/ready":
            status = 200 if self._ready else 503
            self._respond_json({"ready": self._ready}, status)
        elif self.path == "/metrics":
            self._respond_json(self._get_metrics(), 200)
        else:
            self._respond_json({"error": "not found"}, 404)
    
    def _get_health(self) -> Dict[str, Any]:
        if self.health_fn:
            try:
                return self.health_fn()
            except Exception as exc:
                return {"status": "error", "error": str(exc)}
        return {"status": "unknown"}
    
    def _get_metrics(self) -> Dict[str, Any]:
        if self.metrics_fn:
            try:
                return self.metrics_fn()
            except Exception:
                return {}
        return {}
    
    def _respond_json(self, body: dict, status: int):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
    
    def log_message(self, format, *args):
        # Silence default stderr logging from BaseHTTPRequestHandler
        pass


def start_health_server(
    service_name: str,
    health_fn: Optional[Callable[[], Dict[str, Any]]] = None,
    metrics_fn: Optional[Callable[[], Dict[str, Any]]] = None,
    port: Optional[int] = None,
):
    """Start the health-check HTTP server in a daemon thread.
    
    Args:
        service_name: Human-readable service name for logging.
        health_fn: Callable returning health-check dict (called on GET /health).
        metrics_fn: Callable returning metrics dict (called on GET /metrics).
        port: Port to bind (default: HEALTH_PORT env or 8080).
    """
    port = port or int(os.getenv("HEALTH_PORT", "8080"))
    
    _HealthHandler.health_fn = health_fn
    _HealthHandler.metrics_fn = metrics_fn
    
    def _serve():
        try:
            server = HTTPServer(("0.0.0.0", port), _HealthHandler)
            logger.info("Health server started for '%s' on port %d", service_name, port)
            server.serve_forever()
        except Exception as exc:
            logger.error("Health server failed: %s", exc)
    
    thread = threading.Thread(target=_serve, daemon=True, name=f"health-{service_name}")
    thread.start()
    return thread


def mark_ready():
    """Mark the service as ready (readiness probe returns 200)."""
    _HealthHandler._ready = True


def mark_not_ready():
    """Mark the service as not ready (readiness probe returns 503)."""
    _HealthHandler._ready = False
