"""HuggingFace image-captioning provider.

Supports both HF Inference API (``api-inference.huggingface.co``,
image-to-text pipeline) and custom HF Spaces endpoints.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from shared.providers.base import BaseCaptioningProvider
from shared.providers.types import CaptioningResult
from shared.utils.http_client import get_http_session
from shared.utils.hf_inference import post_image_binary
from shared.utils.secrets import get_secret

logger = logging.getLogger(__name__)


def _is_inference_api(url: str) -> bool:
    return "api-inference.huggingface.co" in url


class HFCaptioningProvider(BaseCaptioningProvider):
    """Image captioning via HF Inference API or a custom HF Space."""

    def __init__(self) -> None:
        self._api_url: str = os.getenv(
            "HF_CAPTIONING_API_URL", os.getenv("HF_API_URL", "")
        )
        self._api_token: str | None = get_secret("HF_API_TOKEN")
        self._session = get_http_session()
        self._use_inference_api = _is_inference_api(self._api_url)

        if not self._api_url:
            logger.warning("HF_CAPTIONING_API_URL / HF_API_URL not configured")
        else:
            mode = "Inference API" if self._use_inference_api else "HF Space"
            logger.info("Captioning provider using %s: %s", mode, self._api_url)

    @property
    def name(self) -> str:
        return "huggingface"

    # ------------------------------------------------------------------

    def _call_api(self, image_bytes: bytes) -> str:
        """POST the image and return the generated caption text."""
        if self._use_inference_api:
            return self._call_inference_api(image_bytes)
        return self._call_spaces_api(image_bytes)

    def _call_inference_api(self, image_bytes: bytes) -> str:
        """HF Inference API: send raw bytes, get ``[{generated_text}]``."""
        api_result = post_image_binary(
            self._session, self._api_url, self._api_token, image_bytes,
        )
        return self._extract_caption(api_result)

    def _call_spaces_api(self, image_bytes: bytes) -> str:
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
        return self._extract_caption(response.json())

    @staticmethod
    def _extract_caption(api_result: Any) -> str:
        if isinstance(api_result, list) and len(api_result) > 0:
            return api_result[0].get("generated_text", "")
        if isinstance(api_result, dict):
            return api_result.get("generated_text", "")
        return ""

    # ------------------------------------------------------------------

    def caption(self, image_bytes: bytes) -> CaptioningResult:
        """Generate a caption for the given image bytes."""
        text = self._call_api(image_bytes)
        return CaptioningResult(caption=text)
