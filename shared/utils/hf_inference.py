"""Helpers for calling HuggingFace inference.

Supports two backends:
1. InferenceClient (huggingface_hub) - uses the new Inference Providers API
   when *model_id* is a Hub model ID (e.g. "Falconsai/nsfw_image_detection").
2. HTTP / HF Spaces - when *url* is a full URL (e.g. "https://...hf.space/classify").
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


def is_model_id(value: str) -> bool:
    """Return True if value looks like a HuggingFace model ID (e.g. org/model)."""
    return bool(value) and "://" not in value and "/" in value


def get_inference_client(token: Optional[str] = None):
    """Return a HuggingFace InferenceClient for the new Inference Providers API."""
    try:
        from huggingface_hub import InferenceClient
        return InferenceClient(token=token or None)
    except ImportError as e:
        raise ImportError(
            "huggingface_hub is required for Inference Providers. "
            "Install with: pip install huggingface_hub>=0.25.0"
        ) from e


# ---------------------------------------------------------------------------
# InferenceClient (new Inference Providers API)
# ---------------------------------------------------------------------------


def inference_client_image_classification(
    model_id: str,
    image_bytes: bytes,
    token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Run image classification via InferenceClient. Returns [{label, score}]."""
    client = get_inference_client(token)
    result = client.image_classification(image_bytes, model=model_id)
    return [
        {"label": item.label, "score": float(item.score)}
        for item in result
    ]


def inference_client_zero_shot_image_classification(
    model_id: str,
    image_bytes: bytes,
    candidate_labels: List[str],
    token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Run zero-shot image classification via InferenceClient. Returns [{label, score}]."""
    client = get_inference_client(token)
    result = client.zero_shot_image_classification(
        image_bytes,
        candidate_labels=candidate_labels,
        model=model_id,
    )
    return [
        {"label": item.label, "score": float(item.score)}
        for item in result
    ]


def inference_client_image_to_text(
    model_id: str,
    image_bytes: bytes,
    token: Optional[str] = None,
) -> str:
    """Run image-to-text (captioning) via InferenceClient. Returns caption string."""
    client = get_inference_client(token)
    result = client.image_to_text(image_bytes, model=model_id)
    if hasattr(result, "generated_text"):
        return result.generated_text or ""
    return str(result) if result else ""


# ---------------------------------------------------------------------------
# Legacy HTTP (HF Spaces / deprecated api-inference.huggingface.co)
# ---------------------------------------------------------------------------


def _wait_for_model(response_json: Any) -> float:
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
    """POST raw image bytes (image-classification, image-to-text). Used for HF Spaces."""
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
    """POST zero-shot image classification. Used for HF Spaces."""
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
