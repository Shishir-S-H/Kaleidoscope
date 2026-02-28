"""Helpers for calling the HuggingFace Inference API.

Handles the differences between HF Spaces (multipart form) and the
serverless Inference API (raw bytes / JSON), including automatic retry
when the model is cold-starting (HTTP 503 with ``estimated_time``).
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any, Dict, List, Optional

from requests import Session

logger = logging.getLogger(__name__)

_MAX_COLD_START_RETRIES = 3
_DEFAULT_COLD_WAIT = 20  # seconds


def _wait_for_model(response_json: Any) -> float:
    """Return the estimated wait time from a 'model loading' response, or 0."""
    if isinstance(response_json, dict):
        return float(response_json.get("estimated_time", _DEFAULT_COLD_WAIT))
    return _DEFAULT_COLD_WAIT


def _is_model_loading(status_code: int, body: Any) -> bool:
    if status_code != 503:
        return False
    if isinstance(body, dict) and "error" in body:
        err = str(body["error"]).lower()
        return "loading" in err or "currently loading" in err
    return False


def post_image_binary(
    session: Session,
    url: str,
    token: Optional[str],
    image_bytes: bytes,
    timeout: float = 120,
) -> Any:
    """POST raw image bytes (image-classification, image-to-text).

    Used for tasks where the Inference API accepts the image as the
    request body (no JSON wrapping).
    """
    headers: Dict[str, str] = {"Content-Type": "application/octet-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(_MAX_COLD_START_RETRIES + 1):
        resp = session.post(url, headers=headers, data=image_bytes, timeout=timeout)

        if resp.status_code == 503:
            try:
                body = resp.json()
            except Exception:
                body = {}
            if _is_model_loading(resp.status_code, body) and attempt < _MAX_COLD_START_RETRIES:
                wait = min(_wait_for_model(body), 60)
                logger.warning(
                    "Model loading (attempt %d/%d), waiting %.0fs …",
                    attempt + 1, _MAX_COLD_START_RETRIES, wait,
                )
                time.sleep(wait)
                continue
        resp.raise_for_status()
        return resp.json()

    resp.raise_for_status()
    return resp.json()


def post_zero_shot_image(
    session: Session,
    url: str,
    token: Optional[str],
    image_bytes: bytes,
    candidate_labels: List[str],
    timeout: float = 120,
) -> Any:
    """POST a zero-shot image classification request.

    The Inference API expects JSON with a base64-encoded image and
    ``candidate_labels`` in ``parameters``.
    """
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "inputs": b64,
        "parameters": {"candidate_labels": candidate_labels},
    }

    for attempt in range(_MAX_COLD_START_RETRIES + 1):
        resp = session.post(url, headers=headers, json=payload, timeout=timeout)

        if resp.status_code == 503:
            try:
                body = resp.json()
            except Exception:
                body = {}
            if _is_model_loading(resp.status_code, body) and attempt < _MAX_COLD_START_RETRIES:
                wait = min(_wait_for_model(body), 60)
                logger.warning(
                    "Model loading (attempt %d/%d), waiting %.0fs …",
                    attempt + 1, _MAX_COLD_START_RETRIES, wait,
                )
                time.sleep(wait)
                continue
        resp.raise_for_status()
        return resp.json()

    resp.raise_for_status()
    return resp.json()
