"""HuggingFace face-detection provider."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, List

from shared.providers.base import BaseFaceProvider
from shared.providers.types import FaceDetectionResult, FaceResult
from shared.utils.http_client import get_http_session
from shared.utils.secrets import get_secret

logger = logging.getLogger(__name__)

EXPECTED_EMBEDDING_DIM = 1024


class HFFaceProvider(BaseFaceProvider):
    """Face detection and embedding extraction via a HuggingFace endpoint."""

    def __init__(self) -> None:
        self._api_url: str = os.getenv(
            "HF_FACE_API_URL", os.getenv("HF_API_URL", "")
        )
        self._api_token: str | None = get_secret("HF_API_TOKEN")
        self._session = get_http_session()

        if not self._api_url:
            logger.warning("HF_FACE_API_URL / HF_API_URL not configured")

    @property
    def name(self) -> str:
        return "huggingface"

    # ------------------------------------------------------------------

    def _call_api(self, image_bytes: bytes) -> Dict[str, Any]:
        """POST the image and return the raw face-detection result dict."""
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
        return response.json()

    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_embedding(embedding: List[float]) -> List[float]:
        """Pad or truncate *embedding* to :data:`EXPECTED_EMBEDDING_DIM`."""
        length = len(embedding)
        if length < EXPECTED_EMBEDDING_DIM:
            logger.warning(
                "Padding face embedding from %d to %d dims",
                length,
                EXPECTED_EMBEDDING_DIM,
            )
            return embedding + [0.0] * (EXPECTED_EMBEDDING_DIM - length)
        if length > EXPECTED_EMBEDDING_DIM:
            logger.warning(
                "Truncating face embedding from %d to %d dims",
                length,
                EXPECTED_EMBEDDING_DIM,
            )
            return embedding[:EXPECTED_EMBEDDING_DIM]
        return embedding

    # ------------------------------------------------------------------

    def detect(self, image_bytes: bytes) -> FaceDetectionResult:
        """Detect faces and return bounding-boxes + embeddings."""
        api_result = self._call_api(image_bytes)

        raw_faces: List[Dict[str, Any]] = api_result.get("faces", [])

        faces: List[FaceResult] = []
        for face in raw_faces:
            embedding = face.get("embedding", [])
            if isinstance(embedding, list):
                embedding = self._normalize_embedding(embedding)

            faces.append(
                FaceResult(
                    face_id=face.get("face_id", str(uuid.uuid4())),
                    bbox=face.get("bbox", []),
                    embedding=embedding,
                    confidence=float(face.get("confidence", 0.0)),
                )
            )

        return FaceDetectionResult(
            faces_detected=len(faces),
            faces=faces,
        )
