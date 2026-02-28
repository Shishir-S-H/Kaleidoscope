"""HuggingFace image-captioning provider.

Supports:
- InferenceClient (model ID) - new Inference Providers API
- HF Spaces (URL)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from shared.providers.base import BaseCaptioningProvider
from shared.providers.types import CaptioningResult
from shared.utils.http_client import get_http_session
from shared.utils.hf_inference import (
    inference_client_image_to_text,
    is_model_id,
    post_image_binary,
)
from shared.utils.secrets import get_secret

logger = logging.getLogger(__name__)


class HFCaptioningProvider(BaseCaptioningProvider):
    """Image captioning via InferenceClient or HF Spaces."""

    def __init__(self) -> None:
        self._api_url: str = os.getenv(
            "HF_CAPTIONING_API_URL", os.getenv("HF_API_URL", "")
        )
        self._api_token: str | None = get_secret("HF_API_TOKEN")
        self._session = get_http_session()
        self._use_inference_client = is_model_id(self._api_url)

        if not self._api_url:
            logger.warning("HF_CAPTIONING_API_URL / HF_API_URL not configured")
        else:
            mode = "Inference Providers" if self._use_inference_client else "HF Space"
            logger.info("Captioning provider using %s: %s", mode, self._api_url)

    @property
    def name(self) -> str:
        return "huggingface"

    # ------------------------------------------------------------------

    def _call_api(self, image_bytes: bytes) -> str:
        """POST the image and return the generated caption text."""
        if self._use_inference_client:
            return self._call_inference_client(image_bytes)
        return self._call_spaces_api(image_bytes)

    def _call_inference_client(self, image_bytes: bytes) -> str:
        """InferenceClient (Inference Providers API)."""
        return inference_client_image_to_text(
            self._api_url, image_bytes, self._api_token,
        )

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
