"""Strict Pydantic DTO schemas matching the Java backend data contracts.

Use model_validate() at ingress/egress points to enforce the contract and
catch schema drift early.
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PostImageEventDTO(BaseModel):
    """Incoming Redis event: a new post image that requires AI processing.

    Corresponds to PostImageEventDTO on the Java backend.
    Field name is mediaUrl to match the Java DTO (was imageUrl — GAP-5 fix).
    """

    model_config = ConfigDict(strict=True)

    postId: str = Field(..., description="ID of the post this media belongs to")
    mediaId: str = Field(..., description="Unique ID of the media asset")
    mediaUrl: str = Field(..., description="Publicly accessible URL of the image")
    correlationId: str = Field(..., description="Trace / correlation ID for the request")


class MediaAiInsightsResultDTO(BaseModel):
    """Outgoing Redis event: ML insights produced for a single media asset.

    Corresponds to MediaAiInsightsResultDTO on the Java backend.
    """

    model_config = ConfigDict(strict=True)

    mediaId: str = Field(..., description="ID of the media asset that was processed")
    correlationId: str = Field(..., description="Echoed correlation ID from the originating event")
    isSafe: bool = Field(..., description="True when content moderation deems the image safe")
    caption: Optional[str] = Field(None, description="Auto-generated image caption")
    tags: Optional[List[str]] = Field(None, description="Predicted semantic tags")
    scenes: Optional[List[str]] = Field(None, description="Detected scene categories")
    imageEmbedding: Optional[List[float]] = Field(None, description="Dense vector embedding of the image")


class LocalMediaEventDTO(BaseModel):
    """Internal pipeline event: image downloaded to shared local storage.

    Published by the MediaPreprocessorWorker to ml-inference-tasks after a
    successful download. Downstream ML workers read the image from localFilePath
    instead of fetching it over the network.
    """

    model_config = ConfigDict(strict=True)

    postId: str = Field(..., description="ID of the post this media belongs to")
    mediaId: str = Field(..., description="Unique ID of the media asset")
    localFilePath: str = Field(..., description="Absolute path to the downloaded image on the shared volume")
    correlationId: str = Field(..., description="Echoed correlation ID for end-to-end tracing")


class ModelUpdateEventDTO(BaseModel):
    """Incoming federated-learning gradient update from an edge node.

    Published by edge nodes to federated-gradient-updates and consumed by
    the FederatedAggregatorWorker.
    """

    model_config = ConfigDict(strict=True)

    nodeId: str = Field(..., description="Identifier of the edge node that produced this update")
    modelName: str = Field(..., description="Name/version of the model being trained")
    gradientPayload: List[float] = Field(..., description="Gradient values to aggregate")
    correlationId: str = Field(..., description="Trace ID for end-to-end correlation")


class ProfilePictureEventDTO(BaseModel):
    """Incoming Redis event: a user profile picture requires face enrollment.

    Published by the Java backend to profile-picture-processing when a user
    uploads or changes their profile picture. The ProfileEnrollmentWorker
    extracts the face embedding and publishes the result to
    user-profile-face-embedding-results for the Java backend to consume.

    Fields match Java ProfilePictureEventDTO exactly (GAP-4 fix):
      - removed: username (Java does not publish this field)
      - renamed: profilePicUrl -> imageUrl (matches Java field name)
    """

    model_config = ConfigDict(strict=True)

    userId: str = Field(..., description="Unique ID of the user")
    imageUrl: str = Field(..., description="Publicly accessible URL of the profile picture")
    correlationId: str = Field(..., description="Trace / correlation ID for the request")


class FaceTagSuggestionDTO(BaseModel):
    """Outgoing Redis event: a face in a post image matched to a known user.

    Published by the FaceMatcherWorker to face-recognition-results so the Java
    FaceRecognitionConsumer can create a pending tag suggestion.

    Field names match Java FaceRecognitionResultDTO (GAP-1/GAP-3/GAP-7 fix):
      - renamed: matchedUserId -> suggestedUserId
      - renamed: confidence   -> confidenceScore (type: float, not str)
    Extra context fields (mediaId, postId, matchedUsername, correlationId) are
    ignored by Java's Jackson deserializer but useful for tracing.
    """

    model_config = ConfigDict(strict=True)

    mediaId: str = Field(..., description="ID of the media asset where the face was detected")
    postId: str = Field(..., description="ID of the post containing the media")
    faceId: str = Field(..., description="Identifier of the specific detected face")
    suggestedUserId: str = Field(..., description="User ID of the matched known face")
    matchedUsername: str = Field(..., description="Username of the matched known face")
    confidenceScore: float = Field(..., description="KNN similarity score between 0 and 1")
    correlationId: str = Field(..., description="Echoed correlation ID for end-to-end tracing")
