"""HuggingFace image-captioning provider."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from shared.providers.base import BaseCaptioningProvider
from shared.providers.types import CaptioningResult
from shared.utils.http_client import get_http_session
from shared.utils.secrets import get_secret

logger = logging.getLogger(__name__)


class HFCaptioningProvider(BaseCaptioningProvider):
    """Image captioning via a HuggingFace image-to-text endpoint."""

    def __init__(self) -> None:
        self._api_url: str = os.getenv(
            "HF_CAPTIONING_API_URL", os.getenv("HF_API_URL", "")
        )
        self._api_token: str | None = get_secret("HF_API_TOKEN")
        self._session = get_http_session()

        if not self._api_url:
            logger.warning("HF_CAPTIONING_API_URL / HF_API_URL not configured")

    @property
    def name(self) -> str:
        return "huggingface"

    # ------------------------------------------------------------------

    def _call_api(self, image_bytes: bytes) -> str:
        """POST the image and return the generated caption text."""
        headers: Dict[str, str] = {}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"

        files = {
            "file": ("image.jpg", image_bytes, "image/jpeg"),
        }

        timeout = getattr(self._session, "default_timeout", 60)
        response = self._session.post(
            self._api_url, headers=headers, files=files, timeout=timeout
        )
        response.raise_for_status()

        api_result: Any = response.json()

        if isinstance(api_result, list) and len(api_result) > 0:
            caption = api_result[0].get("generated_text", "")
        elif isinstance(api_result, dict):
            caption = api_result.get("generated_text", "")
        else:
            caption = ""

        return caption

    # ------------------------------------------------------------------

    def caption(self, image_bytes: bytes) -> CaptioningResult:
        """Generate a caption for the given image bytes."""
        text = self._call_api(image_bytes)
        return CaptioningResult(caption=text)
