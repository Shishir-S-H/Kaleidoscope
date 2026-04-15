"""Google Gemini image tagging provider."""

from __future__ import annotations

import json
import logging
import os
import re

from shared.providers.base import BaseTaggerProvider
from shared.providers.google.base import GoogleBaseProvider
from shared.providers.types import TaggingResult

logger = logging.getLogger(__name__)

_MODEL = os.getenv("GOOGLE_GEMINI_MODEL", "gemini-2.0-flash-001")
_TAG_PROMPT = (
    "Analyse this image and return the {top_n} most relevant descriptive tags "
    "as a JSON array of lowercase strings. "
    "Example: [\"beach\", \"sunset\", \"people\", \"summer\"]. "
    "Respond with ONLY the JSON array, no explanation."
)


class GoogleTaggerProvider(GoogleBaseProvider, BaseTaggerProvider):
    """Image tagging using Gemini (model controlled by GOOGLE_GEMINI_MODEL env var)."""

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

    def tag(
        self,
        image_bytes: bytes,
        top_n: int = 5,
        threshold: float = 0.01,
    ) -> TaggingResult:
        """Return the top-N tags for the image.

        Gemini does not return per-tag confidence scores; scores are assigned
        by rank (1.0 / rank) so downstream ranking stays consistent.
        """
        from vertexai.generative_models import Image, Part

        model = self._get_model()
        prompt = _TAG_PROMPT.format(top_n=top_n)
        image_part = Part.from_image(Image.from_bytes(image_bytes))
        response = model.generate_content([prompt, image_part])

        raw_text = response.text.strip()
        tags = self._parse_tags(raw_text, top_n)

        # Rank-based scores: tag[0] → 1.0, tag[1] → 0.5, tag[2] → 0.33, …
        scores = {tag: round(1.0 / (idx + 1), 4) for idx, tag in enumerate(tags)}

        logger.debug("Tagging returned %d tags.", len(tags))
        return TaggingResult(tags=tags, scores=scores)

    @staticmethod
    def _parse_tags(raw: str, top_n: int) -> list[str]:
        """Extract a list of strings from a Gemini JSON response."""
        # Strip markdown fences if present
        raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(t).lower().strip() for t in parsed[:top_n] if str(t).strip()]
        except json.JSONDecodeError:
            pass

        # Fallback: split by comma / newline
        items = re.split(r"[,\n]+", raw)
        return [
            re.sub(r'["\'\[\]]', "", item).lower().strip()
            for item in items
            if item.strip()
        ][:top_n]
