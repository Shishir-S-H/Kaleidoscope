"""HuggingFace image-tagging provider.

Supports:
- InferenceClient (model ID) - new Inference Providers API
- HF Spaces (URL)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Tuple

from shared.providers.base import BaseTaggerProvider
from shared.providers.types import TaggingResult
from shared.utils.http_client import get_http_session
from shared.utils.hf_inference import (
    inference_client_zero_shot_image_classification,
    is_model_id,
    post_zero_shot_image,
)
from shared.utils.secrets import get_secret

logger = logging.getLogger(__name__)

IMAGE_TAGS: List[str] = [
    "person", "people", "face", "car", "vehicle", "building", "architecture",
    "tree", "nature", "sky", "water", "beach", "mountain", "forest",
    "food", "animal", "dog", "cat", "bird", "indoor", "outdoor",
    "city", "street", "road", "sunset", "sunrise", "night", "day",
]


class HFTaggerProvider(BaseTaggerProvider):
    """Image tagging via InferenceClient or HF Spaces."""

    def __init__(self) -> None:
        self._api_url: str = os.getenv(
            "HF_TAGGER_API_URL", os.getenv("HF_API_URL", "")
        )
        self._api_token: str | None = get_secret("HF_API_TOKEN")
        self._session = get_http_session()
        self._use_inference_client = is_model_id(self._api_url)

        if not self._api_url:
            logger.warning("HF_TAGGER_API_URL / HF_API_URL not configured")
        else:
            mode = "Inference Providers" if self._use_inference_client else "HF Space"
            logger.info("Tagger provider using %s: %s", mode, self._api_url)

    @property
    def name(self) -> str:
        return "huggingface"

    # ------------------------------------------------------------------

    def _call_api(self, image_bytes: bytes) -> Dict[str, float]:
        """POST the image and return a ``{tag: score}`` mapping."""
        if self._use_inference_client:
            return self._call_inference_client(image_bytes)
        return self._call_spaces_api(image_bytes)

    def _call_inference_client(self, image_bytes: bytes) -> Dict[str, float]:
        """InferenceClient (Inference Providers API)."""
        result = inference_client_zero_shot_image_classification(
            self._api_url, image_bytes, IMAGE_TAGS, self._api_token,
        )
        return {item["label"]: item["score"] for item in result}

    def _call_spaces_api(self, image_bytes: bytes) -> Dict[str, float]:
        """Legacy HF Spaces: multipart form with ``file`` + ``labels``."""
        headers: Dict[str, str] = {}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"

        files = {
            "file": ("image.jpg", image_bytes, "image/jpeg"),
            "labels": (None, json.dumps(IMAGE_TAGS)),
        }
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

    def tag(
        self,
        image_bytes: bytes,
        top_n: int = 5,
        threshold: float = 0.01,
    ) -> TaggingResult:
        """Return the top-N tags above *threshold* for an image."""
        api_scores = self._call_api(image_bytes)

        filtered: List[Tuple[str, float]] = [
            (t, s) for t, s in api_scores.items() if s > threshold
        ]
        sorted_tags = sorted(filtered, key=lambda x: x[1], reverse=True)[:top_n]

        if not sorted_tags and api_scores:
            sorted_tags = sorted(
                api_scores.items(), key=lambda x: x[1], reverse=True
            )[:top_n]
            logger.info(
                "No tags above threshold=%.4f; returning top-%d anyway", threshold, top_n
            )

        return TaggingResult(
            tags=[t for t, _ in sorted_tags],
            scores={t: round(s, 4) for t, s in sorted_tags},
        )
