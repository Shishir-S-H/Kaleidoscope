"""Google Cloud Vision face detection provider.

Maps Vision API face annotations to the internal
:class:`~shared.providers.types.FaceDetectionResult` contract.

Note on embeddings
------------------
The Vision API returns bounding boxes, landmarks, and headpose angles, but
does **not** return face embedding vectors.  ``FaceResult.embedding`` is left
as an empty list (allowed since the type was made optional).

Downstream services that require a face embedding vector (e.g. face_matcher)
should either:
  * Keep ``FACE_PLATFORM=huggingface`` for the identity pipeline, or
  * Pair this provider with a dedicated embedding step.
"""

from __future__ import annotations

import logging
import uuid

from shared.providers.base import BaseFaceProvider
from shared.providers.google.base import GoogleBaseProvider
from shared.providers.types import FaceDetectionResult, FaceResult

logger = logging.getLogger(__name__)


class GoogleFaceProvider(GoogleBaseProvider, BaseFaceProvider):
    """Face detection using Google Cloud Vision Face Detection."""

    def __init__(self) -> None:
        self._bootstrap()
        self._client = None

    @property
    def name(self) -> str:
        return "google"

    def _get_client(self):
        if self._client is None:
            from google.cloud import vision
            self._client = vision.ImageAnnotatorClient()
        return self._client

    def detect(self, image_bytes: bytes) -> FaceDetectionResult:
        """Detect faces and return bounding boxes + landmarks."""
        from google.cloud import vision

        client = self._get_client()
        image = vision.Image(content=image_bytes)
        response = client.face_detection(image=image)

        if response.error.message:
            raise RuntimeError(
                f"Vision Face Detection API error: {response.error.message}"
            )

        faces: list[FaceResult] = []
        for annotation in response.face_annotations:
            vertices = annotation.bounding_poly.vertices
            if vertices:
                xs = [v.x for v in vertices]
                ys = [v.y for v in vertices]
                bbox = [min(xs), min(ys), max(xs), max(ys)]
            else:
                bbox = [0, 0, 0, 0]

            confidence = round(annotation.detection_confidence, 4)

            faces.append(
                FaceResult(
                    face_id=str(uuid.uuid4()),
                    bbox=bbox,
                    confidence=confidence,
                    # Vision API does not produce face embeddings
                    embedding=[],
                )
            )

        logger.debug("Face detection: found %d face(s).", len(faces))

        return FaceDetectionResult(
            faces_detected=len(faces),
            faces=faces,
        )
