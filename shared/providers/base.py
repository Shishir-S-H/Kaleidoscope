"""Abstract base classes for each AI task provider."""

from __future__ import annotations

from abc import ABC, abstractmethod

from shared.providers.types import (
    CaptioningResult,
    FaceDetectionResult,
    ModerationResult,
    SceneResult,
    TaggingResult,
)


class BaseModerationProvider(ABC):
    """Analyse an image for content-safety / moderation."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider platform name (e.g. ``"huggingface"``)."""

    @abstractmethod
    def analyze(self, image_bytes: bytes) -> ModerationResult:
        """Run moderation analysis on raw image bytes."""


class BaseTaggerProvider(ABC):
    """Tag an image with descriptive labels."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider platform name."""

    @abstractmethod
    def tag(
        self,
        image_bytes: bytes,
        top_n: int = 5,
        threshold: float = 0.01,
    ) -> TaggingResult:
        """Return the top-N tags above *threshold* for an image."""


class BaseSceneProvider(ABC):
    """Recognise the scene / setting depicted in an image."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider platform name."""

    @abstractmethod
    def recognize(
        self,
        image_bytes: bytes,
        labels: list[str] | None = None,
        threshold: float = 0.005,
    ) -> SceneResult:
        """Return the best-matching scene label for an image."""


class BaseCaptioningProvider(ABC):
    """Generate a natural-language caption for an image."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider platform name."""

    @abstractmethod
    def caption(self, image_bytes: bytes) -> CaptioningResult:
        """Generate a caption for the given image bytes."""


class BaseFaceProvider(ABC):
    """Detect faces and extract embeddings from an image."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider platform name."""

    @abstractmethod
    def detect(self, image_bytes: bytes) -> FaceDetectionResult:
        """Detect faces and return bounding-boxes + embeddings."""
