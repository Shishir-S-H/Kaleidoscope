# User Journeys — Kaleidoscope Platform

> **Edition:** Phase C (April 2026)  
> **Scope:** End-to-end flows through the full stack — React → Java → Redis → Python → Elasticsearch.

---

## Table of Contents

1. [Journey 1: User Registration & Profile Picture Enrollment](#1-journey-1-user-registration--profile-picture-enrollment)
2. [Journey 2: Post Creation & Auto-Tagging](#2-journey-2-post-creation--auto-tagging)
3. [Journey 3: Media Discovery & Semantic Search](#3-journey-3-media-discovery--semantic-search)

---

## 1. Journey 1: User Registration & Profile Picture Enrollment

### Overview

A new user creates an account and uploads a profile picture. The platform extracts a face embedding from the picture and enrolls it into the `known_faces_index` in Elasticsearch, enabling future automatic face-tag suggestions on posts.

### Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant FE as React Frontend
    participant BE as Java Backend
    participant CDN as Cloudinary
    participant REDIS as Redis Streams
    participant PE as profile_enrollment<br/>(Python)
    participant HF as HuggingFace<br/>Inference API
    participant PG as PostgreSQL
    participant ES as Elasticsearch

    User->>FE: Fill registration form
    FE->>BE: POST /api/auth/register<br/>{ username, email, password, department }
    BE->>PG: INSERT users (hashed password, role)
    BE-->>FE: 201 { userId, accessToken }
    FE-->>User: Redirect to profile setup

    User->>FE: Upload profile picture
    FE->>CDN: Upload image (direct upload)
    CDN-->>FE: { secure_url }
    FE->>BE: POST /api/users/{userId}/profile-picture<br/>{ profilePicUrl }
    BE->>PG: UPDATE users SET profile_pic_url = ?
    BE->>REDIS: XADD profile-picture-processing<br/>{ userId, imageUrl, correlationId }
    BE-->>FE: 200 { profilePicUrl }
    FE-->>User: Profile picture saved ✓

    Note over REDIS,PE: Asynchronous AI Processing
    REDIS->>PE: XREADGROUP profile-enrollment-group<br/>{ userId, imageUrl, correlationId }
    PE->>CDN: GET imageUrl (download image bytes)
    CDN-->>PE: image bytes
    PE->>HF: Face detection + embedding extraction
    HF-->>PE: { faces: [{ embedding[1024], confidence }] }

    alt No face detected
        PE->>PE: Log warning, XACK, skip enrollment
    else Face detected
        PE->>REDIS: XADD user-profile-face-embedding-results<br/>{ userId, faceEmbedding[1024], correlationId }
        PE->>REDIS: XACK profile-picture-processing
        REDIS->>BE: XREADGROUP UserProfileFaceEmbeddingConsumer
        BE->>PG: UPDATE read_model_known_faces SET face_embedding = ?
        BE->>REDIS: XADD es-sync-queue<br/>{ indexType: "known_faces_index", documentId: userId, operation: "index" }
        REDIS->>BE: es_sync reads from PostgreSQL
        Note over BE,ES: es_sync worker queries PG read model
        BE->>ES: PUT /known_faces_index/_doc/{userId}<br/>{ user_id, username, face_embedding[1024], is_active: true }
        ES-->>BE: 201 indexed
    end

    Note over ES: User is now enrolled —<br/>future posts will trigger auto face-tag suggestions
```

### Key Events

| Step | Stream / API | Producer | Consumer |
|------|-------------|----------|---------|
| Register | `POST /api/auth/register` | React | Java |
| Upload picture | `POST /api/users/{id}/profile-picture` | React | Java |
| Trigger enrollment | `profile-picture-processing` | Java | `profile_enrollment` |
| Return embedding | `user-profile-face-embedding-results` | `profile_enrollment` | Java |
| Trigger ES sync | `es-sync-queue` | Java | `es_sync` |
| Index enrollment | ES `known_faces_index` | `es_sync` | Elasticsearch |

### Failure Modes

- **No face in picture:** `profile_enrollment` logs a warning and ACKs the message without publishing to `user-profile-face-embedding-results`. The user's profile is saved without a face embedding; they can re-upload at any time.
- **HuggingFace timeout:** `profile_enrollment` publishes to `ai-processing-dlq`. `dlq_processor` retries up to `DLQ_MAX_RETRIES` times.
- **Cloudinary unreachable:** `validate_url()` rejects private/loopback IPs via SSRF check before any download attempt.

---

## 2. Journey 2: Post Creation & Auto-Tagging

### Overview

A user creates a post with one or more images. The Java backend fans out AI processing jobs to six concurrent Python workers. After all ML results are collected, a `post_aggregator` merges the insights. The `face_matcher` runs KNN search against enrolled profiles and emits face-tag suggestions back to Java. The complete enriched post is then indexed into Elasticsearch.

### Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant FE as React Frontend
    participant BE as Java Backend
    participant CDN as Cloudinary
    participant REDIS as Redis Streams
    participant MP as media_preprocessor
    participant CM as content_moderation
    participant IT as image_tagger
    participant SR as scene_recognition
    participant IC as image_captioning
    participant FR as face_recognition
    participant FM as face_matcher
    participant PA as post_aggregator
    participant HF as HuggingFace API
    participant ES as Elasticsearch
    participant PG as PostgreSQL

    User->>FE: Compose post + attach images
    FE->>CDN: Upload images (direct)
    CDN-->>FE: { mediaUrls[] }
    FE->>BE: POST /api/posts<br/>{ title, body, mediaUrls[] }
    BE->>PG: INSERT post, INSERT media_assets
    BE-->>FE: 201 { postId }
    FE-->>User: Post published ✓

    loop For each mediaUrl
        BE->>REDIS: XADD post-image-processing<br/>{ postId, mediaId, mediaUrl, correlationId }
    end

    Note over REDIS,FM: Six consumer groups read independently — fan-out

    par media_preprocessor
        REDIS->>MP: XREADGROUP media-preprocessor-group
        MP->>CDN: GET mediaUrl (download once)
        CDN-->>MP: image bytes
        MP->>REDIS: XADD ml-inference-tasks<br/>{ postId, mediaId, localFilePath, correlationId }
        MP->>REDIS: XACK post-image-processing
    and content_moderation
        REDIS->>CM: XREADGROUP content-moderation-group
        CM->>HF: NSFW / safety classification
        HF-->>CM: { isSafe, confidence }
        CM->>REDIS: XADD ml-insights-results<br/>{ service: "moderation", isSafe, moderationConfidence }
        CM->>REDIS: XACK post-image-processing
    and image_tagger
        REDIS->>IT: XREADGROUP image-tagger-group
        IT->>HF: Zero-shot tagging
        HF-->>IT: { tags[] }
        IT->>REDIS: XADD ml-insights-results<br/>{ service: "tagging", tags }
        IT->>REDIS: XACK post-image-processing
    and scene_recognition
        REDIS->>SR: XREADGROUP scene-recognition-group
        SR->>HF: Zero-shot scene classification
        HF-->>SR: { scenes[] }
        SR->>REDIS: XADD ml-insights-results<br/>{ service: "scene_recognition", scenes }
        SR->>REDIS: XACK post-image-processing
    and image_captioning
        REDIS->>IC: XREADGROUP image-captioning-group
        IC->>HF: Image-to-text captioning
        HF-->>IC: { caption }
        IC->>REDIS: XADD ml-insights-results<br/>{ service: "image_captioning", caption }
        IC->>REDIS: XACK post-image-processing
    and face_recognition
        REDIS->>FR: XREADGROUP face-recognition-group
        FR->>HF: Face detection + embedding extraction
        HF-->>FR: { faces[{ faceId, bbox, embedding[1024], confidence }] }
        FR->>REDIS: XADD face-detection-results<br/>{ mediaId, postId, facesDetected, faces[], correlationId }
        FR->>REDIS: XACK post-image-processing
    end

    Note over REDIS,FM: face_matcher picks up face-detection-results
    REDIS->>FM: XREADGROUP face-matcher-group
    loop For each detected face
        FM->>ES: KNN search known_faces_index<br/>{ query_vector: embedding, k:1, filter: is_active:true }
        ES-->>FM: { _score, user_id, username }
        alt score >= KNN_CONFIDENCE_THRESHOLD (0.85)
            FM->>REDIS: XADD face-recognition-results<br/>{ mediaId, postId, faceId, suggestedUserId,<br/>  matchedUsername, confidenceScore (float), correlationId }
        end
    end
    FM->>REDIS: XACK face-detection-results

    Note over BE,PA: Java collects ML results, then triggers aggregation
    BE->>REDIS: XREADGROUP ml-insights-results (4 results per media)
    BE->>PG: UPDATE read_model_media_search (tags, caption, scenes, isSafe)
    BE->>REDIS: XREADGROUP face-detection-results
    BE->>PG: UPDATE read_model_media_search (detected_user_ids)
    BE->>REDIS: XREADGROUP face-recognition-results
    BE->>PG: INSERT face_tag_suggestions (pending)
    BE->>REDIS: XADD post-aggregation-trigger<br/>{ postId, allMediaIds[], totalMedia, correlationId }

    REDIS->>PA: XREADGROUP post-aggregator-group
    PA->>PA: Merge insights from all media:<br/>deduplicate tags/scenes, sum faces,<br/>AND isSafe verdicts, infer event type
    PA->>REDIS: XADD post-insights-enriched<br/>{ postId, aggregatedTags, aggregatedScenes,<br/>  totalFaces, isSafe, inferredEventType,<br/>  combinedCaption, ... }
    PA->>REDIS: XACK post-aggregation-trigger

    BE->>REDIS: XREADGROUP post-insights-enriched
    BE->>PG: UPDATE read_model_post_search
    BE->>REDIS: XADD es-sync-queue<br/>{ indexType: "post_search", documentId: postId }
    BE->>REDIS: XADD es-sync-queue<br/>{ indexType: "media_search", documentId: mediaId } (per media)
    REDIS->>BE: es_sync worker reads PG, indexes to ES
    BE->>ES: PUT /post_search/_doc/{postId}
    BE->>ES: PUT /media_search/_doc/{mediaId}
    ES-->>BE: 201 indexed

    FE->>User: Post appears in feed with AI tags and captions
    Note over FE,User: Face-tag notification shown<br/>if suggestedUserId matched a followed user
```

### Key Events

| Step | Stream | Producer | Consumer |
|------|--------|----------|---------|
| Trigger ML pipeline | `post-image-processing` | Java | 6 Python workers (fan-out) |
| Pre-fetch image | `ml-inference-tasks` | `media_preprocessor` | *(pending TD-1)* |
| ML results | `ml-insights-results` | 4 ML workers | Java |
| Face embeddings | `face-detection-results` | `face_recognition` | `face_matcher` + Java |
| Face-tag suggestions | `face-recognition-results` | `face_matcher` | Java |
| Aggregate insights | `post-aggregation-trigger` | Java | `post_aggregator` |
| Enriched post | `post-insights-enriched` | `post_aggregator` | Java |
| Index to ES | `es-sync-queue` | Java | `es_sync` |

### KNN Threshold

`face_matcher` uses `KNN_CONFIDENCE_THRESHOLD` (default `0.85`). Only faces exceeding this cosine similarity score against `known_faces_index` generate a `face-recognition-results` event. Java creates a **pending** tag suggestion requiring user confirmation.

---

## 3. Journey 3: Media Discovery & Semantic Search

### Overview

A user searches for media using a keyword query. The Java backend queries Elasticsearch against the `media_search` index (enriched with AI-generated captions, tags, and scene classifications written during Journey 2) and returns ranked, AI-enhanced results.

### Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant FE as React Frontend
    participant BE as Java Backend
    participant PG as PostgreSQL
    participant ES as Elasticsearch

    User->>FE: Enter search query<br/>"beach sunset people"
    FE->>BE: GET /api/search/media?q=beach+sunset+people&page=0&size=20
    BE->>ES: Multi-match query on media_search index<br/>fields: [ai_caption^3, ai_tags^2, ai_scenes^2,<br/>post_title, uploader_username]<br/>filter: is_safe:true
    ES-->>BE: Ranked hits [{ mediaId, _score, _source }]

    BE->>PG: SELECT * FROM read_model_media_search<br/>WHERE media_id IN (hit_ids)
    PG-->>BE: Full media records (URLs, user info, engagement counts)

    BE-->>FE: 200 Page<MediaResultDTO><br/>{ mediaId, mediaUrl, aiCaption, aiTags[],<br/>  aiScenes[], uploaderUsername, reactionCount, ... }
    FE-->>User: Rendered search results with AI captions and tags

    Note over User,FE: User narrows search by tag filter

    User->>FE: Click tag filter: "outdoor"
    FE->>BE: GET /api/search/media?q=beach+sunset&tags[]=outdoor&page=0
    BE->>ES: Bool query: must { multi_match } + filter { terms { ai_tags: ["outdoor"] } }
    ES-->>BE: Filtered ranked hits
    BE-->>FE: 200 filtered results
    FE-->>User: Narrowed results shown

    Note over User,FE: User clicks "Find photos with me"

    User->>FE: Navigate to /search/faces
    FE->>BE: GET /api/search/faces?userId={myUserId}
    BE->>ES: Term query on face_search index<br/>{ detected_user_ids: myUserId }
    ES-->>BE: All media where user was auto-tagged
    BE->>PG: Enrich with post titles and uploader info
    BE-->>FE: 200 List<MediaResultDTO>
    FE-->>User: Gallery of confirmed + suggested face-tagged photos

    Note over User,FE: KNN-based content recommendation

    User->>FE: Visit post recommendations page
    FE->>BE: GET /api/recommendations?page=0&size=10
    BE->>ES: KNN search on recommendations_knn index<br/>{ query_vector: userAffinityVector, k: 10 }
    ES-->>BE: Top-k recommended post IDs
    BE->>PG: SELECT posts WHERE post_id IN (recommended_ids)
    PG-->>BE: Enriched post records
    BE-->>FE: 200 Page<PostDTO>
    FE-->>User: Personalised "You might like" feed
```

### Elasticsearch Query Patterns

| Search Type | Index | Query Strategy | Key Boosting |
|------------|-------|---------------|-------------|
| Full-text media search | `media_search` | `multi_match` + `is_safe: true` filter | `ai_caption` ×3, `ai_tags` ×2, `ai_scenes` ×2 |
| Tag-filtered search | `media_search` | Bool `must` + `terms` filter on `ai_tags` | — |
| Post-level search | `post_search` | `multi_match` on title, caption, tags | `inferred_event_type` match |
| User discovery | `user_search` | `multi_match` on username, department | — |
| Face search | `face_search` | `term` on `detected_user_ids` | — |
| Face KNN | `known_faces_index` | `knn` on `face_embedding` (cosine, 1024-dim) | `is_active: true` filter |
| Recommendations | `recommendations_knn` | `knn` on `content_embedding` | User affinity vector |

### Data Flow That Enables Search

All search results are powered by AI enrichment written during Journey 2. The chain is:

```
Post uploaded  
  → post-image-processing  
    → [content_moderation, image_tagger, scene_recognition, image_captioning, face_recognition]  
      → ml-insights-results + face-detection-results  
        → post_aggregator → post-insights-enriched  
          → es-sync-queue  
            → es_sync (reads PostgreSQL read model, writes to Elasticsearch)  
              → media_search / post_search indices  
                → Search API responds with AI-enhanced results
```

The typical end-to-end latency from upload to searchability is **15–45 seconds** under normal load, bounded by HuggingFace inference round-trips.
