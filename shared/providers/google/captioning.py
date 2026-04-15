"""Google Gemini 1.5 Flash image captioning provider."""

from __future__ import annotations

import logging
import os

from shared.providers.base import BaseCaptioningProvider
from shared.providers.google.base import GoogleBaseProvider
from shared.providers.types import CaptioningResult

logger = logging.getLogger(__name__)

_MODEL = os.getenv("GOOGLE_GEMINI_MODEL", "gemini-1.5-flash")
_CAPTION_PROMPT = (
    "Describe this image in one concise sentence. "
    "Focus on the main subject and key visual elements."
)


class GoogleCaptioningProvider(GoogleBaseProvider, BaseCaptioningProvider):
    """Image captioning using Gemini 1.5 Flash."""

    def __init__(self) -> None:
        self._bootstrap()
        self._model = None

    @property
    def name(self) -> str:
        return "google"

    def _get_model(self):
        if self._model is None:
            import vertexai
            from vertexai.generative_models import GenerativeModel

            vertexai.init(project=self._project, location=self._location)
            self._model = GenerativeModel(_MODEL)
        return self._model

    def caption(self, image_bytes: bytes) -> CaptioningResult:
        """Generate a one-sentence caption for the image."""
        from vertexai.generative_models import Image, Part

        model = self._get_model()
        image_part = Part.from_image(Image.from_bytes(image_bytes))
        response = model.generate_content([_CAPTION_PROMPT, image_part])

        caption = response.text.strip()
        logger.debug("Caption generated (%d chars).", len(caption))
        return CaptioningResult(caption=caption)
