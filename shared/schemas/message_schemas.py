"""Pydantic schemas for Redis Stream message validation.

These schemas match the actual camelCase field names used in Redis Stream
messages. Use validate_incoming() / validate_outgoing() in workers to
enforce structure at runtime.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class PostImageProcessingMessage(BaseModel):
    """Incoming message on the post-image-processing stream."""
    mediaId: str = Field(..., description="Media ID")
    postId: str = Field(..., description="Post ID")
    mediaUrl: str = Field(..., description="Image URL to process")
    correlationId: Optional[str] = Field("", description="Correlation ID for tracing")
    version: Optional[str] = Field(None)


class MLInsightsResultMessage(BaseModel):
    """Outgoing message on the ml-insights-results stream."""
    mediaId: str
    postId: str
    service: str
    timestamp: str
    version: str = "1"
    
    isSafe: Optional[str] = None
    moderationConfidence: Optional[str] = None
    tags: Optional[str] = None
    scenes: Optional[str] = None
    caption: Optional[str] = None


class FaceDetectionResultMessage(BaseModel):
    """Outgoing message on the face-detection-results stream."""
    mediaId: str
    postId: str
    facesDetected: str
    faces: str  # JSON-encoded list
    timestamp: str
    version: str = "1"


class PostAggregationTriggerMessage(BaseModel):
    """Incoming trigger on the post-aggregation-trigger stream."""
    postId: str
    mediaInsights: Optional[str] = "[]"
    allMediaIds: Optional[str] = None
    totalMedia: Optional[str] = None
    correlationId: Optional[str] = ""
    version: Optional[str] = None


class PostInsightsEnrichedMessage(BaseModel):
    """Outgoing message on the post-insights-enriched stream."""
    postId: str
    mediaCount: str
    allAiTags: str
    allAiScenes: str
    aggregatedTags: str
    aggregatedScenes: str
    totalFaces: str
    isSafe: str
    moderationConfidence: str
    inferredEventType: str
    combinedCaption: str
    hasMultipleImages: str
    timestamp: str
    correlationId: Optional[str] = ""
    version: str = "1"


class ESSyncEventMessage(BaseModel):
    """Incoming message on the es-sync-queue stream."""
    indexType: str
    documentId: str
    operation: Optional[str] = "index"
    version: Optional[str] = None


class DLQMessage(BaseModel):
    """Message on the ai-processing-dlq stream."""
    originalMessageId: Optional[str] = None
    serviceName: Optional[str] = None
    error: Optional[str] = None
    errorType: Optional[str] = None
    retryCount: Optional[str] = None
    timestamp: Optional[str] = None
    version: str = "1"


def validate_incoming(data: Dict[str, Any], schema: Type[T]) -> T:
    """Validate an incoming decoded message against a schema.
    
    Returns the validated model instance.
    Raises pydantic.ValidationError on failure.
    """
    return schema.model_validate(data)


def validate_outgoing(data: Dict[str, Any], schema: Type[T]) -> Dict[str, Any]:
    """Validate an outgoing message dict against a schema.
    
    Returns the dict unchanged if valid.
    Raises pydantic.ValidationError on failure.
    """
    schema.model_validate(data)
    return data
