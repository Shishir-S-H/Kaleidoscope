"""HuggingFace content-moderation provider."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from shared.providers.base import BaseModerationProvider
from shared.providers.types import ModerationResult
from shared.utils.http_client import get_http_session
from shared.utils.secrets import get_secret

logger = logging.getLogger(__name__)

MODERATION_LABELS = [
    "safe content",
    "appropriate content",
    "nsfw content",
    "explicit content",
    "nudity",
    "violence",
    "gore",
]

_SAFE_KEYS = {"safe content", "appropriate content"}
_UNSAFE_KEYS = {"nsfw content", "explicit content", "nudity", "violence", "gore"}

_UNSAFE_THRESHOLD = 0.15
_SAFE_THRESHOLD = 0.16


def _normalize_label(label: str) -> str:
    return label.lower().replace("_", " ").strip()


class HFModerationProvider(BaseModerationProvider):
    """Content-moderation via a HuggingFace zero-shot classification endpoint."""

    def __init__(self) -> None:
        self._api_url: str = os.getenv(
            "HF_MODERATION_API_URL", os.getenv("HF_API_URL", "")
        )
        self._api_token: str | None = get_secret("HF_API_TOKEN")
        self._session = get_http_session()

        if not self._api_url:
            logger.warning("HF_MODERATION_API_URL / HF_API_URL not configured")

    @property
    def name(self) -> str:
        return "huggingface"

    # ------------------------------------------------------------------

    def _call_api(self, image_bytes: bytes) -> Dict[str, float]:
        """POST the image and return a ``{label: score}`` mapping."""
        headers: Dict[str, str] = {}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"

        files = {
            "file": ("image.jpg", image_bytes, "image/jpeg"),
            "labels": (None, json.dumps(MODERATION_LABELS)),
        }

        timeout = getattr(self._session, "default_timeout", 60)
        response = self._session.post(
            self._api_url, headers=headers, files=files, timeout=timeout
        )
        response.raise_for_status()

        api_result: Any = response.json()

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

        unsafe_scores = [normalized.get(k, 0.0) for k in _UNSAFE_KEYS]
        safe_scores = [normalized.get(k, 0.0) for k in _SAFE_KEYS]

        has_unsafe = any(s > _UNSAFE_THRESHOLD for s in unsafe_scores)
        has_safe = any(s > _SAFE_THRESHOLD for s in safe_scores)

        max_unsafe = max(unsafe_scores) if unsafe_scores else 0.0
        max_safe = max(safe_scores) if safe_scores else 0.0
        significant_gap = (max_safe - max_unsafe) > 0.01

        is_safe = (not has_unsafe) or (has_safe and significant_gap)

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
