"""HuggingFace content-moderation provider.

Supports both HF Inference API (``api-inference.huggingface.co``)
and custom HF Spaces endpoints.  The request format is chosen
automatically based on the configured URL.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from shared.providers.base import BaseModerationProvider
from shared.providers.types import ModerationResult
from shared.utils.http_client import get_http_session
from shared.utils.hf_inference import post_image_binary
from shared.utils.secrets import get_secret

logger = logging.getLogger(__name__)

_NSFW_LABELS = {"nsfw", "unsafe", "porn", "hentai", "sexy"}
_SAFE_LABELS = {"normal", "safe", "sfw", "neutral", "drawings"}

_UNSAFE_THRESHOLD = 0.45


def _normalize_label(label: str) -> str:
    return label.lower().replace("_", " ").strip()


def _is_inference_api(url: str) -> bool:
    return "api-inference.huggingface.co" in url


class HFModerationProvider(BaseModerationProvider):
    """Content moderation via HF Inference API or a custom HF Space."""

    def __init__(self) -> None:
        self._api_url: str = os.getenv(
            "HF_MODERATION_API_URL", os.getenv("HF_API_URL", "")
        )
        self._api_token: str | None = get_secret("HF_API_TOKEN")
        self._session = get_http_session()
        self._use_inference_api = _is_inference_api(self._api_url)

        if not self._api_url:
            logger.warning("HF_MODERATION_API_URL / HF_API_URL not configured")
        else:
            mode = "Inference API" if self._use_inference_api else "HF Space"
            logger.info("Moderation provider using %s: %s", mode, self._api_url)

    @property
    def name(self) -> str:
        return "huggingface"

    # ------------------------------------------------------------------

    def _call_api(self, image_bytes: bytes) -> Dict[str, float]:
        """POST the image and return a ``{label: score}`` mapping."""
        if self._use_inference_api:
            return self._call_inference_api(image_bytes)
        return self._call_spaces_api(image_bytes)

    def _call_inference_api(self, image_bytes: bytes) -> Dict[str, float]:
        """HF Inference API: send raw bytes, get ``[{label, score}]``."""
        api_result = post_image_binary(
            self._session, self._api_url, self._api_token, image_bytes,
        )
        return self._parse_label_scores(api_result)

    def _call_spaces_api(self, image_bytes: bytes) -> Dict[str, float]:
        """Legacy HF Spaces: multipart form with ``file`` field."""
        headers: Dict[str, str] = {}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"

        files = {"file": ("image.jpg", image_bytes, "image/jpeg")}
        timeout = getattr(self._session, "default_timeout", 60)
        response = self._session.post(
            self._api_url, headers=headers, files=files, timeout=timeout,
        )
        response.raise_for_status()
        return self._parse_label_scores(response.json())

    @staticmethod
    def _parse_label_scores(api_result: Any) -> Dict[str, float]:
        if isinstance(api_result, dict) and "results" in api_result:
            api_result = api_result["results"]
        scores: Dict[str, float] = {}
        if isinstance(api_result, list):
            for item in api_result:
                if "label" in item and "score" in item:
                    scores[item["label"]] = float(item["score"])
        return scores

    # ------------------------------------------------------------------

    def analyze(self, image_bytes: bytes) -> ModerationResult:
        """Run moderation on *image_bytes* and return a :class:`ModerationResult`."""
        api_scores = self._call_api(image_bytes)

        normalized = {_normalize_label(k): v for k, v in api_scores.items()}

        nsfw_score = max(
            (normalized.get(k, 0.0) for k in _NSFW_LABELS), default=0.0,
        )
        safe_score = max(
            (normalized.get(k, 0.0) for k in _SAFE_LABELS), default=0.0,
        )

        is_safe = nsfw_score < _UNSAFE_THRESHOLD and safe_score > nsfw_score

        if api_scores:
            sorted_scores = sorted(api_scores.items(), key=lambda x: x[1], reverse=True)
            top_label = sorted_scores[0][0]
            confidence = sorted_scores[0][1]
        else:
            top_label = "unknown"
            confidence = 0.0

        return ModerationResult(
            is_safe=is_safe,
            confidence=round(confidence, 4),
            scores={k: round(v, 4) for k, v in api_scores.items()},
            top_label=top_label,
        )
