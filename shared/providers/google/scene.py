"""Google Gemini scene recognition provider."""

from __future__ import annotations

import json
import logging
import os
import re

from shared.providers.base import BaseSceneProvider
from shared.providers.google.base import GoogleBaseProvider
from shared.providers.types import SceneResult

logger = logging.getLogger(__name__)

_MODEL = os.getenv("GOOGLE_GEMINI_MODEL", "gemini-2.0-flash-001")

_SCENE_PROMPT = """\
Identify the primary scene or setting depicted in this image.
Respond with ONLY a JSON object in this exact format (no markdown, no explanation):
{{
  "scene": "<primary scene label>",
  "confidence": <float 0.0-1.0>,
  "scores": {{
    "<label1>": <float>,
    "<label2>": <float>
  }}
}}
The "scores" map should contain the top 3-5 candidate scene labels.
If custom labels are provided, prefer them: {labels}
"""


class GoogleSceneProvider(GoogleBaseProvider, BaseSceneProvider):
    """Scene recognition using Gemini (model controlled by GOOGLE_GEMINI_MODEL env var)."""

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

    def recognize(
        self,
        image_bytes: bytes,
        labels: list[str] | None = None,
        threshold: float = 0.005,
    ) -> SceneResult:
        """Return the best-matching scene label for the image."""
        from vertexai.generative_models import Image, Part

        model = self._get_model()
        label_hint = ", ".join(labels) if labels else "any"
        prompt = _SCENE_PROMPT.format(labels=label_hint)
        image_part = Part.from_image(Image.from_bytes(image_bytes))
        response = model.generate_content([prompt, image_part])

        raw_text = response.text.strip()
        result = self._parse_response(raw_text)
        logger.debug(
            "Scene recognition: scene=%s, confidence=%.3f",
            result.scene, result.confidence,
        )
        return result

    @staticmethod
    def _parse_response(raw: str) -> SceneResult:
        """Parse a Gemini JSON response into a :class:`SceneResult`."""
        # Strip markdown fences
        raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
        try:
            data = json.loads(raw)
            scene = str(data.get("scene", "unknown")).strip()
            confidence = float(data.get("confidence", 0.5))
            scores: dict[str, float] = {
                str(k): float(v)
                for k, v in data.get("scores", {}).items()
            }
            if scene not in scores:
                scores[scene] = confidence
            return SceneResult(
                scene=scene,
                confidence=round(confidence, 4),
                scores={k: round(v, 4) for k, v in scores.items()},
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            # Graceful fallback: treat the whole text as the scene label
            scene = raw.split("\n")[0][:100].strip() or "unknown"
            return SceneResult(
                scene=scene,
                confidence=0.5,
                scores={scene: 0.5},
            )
