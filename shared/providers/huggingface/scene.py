"""HuggingFace scene-recognition provider.

Uses image-classification via Inference API (model generates its own labels).
Falls back to HF Space on permanent failure.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from shared.providers.base import BaseSceneProvider
from shared.providers.types import SceneResult
from shared.utils.http_client import get_http_session
from shared.utils.hf_inference import (
    inference_client_image_classification,
    is_model_id,
    post_image_binary,
)
from shared.utils.secrets import get_secret

logger = logging.getLogger(__name__)

DEFAULT_SPACE_URL = "https://phantomfury-kaleidoscope-scene-recognition.hf.space/recognize"


class HFSceneProvider(BaseSceneProvider):
    """Scene recognition via Inference API (image-classification)."""

    def __init__(self) -> None:
        self._api_url: str = os.getenv(
            "HF_SCENE_API_URL", os.getenv("HF_API_URL", "")
        )
        self._api_token: str | None = get_secret("HF_API_TOKEN")
        self._session = get_http_session()
        self._use_inference_first = is_model_id(self._api_url)
        self._inference_disabled = False
        self._space_fallback_url: str = os.getenv(
            "HF_SCENE_SPACE_URL", DEFAULT_SPACE_URL
        )

        if not self._api_url:
            logger.warning("HF_SCENE_API_URL / HF_API_URL not configured")
        else:
            mode = "Inference" if self._use_inference_first else "HF Space"
            logger.info("Scene provider using %s: %s", mode, self._api_url)

    @property
    def name(self) -> str:
        return "huggingface"

    # ------------------------------------------------------------------

    def _call_api(self, image_bytes: bytes) -> Dict[str, float]:
        """Try Inference first; fall back to Space only on permanent failures."""
        if self._use_inference_first and not self._inference_disabled:
            try:
                return self._call_inference_client(image_bytes)
            except StopIteration:
                logger.warning(
                    "Scene: no Inference Provider for this model; "
                    "permanently switching to Space fallback",
                )
                self._inference_disabled = True
                return self._call_spaces_api(image_bytes, self._space_fallback_url)
            except Exception as e:
                logger.warning("Scene Inference error, falling back to Space: %s", e)
                return self._call_spaces_api(image_bytes, self._space_fallback_url)
        if self._use_inference_first:
            return self._call_spaces_api(image_bytes, self._space_fallback_url)
        return self._call_spaces_api(image_bytes, self._api_url)

    def _call_inference_client(self, image_bytes: bytes) -> Dict[str, float]:
        """image-classification via InferenceClient -- model picks its own labels."""
        result = inference_client_image_classification(
            self._api_url, image_bytes, self._api_token,
        )
        return {item["label"]: item["score"] for item in result}

    def _call_spaces_api(self, image_bytes: bytes, url: str) -> Dict[str, float]:
        """HF Spaces fallback."""
        headers: Dict[str, str] = {}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"

        files = {"file": ("image.jpg", image_bytes, "image/jpeg")}
        timeout = getattr(self._session, "default_timeout", 60)
        response = self._session.post(
            url, headers=headers, files=files, timeout=timeout,
        )
        response.raise_for_status()
        return self._parse_response(response.json())

    @staticmethod
    def _parse_response(api_result: Any) -> Dict[str, float]:
        """Parse any response shape into {label: score}."""
        if isinstance(api_result, dict):
            scores_dict = api_result.get("scores")
            if isinstance(scores_dict, dict) and scores_dict:
                return {k: float(v) for k, v in scores_dict.items()
                        if isinstance(v, (int, float))}
            if "results" in api_result:
                api_result = api_result["results"]
        scores: Dict[str, float] = {}
        if isinstance(api_result, list):
            for item in api_result:
                if "label" in item and "score" in item:
                    scores[item["label"]] = float(item["score"])
        return scores

    # ------------------------------------------------------------------

    def recognize(
        self,
        image_bytes: bytes,
        labels: list[str] | None = None,
        threshold: float = 0.05,
        top_n: int = 5,
    ) -> SceneResult:
        """Return the top-N scene labels for an image."""
        scores = self._call_api(image_bytes)

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        if sorted_scores:
            best_scene = sorted_scores[0][0]
            best_score = sorted_scores[0][1]
        else:
            best_scene = "unknown"
            best_score = 0.0

        top_scores = {k: v for k, v in sorted_scores[:top_n] if v >= threshold}
        if not top_scores and sorted_scores:
            top_scores = dict(sorted_scores[:3])

        return SceneResult(
            scene=best_scene,
            confidence=round(best_score, 4),
            scores={k: round(v, 4) for k, v in top_scores.items()},
        )
