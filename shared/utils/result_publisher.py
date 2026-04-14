"""Typed publish helpers for ML worker outbound messages.

Workers call these functions with native Python types (bool, list, etc.).
This module applies the global Redis encoding rules and validates against
the outbound Pydantic schema before handing off to RedisStreamPublisher.

Global encoding rules (integration_contracts.md §4):
  - All field values are UTF-8 strings.
  - Arrays → json.dumps(list)
  - Booleans → "true" / "false"
  - Numeric IDs → str(int)
  - Timestamps → ISO-8601 with Z suffix
"""

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from shared.redis_streams import RedisStreamPublisher
from shared.schemas.message_schemas import (
    FaceDetectionResultMessage,
    MLInsightsResultMessage,
    validate_outgoing,
)


def publish_ml_insight(
    publisher: RedisStreamPublisher,
    stream: str,
    *,
    media_id: str,
    post_id: str,
    service: str,
    correlation_id: str,
    is_safe: Optional[bool] = None,
    moderation_confidence: Optional[float] = None,
    tags: Optional[List[str]] = None,
    scenes: Optional[List[str]] = None,
    caption: Optional[str] = None,
) -> str:
    """Build, validate, and publish a single MLInsightsResultMessage.

    Accepts native Python types; encodes to wire format internally.
    Raises pydantic.ValidationError if required fields are missing or wrong type.

    Encoding applied:
      - is_safe (bool)  → "true" / "false"
      - tags / scenes (list) → json.dumps(list)
      - moderation_confidence (float) → str(float)
    """
    message: Dict[str, str] = {
        "mediaId": str(media_id),
        "postId": str(post_id),
        "service": service,
        "correlationId": correlation_id,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "version": "1",
    }

    if is_safe is not None:
        message["isSafe"] = "true" if is_safe else "false"
    if moderation_confidence is not None:
        message["moderationConfidence"] = str(moderation_confidence)
    if tags is not None:
        message["tags"] = json.dumps(tags)
    if scenes is not None:
        message["scenes"] = json.dumps(scenes)
    if caption is not None:
        message["caption"] = caption

    validate_outgoing(message, MLInsightsResultMessage)
    return publisher.publish(stream, message)


def publish_face_detection(
    publisher: RedisStreamPublisher,
    stream: str,
    *,
    media_id: str,
    post_id: str,
    correlation_id: str,
    faces_detected: int,
    faces: List[Dict],
) -> str:
    """Build, validate, and publish a FaceDetectionResultMessage.

    Accepts native Python types; encodes to wire format internally.
    Raises pydantic.ValidationError if required fields are missing or wrong type.

    Encoding applied:
      - faces_detected (int) → str(int)
      - faces (list of dicts) → json.dumps(list)
    """
    message: Dict[str, str] = {
        "mediaId": str(media_id),
        "postId": str(post_id),
        "facesDetected": str(faces_detected),
        "faces": json.dumps(faces),
        "correlationId": correlation_id,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "version": "1",
    }

    validate_outgoing(message, FaceDetectionResultMessage)
    return publisher.publish(stream, message)
