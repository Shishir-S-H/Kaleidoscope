"""HuggingFace image-embedding provider.

Uses the Inference API feature-extraction pipeline (e.g. openai/clip-vit-base-patch32)
to produce a 512-dim dense vector for a given image.

Falls back to a direct HTTP POST to an HF Space URL when the Inference API is
unavailable or not configured.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, List, Optional

from shared.providers.base import BaseEmbeddingProvider
from shared.providers.types import EmbeddingResult
from shared.utils.http_client import get_http_session
from shared.utils.hf_inference import is_model_id
from shared.utils.secrets import get_secret

logger = logging.getLogger(__name__)

DEFAULT_MODEL_ID = "openai/clip-vit-base-patch32"
EXPECTED_DIMS = 512


class HFEmbeddingProvider(BaseEmbeddingProvider):
    """Image embedding via HuggingFace feature-extraction.

    Priority:
      1. InferenceClient (when HF_EMBEDDING_API_URL is a model ID, e.g. openai/clip-vit-base-patch32)
      2. HTTP POST to an HF Space URL (when HF_EMBEDDING_API_URL is a full URL)
    """

    def __init__(self) -> None:
        self._api_url: str = os.getenv(
            "HF_EMBEDDING_API_URL", os.getenv("HF_API_URL", DEFAULT_MODEL_ID)
        )
        self._api_token: Optional[str] = get_secret("HF_API_TOKEN")
        self._session = get_http_session()
        self._use_inference = is_model_id(self._api_url)
        self._inference_disabled = False

        mode = "InferenceClient" if self._use_inference else "HF Space URL"
        logger.info("Embedding provider using %s: %s", mode, self._api_url)

    @property
    def name(self) -> str:
        return "huggingface"

    # ------------------------------------------------------------------

    def embed(self, image_bytes: bytes) -> EmbeddingResult:
        """Return a 512-dim embedding vector for the given image bytes."""
        if self._use_inference and not self._inference_disabled:
            try:
                vector = self._embed_via_inference(image_bytes)
                return EmbeddingResult(embedding=vector, dimensions=len(vector))
            except Exception as exc:
                logger.warning(
                    "Embedding InferenceClient failed, falling back to Space URL: %s", exc
                )
                self._inference_disabled = True

        vector = self._embed_via_space(image_bytes, self._api_url)
        return EmbeddingResult(embedding=vector, dimensions=len(vector))

    def _embed_via_inference(self, image_bytes: bytes) -> List[float]:
        """Use huggingface_hub InferenceClient.feature_extraction."""
        from huggingface_hub import InferenceClient

        client = InferenceClient(token=self._api_token or None)

        suffix = ".jpg"
        if len(image_bytes) >= 4 and image_bytes[:4] == b"\x89PNG":
            suffix = ".png"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(image_bytes)
            tmp_path = Path(f.name)

        try:
            result = client.feature_extraction(str(tmp_path), model=self._api_url)
        finally:
            tmp_path.unlink(missing_ok=True)

        return self._flatten(result)

    def _embed_via_space(self, image_bytes: bytes, url: str) -> List[float]:
        """POST base64-encoded image to an HF Space embedding endpoint."""
        headers: dict = {"Content-Type": "application/json"}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload = {"inputs": b64}

        response = self._session.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        return self._flatten(response.json())

    @staticmethod
    def _flatten(raw: Any) -> List[float]:
        """Flatten a nested list / numpy array to a plain list of floats.

        HuggingFace feature-extraction may return:
          - A 1-D array:   [f1, f2, ..., f512]
          - A 2-D array:   [[f1, f2, ..., f512]]          (batch of 1)
          - A 3-D array:   [[[f1, ...]]]                   (batch + sequence)
        We always want the innermost 1-D slice.
        """
        try:
            import numpy as np  # optional dependency; numpy ships with huggingface_hub
            arr = np.array(raw, dtype="float32")
            while arr.ndim > 1:
                arr = arr[0]
            return arr.tolist()
        except Exception:
            pass

        # Pure-Python fallback
        while isinstance(raw, (list, tuple)) and len(raw) > 0 and isinstance(raw[0], (list, tuple)):
            raw = raw[0]
        return [float(v) for v in raw]
