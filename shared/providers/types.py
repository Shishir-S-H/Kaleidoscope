"""Standardised result types returned by all AI provider implementations."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModerationResult:
    """Result of a content-moderation analysis."""

    is_safe: bool
    confidence: float
    scores: dict[str, float]
    top_label: str


@dataclass
class TaggingResult:
    """Result of image tagging / zero-shot classification."""

    tags: list[str]
    scores: dict[str, float]


@dataclass
class SceneResult:
    """Result of scene recognition."""

    scene: str
    confidence: float
    scores: dict[str, float]


@dataclass
class CaptioningResult:
    """Result of image captioning."""

    caption: str


@dataclass
class FaceResult:
    """A single detected face."""

    face_id: str
    bbox: list[int]
    embedding: list[float]
    confidence: float


@dataclass
class FaceDetectionResult:
    """Result of face detection on an image."""

    faces_detected: int
    faces: list[FaceResult] = field(default_factory=list)
