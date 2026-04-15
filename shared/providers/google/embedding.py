"""Google Vertex AI Multimodal Embeddings provider.

Uses the ``multimodalembedding@001`` model which returns 1408-dimensional
dense vectors — compatible with the updated Elasticsearch index mappings.
"""

from __future__ import annotations

import logging
import os

from shared.providers.base import BaseEmbeddingProvider
from shared.providers.google.base import GoogleBaseProvider
from shared.providers.types import EmbeddingResult

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = os.getenv(
    "GOOGLE_EMBEDDING_MODEL", "multimodalembedding@001"
)
EXPECTED_DIMS = 1408


class GoogleEmbeddingProvider(GoogleBaseProvider, BaseEmbeddingProvider):
    """Image embedding using Vertex AI Multimodal Embeddings (1408-dim)."""

    def __init__(self) -> None:
        self._bootstrap()
        self._model = None

    @property
    def name(self) -> str:
        return "google"

    def _get_model(self):
        if self._model is None:
            import vertexai
            from vertexai.vision_models import MultiModalEmbeddingModel

            vertexai.init(project=self._project, location=self._location)
            self._model = MultiModalEmbeddingModel.from_pretrained(_EMBEDDING_MODEL)
            logger.info(
                "Vertex AI embedding model loaded: %s (project=%s, location=%s)",
                _EMBEDDING_MODEL, self._project, self._location,
            )
        return self._model

    def embed(self, image_bytes: bytes) -> EmbeddingResult:
        """Return a 1408-dim embedding vector for the given image bytes."""
        from vertexai.vision_models import Image as VertexImage

        model = self._get_model()
        vertex_image = VertexImage(image_bytes=image_bytes)
        embeddings = model.get_embeddings(image=vertex_image)

        vector: list[float] = embeddings.image_embedding
        dims = len(vector)

        if dims != EXPECTED_DIMS:
            logger.warning(
                "Vertex AI returned %d dims; expected %d. "
                "Ensure ES index mappings are updated.",
                dims, EXPECTED_DIMS,
            )

        logger.debug("Embedding generated: %d dimensions.", dims)
        return EmbeddingResult(embedding=vector, dimensions=dims)
