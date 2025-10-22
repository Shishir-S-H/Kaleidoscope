"""Pydantic schemas for Redis Stream messages."""

from typing import List, Optional
from pydantic import BaseModel, Field


class PostImageProcessingMessage(BaseModel):
    """Message to trigger AI processing for an image."""
    media_id: int = Field(..., description="Media ID from post_media table")
    post_id: int = Field(..., description="Post ID that contains this media")
    media_url: str = Field(..., description="URL of the image to process")
    uploader_id: int = Field(..., description="User ID who uploaded the image")


class MLInsightsResultMessage(BaseModel):
    """Message containing ML insights results."""
    media_id: int = Field(..., description="Media ID")
    post_id: int = Field(..., description="Post ID")
    service: str = Field(..., description="Service name (tagging, captioning, scene_recognition, moderation)")
    
    # Content moderation fields
    is_safe: Optional[bool] = Field(None, description="Whether content is safe")
    moderation_confidence: Optional[float] = Field(None, description="Confidence score for moderation")
    
    # Tagging fields
    tags: Optional[List[str]] = Field(None, description="AI-generated tags")
    
    # Scene recognition fields
    scenes: Optional[List[str]] = Field(None, description="AI-detected scenes")
    
    # Captioning fields
    caption: Optional[str] = Field(None, description="AI-generated caption")


class FaceDetectionResultMessage(BaseModel):
    """Message containing face detection results."""
    
    class DetectedFace(BaseModel):
        """Single detected face."""
        face_id: str = Field(..., description="Unique face ID (UUID)")
        bbox: List[int] = Field(..., description="Bounding box [x, y, width, height]")
        embedding: str = Field(..., description="1024-dim face embedding as JSON string")
        confidence: float = Field(..., description="Detection confidence score")
    
    media_id: int = Field(..., description="Media ID")
    post_id: int = Field(..., description="Post ID")
    faces_detected: int = Field(..., description="Number of faces detected")
    faces: List[DetectedFace] = Field(..., description="List of detected faces")


class PostAggregationTriggerMessage(BaseModel):
    """Message to trigger post-level aggregation."""
    post_id: int = Field(..., description="Post ID to aggregate")
    total_media_count: int = Field(..., description="Total number of media items in post")


class PostInsightsEnrichedMessage(BaseModel):
    """Message containing enriched post-level insights."""
    post_id: int = Field(..., description="Post ID")
    all_ai_tags: List[str] = Field(..., description="Union of all media tags")
    all_ai_scenes: List[str] = Field(..., description="Union of all media scenes")
    all_detected_user_ids: List[int] = Field(default_factory=list, description="All detected user IDs")
    inferred_event_type: Optional[str] = Field(None, description="Inferred event type (beach_party, meeting, etc.)")
    inferred_tags: List[str] = Field(default_factory=list, description="Enhanced semantic tags")


class ESSyncEventMessage(BaseModel):
    """Message to trigger Elasticsearch sync."""
    index_name: str = Field(..., description="Target ES index name")
    operation: str = Field(..., description="Operation: INDEX, UPDATE, DELETE, BULK")
    document_id: int = Field(..., description="Document ID (or post_id for BULK)")
    
    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "index_name": "media_search",
                "operation": "INDEX",
                "document_id": 123
            }
        }

