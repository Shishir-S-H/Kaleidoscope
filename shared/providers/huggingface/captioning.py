"""HuggingFace image-captioning provider.

Uses Inference API first (model ID), falls back to HF Space URL if Inference fails.
If configured with a URL only, uses Space only.
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

DEFAULT_SPACE_URL = "https://phantomfury-kaleidoscope-image-captioning.hf.space/caption"


class HFCaptioningProvider(BaseCaptioningProvider):
    """Image captioning: Inference first, then fallback to HF Space."""

    def __init__(self) -> None:
        self._api_url: str = os.getenv(
            "HF_CAPTIONING_API_URL", os.getenv("HF_API_URL", "")
        )
        self._api_token: str | None = get_secret("HF_API_TOKEN")
        self._session = get_http_session()
        self._use_inference_first = is_model_id(self._api_url)
        self._inference_disabled = False
        self._space_fallback_url: str = os.getenv(
            "HF_CAPTIONING_SPACE_URL", DEFAULT_SPACE_URL
        )

        if not self._api_url:
            logger.warning("HF_CAPTIONING_API_URL / HF_API_URL not configured")
        else:
            mode = "Inference first (fallback Space)" if self._use_inference_first else "HF Space"
            logger.info("Captioning provider using %s: %s", mode, self._api_url)

    @property
    def name(self) -> str:
        return "huggingface"

    # ------------------------------------------------------------------

    def _call_api(self, image_bytes: bytes) -> str:
        """Try Inference first; fall back to Space only on permanent failures."""
        if self._use_inference_first and not self._inference_disabled:
            try:
                return self._call_inference_client(image_bytes)
            except StopIteration:
                logger.warning(
                    "Captioning: no Inference Provider for this model; "
                    "permanently switching to Space fallback",
                )
                self._inference_disabled = True
                return self._call_spaces_api(image_bytes, self._space_fallback_url)
            except Exception as e:
                logger.warning("Captioning Inference error, falling back to Space: %s", e)
                return self._call_spaces_api(image_bytes, self._space_fallback_url)
        if self._use_inference_first:
            return self._call_spaces_api(image_bytes, self._space_fallback_url)
        return self._call_spaces_api(image_bytes, self._api_url)

    def _call_inference_client(self, image_bytes: bytes) -> str:
        """InferenceClient (Inference Providers API)."""
        return inference_client_image_to_text(
            self._api_url, image_bytes, self._api_token,
        )

    def _call_spaces_api(self, image_bytes: bytes, url: str) -> str:
        """HF Spaces: multipart form with ``file`` field."""
        headers: Dict[str, str] = {}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"

        files = {"file": ("image.jpg", image_bytes, "image/jpeg")}
        timeout = getattr(self._session, "default_timeout", 60)
        response = self._session.post(
            url, headers=headers, files=files, timeout=timeout,
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
