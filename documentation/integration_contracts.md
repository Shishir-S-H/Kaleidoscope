# Integration Contracts — Kaleidoscope Platform

> **Edition:** Phase C (April 2026)  
> **Scope:** REST API surface (React ↔ Java) and all Redis Stream contracts (Java ↔ Python).  
> **Status:** Reflects Phase C DTO fixes — `mediaUrl`, `imageUrl`, `suggestedUserId`, `confidenceScore`, and removal of `hasConsent`.

---

## Table of Contents

1. [REST API — React Frontend ↔ Java Backend](#1-rest-api--react-frontend--java-backend)
2. [Redis Stream Contracts — Java ↔ Python](#2-redis-stream-contracts--java--python)
   - 2.1 [Java → Python streams (inbound to AI layer)](#21-java--python-streams-inbound-to-ai-layer)
   - 2.2 [Python → Java streams (outbound from AI layer)](#22-python--java-streams-outbound-from-ai-layer)
   - 2.3 [Python → Python internal streams](#23-python--python-internal-streams)
   - 2.4 [Resilience streams](#24-resilience-streams)
3. [Pydantic DTO Registry](#3-pydantic-dto-registry)
4. [Global Encoding Rules](#4-global-encoding-rules)

---

## 1. REST API — React Frontend ↔ Java Backend

All endpoints are served by the Java Spring Boot backend at `https://<host>:8080`. Authentication uses JWT Bearer tokens (access token via `Authorization` header; refresh token via HTTP-only cookie).

### Authentication

| Method | Path | Request Body | Response | Description |
|--------|------|-------------|----------|-------------|
| `POST` | `/api/auth/register` | `{ username, email, password, department }` | `201 { userId, accessToken }` | Create account and issue tokens |
| `POST` | `/api/auth/login` | `{ email, password }` | `200 { accessToken, user }` | Authenticate and issue tokens |
| `POST` | `/api/auth/refresh` | *(HTTP-only cookie)* | `200 { accessToken }` | Rotate access token using refresh cookie |
| `POST` | `/api/auth/logout` | — | `204` | Invalidate refresh token |
| `POST` | `/api/auth/forgot-password` | `{ email }` | `200` | Send password-reset email |
| `POST` | `/api/auth/reset-password` | `{ token, newPassword }` | `200` | Apply password reset |

### Users & Profiles

| Method | Path | Request Body | Response | Description |
|--------|------|-------------|----------|-------------|
| `GET` | `/api/users/{userId}` | — | `200 UserDTO` | Fetch public profile |
| `PUT` | `/api/users/{userId}` | `{ username?, department?, bio? }` | `200 UserDTO` | Update own profile |
| `POST` | `/api/users/{userId}/profile-picture` | `multipart/form-data (file)` | `200 { profilePicUrl }` | Upload profile picture; triggers `profile-picture-processing` stream |
| `GET` | `/api/users/{userId}/followers` | — | `200 Page<UserDTO>` | List followers |
| `POST` | `/api/users/{userId}/follow` | — | `204` | Follow a user |
| `DELETE` | `/api/users/{userId}/follow` | — | `204` | Unfollow a user |

### Posts & Media

| Method | Path | Request Body | Response | Description |
|--------|------|-------------|----------|-------------|
| `POST` | `/api/posts` | `{ title, body, mediaUrls[] }` | `201 PostDTO` | Create post; backend publishes to `post-image-processing` for each media URL |
| `GET` | `/api/posts/{postId}` | — | `200 PostDTO` | Fetch single post |
| `GET` | `/api/posts/feed` | `?page&size` | `200 Page<PostDTO>` | Personalised feed |
| `DELETE` | `/api/posts/{postId}` | — | `204` | Delete post |
| `POST` | `/api/posts/{postId}/reactions` | `{ reactionType }` | `201` | Add reaction; updates read-model counts |
| `GET` | `/api/posts/{postId}/comments` | `?page&size` | `200 Page<CommentDTO>` | List comments |
| `POST` | `/api/posts/{postId}/comments` | `{ body }` | `201 CommentDTO` | Add comment |

### Search & Discovery

| Method | Path | Query Params | Response | Description |
|--------|------|-------------|----------|-------------|
| `GET` | `/api/search/media` | `q`, `tags[]`, `scenes[]`, `page`, `size` | `200 Page<MediaResultDTO>` | Full-text + AI-tag media search via `media_search` ES index |
| `GET` | `/api/search/posts` | `q`, `eventType`, `page`, `size` | `200 Page<PostResultDTO>` | Post-level search via `post_search` ES index |
| `GET` | `/api/search/users` | `q`, `department`, `page`, `size` | `200 Page<UserResultDTO>` | User discovery via `user_search` ES index |
| `GET` | `/api/search/faces` | `userId` | `200 List<MediaResultDTO>` | Find all media where `userId` was auto-tagged |
| `GET` | `/api/recommendations` | `?page&size` | `200 Page<PostDTO>` | KNN content recommendations |

### Face Tagging

| Method | Path | Request Body | Response | Description |
|--------|------|-------------|----------|-------------|
| `GET` | `/api/tags/suggestions/{postId}` | — | `200 List<FaceSuggestionDTO>` | Pending AI face-tag suggestions for a post |
| `POST` | `/api/tags/{suggestionId}/confirm` | — | `204` | User confirms a face-tag suggestion |
| `POST` | `/api/tags/{suggestionId}/reject` | — | `204` | User rejects a face-tag suggestion |

---

## 2. Redis Stream Contracts — Java ↔ Python

### 2.1 Java → Python Streams (Inbound to AI Layer)

#### `post-image-processing`

**Producer:** Java backend (on media upload)  
**Consumers:** `media_preprocessor`, `content_moderation`, `image_tagger`, `scene_recognition`, `image_captioning`, `face_recognition` (six independent consumer groups)  
**Pydantic DTO:** `PostImageEventDTO` (`shared/schemas/schemas.py`)

> **Phase C fix (GAP-5):** Field renamed from `imageUrl` → `mediaUrl` to match Java `PostImageEventDTO`.  
> **Phase C fix (GAP-6):** `hasConsent` field removed; consent enforcement is now handled upstream in Java before publishing.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `postId` | string | ✅ | ID of the post this media belongs to |
| `mediaId` | string | ✅ | Unique ID of the media asset |
| `mediaUrl` | string | ✅ | Publicly accessible Cloudinary URL of the image |
| `correlationId` | string | ✅ | End-to-end distributed trace identifier |

---

#### `profile-picture-processing`

**Producer:** Java backend (on profile picture upload)  
**Consumer:** `profile_enrollment`  
**Pydantic DTO:** `ProfilePictureEventDTO` (`shared/schemas/schemas.py`)

> **Phase C fix (GAP-4):** Field renamed from `profilePicUrl` → `imageUrl` and `username` field removed, to match Java `ProfilePictureEventDTO` exactly.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `userId` | string | ✅ | Unique ID of the user |
| `imageUrl` | string | ✅ | Publicly accessible URL of the new profile picture |
| `correlationId` | string | ✅ | Trace / correlation ID |

---

#### `post-aggregation-trigger`

**Producer:** Java backend (after all ML results arrive for a post)  
**Consumer:** `post_aggregator`  
**Pydantic schema:** `PostAggregationTriggerMessage` (`shared/schemas/message_schemas.py`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `postId` | string | ✅ | Post to aggregate |
| `allMediaIds` | string (JSON array) | ✅ | JSON-encoded list of all expected media IDs |
| `totalMedia` | string | ✅ | Integer count of expected media items |
| `mediaInsights` | string (JSON object) | ❌ | Optional pre-fetched insights map |
| `correlationId` | string | ❌ | Trace ID |

---

#### `es-sync-queue`

**Producer:** Java backend (after read-model updates)  
**Consumer:** `es_sync`  
**Pydantic schema:** `ESSyncEventMessage` (`shared/schemas/message_schemas.py`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `indexType` | string | ✅ | Target index: `media_search` \| `post_search` \| `user_search` \| `face_search` \| `recommendations_knn` \| `feed_personalized` \| `known_faces_index` |
| `documentId` | string | ✅ | Primary key of the document (read from PostgreSQL read-model table) |
| `operation` | string | ❌ | `"index"` (default) or `"delete"` |

---

### 2.2 Python → Java Streams (Outbound from AI Layer)

#### `ml-insights-results`

**Producers:** `content_moderation`, `image_tagger`, `scene_recognition`, `image_captioning`  
**Consumer:** Java `MediaAiInsightsConsumer`  
**Pydantic schema:** `MLInsightsResultMessage`

| Field | Type | Present When | Description |
|-------|------|-------------|-------------|
| `mediaId` | string | Always | Media asset ID |
| `postId` | string | Always | Owning post ID |
| `service` | string | Always | `"moderation"` \| `"tagging"` \| `"scene_recognition"` \| `"image_captioning"` |
| `timestamp` | string (ISO-8601) | Always | Processing completion timestamp |
| `version` | string | Always | Schema version (default `"1"`) |
| `isSafe` | string `"true"\|"false"` | Moderation only | Content safety verdict |
| `moderationConfidence` | string (float) | Moderation only | Confidence score |
| `tags` | string (JSON array) | Tagging only | Predicted semantic tags |
| `scenes` | string (JSON array) | Scene recognition only | Detected scene categories |
| `caption` | string | Captioning only | Generated natural-language caption |

---

#### `face-detection-results`

**Producer:** `face_recognition`  
**Consumers:** `face_matcher` (Python), Java `FaceDetectionConsumer`  
**Pydantic schema:** `FaceDetectionResultMessage`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mediaId` | string | ✅ | Media asset ID |
| `postId` | string | ✅ | Owning post ID |
| `facesDetected` | string (integer) | ✅ | Count of faces found |
| `faces` | string (JSON array) | ✅ | JSON-encoded list of face objects (see below) |
| `timestamp` | string (ISO-8601) | ✅ | Processing timestamp |
| `version` | string | ✅ | Schema version (default `"1"`) |
| `correlationId` | string | ✅ | Trace ID |

**Face object schema** (elements of the `faces` JSON array):

| Field | Type | Description |
|-------|------|-------------|
| `faceId` | string (UUID) | Unique identifier for this detected face |
| `bbox` | array `[x, y, w, h]` | Bounding box in pixels |
| `embedding` | array of float (1024-dim) | Dense face embedding vector |
| `confidence` | float | Detection confidence 0–1 |

---

#### `face-recognition-results`

**Producer:** `face_matcher`  
**Consumer:** Java `FaceRecognitionConsumer`  
**Pydantic DTO:** `FaceTagSuggestionDTO` (`shared/schemas/schemas.py`)

> **Phase C fix (GAP-1 / GAP-3 / GAP-7):** Stream renamed from `face-tag-suggestions` → `face-recognition-results`. Field `matchedUserId` renamed to `suggestedUserId`. Field `confidence` renamed to `confidenceScore` and changed type from `string` to `float`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mediaId` | string | ✅ | Media asset ID where face was detected |
| `postId` | string | ✅ | Post containing the media |
| `faceId` | string | ✅ | Identifier of the specific detected face |
| `suggestedUserId` | string | ✅ | User ID of the matched known face |
| `matchedUsername` | string | ✅ | Username of the matched user |
| `confidenceScore` | **float** | ✅ | KNN cosine similarity score 0–1 |
| `correlationId` | string | ✅ | Echoed trace ID |

---

#### `user-profile-face-embedding-results`

**Producer:** `profile_enrollment`  
**Consumer:** Java `UserProfileFaceEmbeddingConsumer`

> **Phase C fix (GAP-2):** Stream was incorrectly routing to `es-sync-queue` (bypassing Java entirely). Now correctly publishes to `user-profile-face-embedding-results` so Java can update the read model before triggering ES sync.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `userId` | string | ✅ | User whose profile picture was enrolled |
| `faceEmbedding` | string (JSON array of float) | ✅ | Extracted 1024-dim face embedding |
| `correlationId` | string | ✅ | Trace ID |

---

#### `post-insights-enriched`

**Producer:** `post_aggregator`  
**Consumer:** Java `PostInsightsConsumer`  
**Pydantic schema:** `PostInsightsEnrichedMessage`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `postId` | string | ✅ | Post ID |
| `mediaCount` | string (integer) | ✅ | Number of media items in post |
| `allAiTags` | string (JSON array) | ✅ | All tags across every media item |
| `allAiScenes` | string (JSON array) | ✅ | All scenes across every media item |
| `aggregatedTags` | string (JSON array) | ✅ | Deduplicated top tags |
| `aggregatedScenes` | string (JSON array) | ✅ | Deduplicated top scenes |
| `totalFaces` | string (integer) | ✅ | Total face count across all media |
| `isSafe` | string `"true"\|"false"` | ✅ | Aggregate content safety verdict |
| `moderationConfidence` | string (float) | ✅ | Confidence of the safety verdict |
| `inferredEventType` | string | ✅ | Inferred event category (e.g. `"beach_party"`) |
| `combinedCaption` | string | ✅ | Merged caption from all media |
| `hasMultipleImages` | string `"true"\|"false"` | ✅ | Whether the post has more than one image |
| `timestamp` | string (ISO-8601) | ✅ | Aggregation completion timestamp |
| `correlationId` | string | ✅ | Trace ID |
| `version` | string | ✅ | Schema version (default `"1"`) |

---

### 2.3 Python → Python Internal Streams

#### `ml-inference-tasks`

**Producer:** `media_preprocessor`  
**Intended consumers:** All five ML inference workers (migration pending — see Tech Debt TD-1)  
**Pydantic DTO:** `LocalMediaEventDTO` (`shared/schemas/schemas.py`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `postId` | string | ✅ | Post ID |
| `mediaId` | string | ✅ | Media asset ID |
| `localFilePath` | string | ✅ | Absolute path to the image on the shared Docker volume (`/tmp/kaleidoscope_media/<mediaId>.jpg`) |
| `correlationId` | string | ✅ | Echoed trace ID |

---

#### `federated-gradient-updates` / `global-model-state`

**Producer of `federated-gradient-updates`:** Edge nodes  
**Consumer:** `federated_aggregator`  
**Producer of `global-model-state`:** `federated_aggregator`  
**Pydantic DTO:** `ModelUpdateEventDTO` (`shared/schemas/schemas.py`)

`federated-gradient-updates` payload:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `nodeId` | string | ✅ | Edge node identifier |
| `modelName` | string | ✅ | Model name and version |
| `gradientPayload` | string (JSON array of float) | ✅ | Gradient values to aggregate |
| `correlationId` | string | ✅ | Trace ID |

`global-model-state` payload:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `modelName` | string | ✅ | Model name and version |
| `aggregatedGradients` | string (JSON array of float) | ✅ | Averaged gradient values |
| `nodeCount` | string (integer) | ✅ | Number of contributing edge nodes |
| `correlationId` | string | ✅ | Trace ID |
| `timestamp` | string (ISO-8601) | ✅ | Aggregation timestamp |

---

### 2.4 Resilience Streams

#### `ai-processing-dlq`

**Producers:** Any Python worker after exhausting retries  
**Consumer:** `dlq_processor` (retries to `post-image-processing`)  
**Pydantic schema:** `DLQMessage`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `originalMessageId` | string | ✅ | Redis message ID of the failed message |
| `serviceName` | string | ✅ | Worker name that failed |
| `error` | string | ✅ | Exception message |
| `errorType` | string | ✅ | Exception class name |
| `retryCount` | string (integer) | ✅ | Number of retry attempts |
| `timestamp` | string (Unix epoch) | ✅ | Failure timestamp |
| `version` | string | ✅ | `"1"` |

`dlq_processor` behaviour is controlled by `DLQ_AUTO_RETRY` env var. When enabled, messages are re-published to `post-image-processing` up to `DLQ_MAX_RETRIES` times.

#### `privacy-audit-queue`

Reserved for non-consented media routed by the upstream Java consent layer. No Python workers consume from this stream; it is drained by a dedicated audit/compliance consumer.

---

## 3. Pydantic DTO Registry

| DTO Class | File | Used By | Direction |
|-----------|------|---------|-----------|
| `PostImageEventDTO` | `shared/schemas/schemas.py` | `media_preprocessor`, all ML workers | Java → Python (inbound) |
| `ProfilePictureEventDTO` | `shared/schemas/schemas.py` | `profile_enrollment` | Java → Python (inbound) |
| `LocalMediaEventDTO` | `shared/schemas/schemas.py` | `media_preprocessor` (out), ML workers (in) | Python → Python (internal) |
| `ModelUpdateEventDTO` | `shared/schemas/schemas.py` | `federated_aggregator` | Edge → Python (inbound) |
| `FaceTagSuggestionDTO` | `shared/schemas/schemas.py` | `face_matcher` | Python → Java (outbound) |
| `MLInsightsResultMessage` | `shared/schemas/message_schemas.py` | `content_moderation`, `image_tagger`, `scene_recognition`, `image_captioning` | Python → Java (outbound) |
| `FaceDetectionResultMessage` | `shared/schemas/message_schemas.py` | `face_recognition` | Python → Java/Python (outbound) |
| `PostAggregationTriggerMessage` | `shared/schemas/message_schemas.py` | `post_aggregator` | Java → Python (inbound) |
| `PostInsightsEnrichedMessage` | `shared/schemas/message_schemas.py` | `post_aggregator` | Python → Java (outbound) |
| `ESSyncEventMessage` | `shared/schemas/message_schemas.py` | `es_sync` | Java → Python (inbound) |
| `DLQMessage` | `shared/schemas/message_schemas.py` | All workers → `dlq_processor` | Python → Python (resilience) |

---

## 4. Global Encoding Rules

| Rule | Detail |
|------|--------|
| All Redis field values | UTF-8 strings |
| Numeric IDs | Always serialised as strings (`"90001"`, not `90001`) |
| Arrays / objects | JSON-encoded strings (e.g. `"[\"beach\",\"sunset\"]"`) |
| Booleans | `"true"` or `"false"` strings (except `confidenceScore` which is a native float in `FaceTagSuggestionDTO`) |
| Timestamps | ISO-8601 format (`"2026-04-06T14:30:00Z"`) |
| `correlationId` | Mandatory on all inbound messages; echoed by all Python workers |
| Schema version | `version: "1"` on all outbound messages where applicable |
