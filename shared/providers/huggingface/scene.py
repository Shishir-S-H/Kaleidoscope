"""HuggingFace scene-recognition provider.

Supports both HF Inference API (``api-inference.huggingface.co``,
zero-shot-image-classification) and custom HF Spaces endpoints.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from shared.providers.base import BaseSceneProvider
from shared.providers.types import SceneResult
from shared.utils.http_client import get_http_session
from shared.utils.hf_inference import post_zero_shot_image
from shared.utils.secrets import get_secret

logger = logging.getLogger(__name__)

DEFAULT_SCENE_LABELS: List[str] = [
    "beach", "mountains", "urban", "office", "restaurant", "forest",
    "desert", "lake", "park", "indoor", "outdoor", "rural",
    "coastal", "mountainous", "tropical", "arctic",
]

_DEFAULT_THRESHOLD = 0.005


def _is_inference_api(url: str) -> bool:
    return "api-inference.huggingface.co" in url


class HFSceneProvider(BaseSceneProvider):
    """Scene recognition via HF Inference API or a custom HF Space."""

    def __init__(self) -> None:
        self._api_url: str = os.getenv(
            "HF_SCENE_API_URL", os.getenv("HF_API_URL", "")
        )
        self._api_token: str | None = get_secret("HF_API_TOKEN")
        self._session = get_http_session()
        self._use_inference_api = _is_inference_api(self._api_url)

        raw_labels = os.getenv("SCENE_LABELS", "")
        self._scene_labels: List[str] = (
            [lbl.strip() for lbl in raw_labels.split(",") if lbl.strip()]
            if raw_labels
            else list(DEFAULT_SCENE_LABELS)
        )

        if not self._api_url:
            logger.warning("HF_SCENE_API_URL / HF_API_URL not configured")
        else:
            mode = "Inference API" if self._use_inference_api else "HF Space"
            logger.info("Scene provider using %s: %s", mode, self._api_url)

    @property
    def name(self) -> str:
        return "huggingface"

    # ------------------------------------------------------------------

    def _call_api(
        self, image_bytes: bytes, candidate_labels: List[str],
    ) -> List[Dict[str, Any]]:
        """POST the image and return a list of ``{label, score}`` dicts."""
        if self._use_inference_api:
            return self._call_inference_api(image_bytes, candidate_labels)
        return self._call_spaces_api(image_bytes, candidate_labels)

    def _call_inference_api(
        self, image_bytes: bytes, candidate_labels: List[str],
    ) -> List[Dict[str, Any]]:
        """HF Inference API: zero-shot-image-classification."""
        api_result = post_zero_shot_image(
            self._session, self._api_url, self._api_token,
            image_bytes, candidate_labels,
        )
        return self._normalize_result(api_result)

    def _call_spaces_api(
        self, image_bytes: bytes, candidate_labels: List[str],
    ) -> List[Dict[str, Any]]:
        """Legacy HF Spaces: multipart form with ``file`` + ``labels``."""
        headers: Dict[str, str] = {}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"

        files = {
            "file": ("image.jpg", image_bytes, "image/jpeg"),
            "labels": (None, json.dumps(candidate_labels)),
        }
        timeout = getattr(self._session, "default_timeout", 60)
        response = self._session.post(
            self._api_url, headers=headers, files=files, timeout=timeout,
        )
        response.raise_for_status()
        return self._normalize_result(response.json())

    @staticmethod
    def _normalize_result(api_result: Any) -> List[Dict[str, Any]]:
        """Coerce any response shape into ``[{label, score}]``."""
        if isinstance(api_result, dict):
            if "results" in api_result:
                api_result = api_result["results"]
            elif "labels" in api_result and "scores" in api_result:
                labels = api_result.get("labels") or []
                scores = api_result.get("scores") or []
                api_result = [
                    {"label": lb, "score": s} for lb, s in zip(labels, scores)
                ]
            elif "scenes" in api_result and "scores" in api_result:
                scenes = api_result.get("scenes") or []
                scores = api_result.get("scores") or []
                api_result = [
                    {"label": sc, "score": s} for sc, s in zip(scenes, scores)
                ]
            else:
                converted = [
                    {"label": k, "score": v}
                    for k, v in api_result.items()
                    if isinstance(v, (int, float))
                ]
                api_result = converted or api_result
        return api_result if isinstance(api_result, list) else []

    # ------------------------------------------------------------------

    def recognize(
        self,
        image_bytes: bytes,
        labels: list[str] | None = None,
        threshold: float = 0.005,
    ) -> SceneResult:
        """Return the best-matching scene label for an image."""
        candidate_labels = labels if labels else self._scene_labels
        api_result = self._call_api(image_bytes, candidate_labels)

        scores: Dict[str, float] = {}
        if isinstance(api_result, list):
            for item in api_result:
                if "label" in item and "score" in item:
                    scores[item["label"]] = float(item["score"])

        filtered = {s: sc for s, sc in scores.items() if sc > threshold}

        if scores:
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            best_scene = sorted_scores[0][0]
            best_score = sorted_scores[0][1]
        else:
            best_scene = "unknown"
            best_score = 0.0

        if not filtered and scores:
            top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
            filtered = dict(top)
            logger.info(
                "No scenes above threshold=%.4f; returning top-3 anyway", threshold,
            )

        return SceneResult(
            scene=best_scene,
            confidence=round(best_score, 4),
            scores={k: round(v, 4) for k, v in filtered.items()},
        )
