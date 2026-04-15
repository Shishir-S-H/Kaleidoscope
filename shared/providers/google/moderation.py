"""Google Cloud Vision Safe Search moderation provider.

Maps Vision API Safe Search likelihood levels to the internal
:class:`~shared.providers.types.ModerationResult` contract.
"""

from __future__ import annotations

import logging
import os

from shared.providers.base import BaseModerationProvider
from shared.providers.google.base import GoogleBaseProvider
from shared.providers.types import ModerationResult

logger = logging.getLogger(__name__)

# Vision API likelihood enum values (integers 0-5)
# UNKNOWN=0, VERY_UNLIKELY=1, UNLIKELY=2, POSSIBLE=3, LIKELY=4, VERY_LIKELY=5
_LIKELIHOOD_SCORE: dict[int, float] = {
    0: 0.0,   # UNKNOWN
    1: 0.05,  # VERY_UNLIKELY
    2: 0.2,   # UNLIKELY
    3: 0.5,   # POSSIBLE
    4: 0.8,   # LIKELY
    5: 0.95,  # VERY_LIKELY
}

# Threshold above which a category triggers is_safe=False
_UNSAFE_THRESHOLD = float(os.getenv("GOOGLE_MODERATION_THRESHOLD", "0.5"))

# Categories that indicate unsafe content
_UNSAFE_CATEGORIES = {"adult", "violence", "racy"}


class GoogleModerationProvider(GoogleBaseProvider, BaseModerationProvider):
    """Content moderation using Google Cloud Vision Safe Search Detection."""

    def __init__(self) -> None:
        self._bootstrap()
        self._client = None  # lazy-init to avoid import cost at module load

    @property
    def name(self) -> str:
        return "google"

    def _get_client(self):
        if self._client is None:
            from google.cloud import vision
            self._client = vision.ImageAnnotatorClient()
        return self._client

    def analyze(self, image_bytes: bytes) -> ModerationResult:
        """Run Safe Search detection and return a :class:`ModerationResult`."""
        from google.cloud import vision

        client = self._get_client()
        image = vision.Image(content=image_bytes)
        response = client.safe_search_detection(image=image)

        if response.error.message:
            raise RuntimeError(
                f"Vision Safe Search API error: {response.error.message}"
            )

        safe = response.safe_search_annotation

        scores: dict[str, float] = {
            "adult":    _LIKELIHOOD_SCORE.get(safe.adult, 0.0),
            "violence": _LIKELIHOOD_SCORE.get(safe.violence, 0.0),
            "racy":     _LIKELIHOOD_SCORE.get(safe.racy, 0.0),
            "spoof":    _LIKELIHOOD_SCORE.get(safe.spoof, 0.0),
            "medical":  _LIKELIHOOD_SCORE.get(safe.medical, 0.0),
        }

        top_label = max(scores, key=lambda k: scores[k])
        confidence = scores[top_label]

        is_safe = all(
            scores[cat] < _UNSAFE_THRESHOLD for cat in _UNSAFE_CATEGORIES
        )

        logger.debug(
            "Moderation result: is_safe=%s, top=%s (%.3f)",
            is_safe, top_label, confidence,
        )

        return ModerationResult(
            is_safe=is_safe,
            confidence=round(confidence, 4),
            scores={k: round(v, 4) for k, v in scores.items()},
            top_label=top_label,
        )
