"""Google Cloud Vision face detection + Vertex AI face embedding provider.

Detection pipeline
------------------
1. Cloud Vision Face Detection  — detects face bounding boxes and confidence.
2. Vertex AI Multimodal Embedding — for each detected face the bounding-box
   crop is embedded with ``multimodalembedding@001`` (1408 dims), the same
   model used by the image-embedding service.  This guarantees that face
   vectors live in the same embedding space as post images, enabling
   cross-index KNN similarity searches.

If the embedding step fails for a face (transient API error, invalid crop,
etc.) a zero-vector of the expected dimensionality is returned so that the
downstream NOT-NULL constraint on ``media_detected_faces.embedding`` is always
satisfied and a warning is logged.
"""

from __future__ import annotations

import io
import logging
import os
import uuid
from typing import List

from shared.providers.base import BaseFaceProvider
from shared.providers.google.base import GoogleBaseProvider
from shared.providers.types import FaceDetectionResult, FaceResult

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = os.getenv("GOOGLE_EMBEDDING_MODEL", "multimodalembedding@001")
_EMBEDDING_DIMS  = int(os.getenv("FACE_EMBEDDING_DIM", "1408"))
# Minimum crop size (pixels) — crops smaller than this are too blurry to embed.
_MIN_CROP_PX = int(os.getenv("FACE_MIN_CROP_PX", "20"))


class GoogleFaceProvider(GoogleBaseProvider, BaseFaceProvider):
    """Face detection (Cloud Vision) + face embedding (Vertex AI)."""

    def __init__(self) -> None:
        self._bootstrap()
        self._vision_client = None
        self._embedding_model = None

    @property
    def name(self) -> str:
        return "google"

    # ------------------------------------------------------------------
    # Lazy-init helpers
    # ------------------------------------------------------------------

    def _get_vision_client(self):
        if self._vision_client is None:
            from google.cloud import vision
            self._vision_client = vision.ImageAnnotatorClient()
        return self._vision_client

    def _get_embedding_model(self):
        if self._embedding_model is None:
            import vertexai
            from vertexai.vision_models import MultiModalEmbeddingModel
            vertexai.init(project=self._project, location=self._location)
            self._embedding_model = MultiModalEmbeddingModel.from_pretrained(
                _EMBEDDING_MODEL
            )
            logger.info(
                "Vertex AI embedding model loaded for face crops: %s "
                "(project=%s, location=%s)",
                _EMBEDDING_MODEL, self._project, self._location,
            )
        return self._embedding_model

    # ------------------------------------------------------------------
    # Embedding helper
    # ------------------------------------------------------------------

    def _embed_face_crop(self, image_bytes: bytes, bbox: List[int]) -> List[float]:
        """Crop *bbox* from *image_bytes* and return a Vertex AI embedding.

        Returns a zero-vector on any failure so the caller always gets a
        valid fixed-length vector.
        """
        try:
            from PIL import Image as PILImage
            from vertexai.vision_models import Image as VertexImage

            img = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
            x0, y0, x1, y1 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])

            # Clamp to image bounds
            w, h = img.size
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(w, x1), min(h, y1)

            if (x1 - x0) < _MIN_CROP_PX or (y1 - y0) < _MIN_CROP_PX:
                logger.warning(
                    "Face crop too small (%dx%d px) — using zero-vector.",
                    x1 - x0, y1 - y0,
                )
                return [0.0] * _EMBEDDING_DIMS

            crop = img.crop((x0, y0, x1, y1))
            buf = io.BytesIO()
            crop.save(buf, format="JPEG", quality=90)
            crop_bytes = buf.getvalue()

            model = self._get_embedding_model()
            vertex_img = VertexImage(image_bytes=crop_bytes)
            result = model.get_embeddings(image=vertex_img)
            vector = result.image_embedding

            if len(vector) != _EMBEDDING_DIMS:
                logger.warning(
                    "Unexpected embedding dims %d (expected %d); padding/truncating.",
                    len(vector), _EMBEDDING_DIMS,
                )
                if len(vector) < _EMBEDDING_DIMS:
                    vector = vector + [0.0] * (_EMBEDDING_DIMS - len(vector))
                else:
                    vector = vector[:_EMBEDDING_DIMS]

            return vector

        except Exception as exc:
            logger.warning(
                "Face embedding failed (bbox=%s): %s — using zero-vector.",
                bbox, exc,
            )
            return [0.0] * _EMBEDDING_DIMS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, image_bytes: bytes) -> FaceDetectionResult:
        """Detect faces with Cloud Vision, then embed each crop via Vertex AI."""
        from google.cloud import vision

        client = self._get_vision_client()
        image  = vision.Image(content=image_bytes)
        response = client.face_detection(image=image)

        if response.error.message:
            raise RuntimeError(
                f"Vision Face Detection API error: {response.error.message}"
            )

        faces: list[FaceResult] = []
        for annotation in response.face_annotations:
            vertices = annotation.bounding_poly.vertices
            if vertices:
                xs   = [v.x for v in vertices]
                ys   = [v.y for v in vertices]
                bbox = [min(xs), min(ys), max(xs), max(ys)]
            else:
                bbox = [0, 0, 0, 0]

            confidence = round(annotation.detection_confidence, 4)
            embedding  = self._embed_face_crop(image_bytes, bbox)

            faces.append(
                FaceResult(
                    face_id=str(uuid.uuid4()),
                    bbox=bbox,
                    confidence=confidence,
                    embedding=embedding,
                )
            )

        logger.info(
            "Face detection complete: %d face(s) detected and embedded.",
            len(faces),
        )
        return FaceDetectionResult(
            faces_detected=len(faces),
            faces=faces,
        )
