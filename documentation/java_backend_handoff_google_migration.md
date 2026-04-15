# Java Backend Handoff — Google AI Migration & Open Pipeline Gaps

> **Audience:** Java / Spring Boot developer  
> **Date:** April 2026  
> **Context:** The Python AI worker fleet has been fully migrated from HuggingFace to Google Cloud AI (Vertex AI Multimodal Embeddings, Gemini Vision, Cloud Vision Face Detection). This migration has two direct consequences for the Java backend that must be addressed, on top of the five open pipeline gaps documented in `backend_handoff_post1_audit.md`. This document supersedes that earlier file and consolidates everything the Java developer needs to action.

---

## Table of Contents

1. [What Changed on the Python Side](#1-what-changed-on-the-python-side)
2. [Critical: Image Embedding Dimension Change 512 → 1408](#2-critical-image-embedding-dimension-change-512--1408)
3. [Critical: Face Embeddings Are Now Empty (Google Vision Limitation)](#3-critical-face-embeddings-are-now-empty-google-vision-limitation)
4. [B1 — `media_detected_faces` Empty: `FaceDetectionConsumer` Not Persisting](#4-b1--media_detected_faces-empty-facedetectionconsumer-not-persisting)
5. [B2 — `read_model_post_search` + `post_search` ES Empty: `PostInsightsEnrichedConsumer` Not Writing](#5-b2--read_model_post_search--post_search-es-empty-postinsightsenrichedconsumer-not-writing)
6. [B3 — `media_search` ES 404: Java Media Sync Not Triggered After ML Completion](#6-b3--media_search-es-404-java-media-sync-not-triggered-after-ml-completion)
7. [B4 — `recommendations_knn` ES 404: Unblocked by Embedding Fix](#7-b4--recommendations_knn-es-404-unblocked-by-embedding-fix)
8. [B5 — `feed_personalized` ES Returns 0 Hits: camelCase Field Name Mismatch](#8-b5--feed_personalized-es-returns-0-hits-camelcase-field-name-mismatch)
9. [Open Security & Reliability GAPs (GAP-8 through GAP-18)](#9-open-security--reliability-gaps-gap-8-through-gap-18)
10. [Full Redis Stream Contract Reference](#10-full-redis-stream-contract-reference)
11. [Recommended Fix Order](#11-recommended-fix-order)
12. [Verification Runbook](#12-verification-runbook)

---

## 1. What Changed on the Python Side

| Service | Was (HuggingFace) | Now (Google Cloud) | Impact on Java |
|---------|-------------------|--------------------|----------------|
| `image_embedding` | CLIP `openai/clip-vit-base-patch32` — 512-dim vectors | Vertex AI `multimodalembedding@001` — **1408-dim** vectors | `read_model_recommendations_knn.image_embedding` must accommodate 1408 floats; any Java hardcoded `512` dim breaks storage and KNN queries |
| `content_moderation` | HF NSFW classifier | Google Vision **SafeSearch** | Same wire format; `isSafe` / `moderationConfidence` fields unchanged |
| `image_tagger` | HF ViT classifier | Google **Gemini** multimodal | Same wire format; `tags` JSON array unchanged |
| `scene_recognition` | HF Places365 classifier | Google **Gemini** multimodal | Same wire format; `scenes` JSON array unchanged |
| `image_captioning` | HF BLIP | Google **Gemini** multimodal | Same wire format; `caption` string unchanged |
| `face_recognition` | HF custom face API returning 1024-dim embeddings | Google Cloud **Vision Face Detection** — **returns EMPTY embeddings** | `FaceDetectionConsumer` guard logic breaks; faces not persisted (see section 3 and 4) |
| `profile_enrollment` | HF face API — 1024-dim embeddings | Google Cloud Vision — **empty embeddings** | `UserProfileFaceEmbeddingConsumer` receives `faceEmbedding: "[]"`; `known_faces_index` and `face_matcher` pipeline disabled until a dedicated embedding step is added |

---

## 2. Critical: Image Embedding Dimension Change 512 → 1408

### Root cause
The previous HuggingFace CLIP model produced **512-dimensional** float vectors. Vertex AI `multimodalembedding@001` produces **1408-dimensional** vectors. The Elasticsearch `recommendations_knn` index mapping has already been updated (`es_mappings/recommendations_knn.json`, `"dims": 1408`), but Java-side code still expects 512 dims.

### Where to fix in Java

**1. `ReadModelUpdateService.updateRecommendationsKnnReadModel()`**

This method receives the `imageEmbedding` from the `ml-insights-results` stream (service = `"image_embedding"`) and writes to `read_model_recommendations_knn`. Find any assertion, truncation, or validation that checks for dim == 512 and remove or replace with 1408:

```java
// BAD — old HF CLIP assumption
if (embedding.size() != 512) {
    log.warn("Unexpected embedding size {}, expected 512", embedding.size());
    return;  // ← This silent guard blocks ALL Google embeddings
}

// GOOD — updated for Vertex AI
if (embedding.size() != 1408) {
    log.warn("Unexpected embedding size {}, expected 1408", embedding.size());
}
// Continue processing regardless; log the warning but do not abort
```

**2. PostgreSQL column type**

Confirm `read_model_recommendations_knn.image_embedding` is stored as `float[]` or `vector(1408)` (if using pgvector), not `vector(512)`. Run:

```sql
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_name = 'read_model_recommendations_knn'
  AND column_name = 'image_embedding';
```

If it's `vector(512)`, run a migration:
```sql
ALTER TABLE read_model_recommendations_knn
    ALTER COLUMN image_embedding TYPE float[];
-- or, if using pgvector:
ALTER TABLE read_model_recommendations_knn
    ALTER COLUMN image_embedding TYPE vector(1408)
        USING image_embedding::vector(1408);
```

**3. Elasticsearch index recreation**

If the live `recommendations_knn` ES index was created with the old 512-dim mapping, it must be dropped and recreated:

```bash
# Run on the server (replace <password> with ELASTICSEARCH_PASSWORD)
curl -u elastic:<password> -X DELETE http://localhost:9200/recommendations_knn
curl -u elastic:<password> -X PUT http://localhost:9200/recommendations_knn \
  -H "Content-Type: application/json" \
  -d @~/Kaleidoscope/es_mappings/recommendations_knn.json
```

**4. KNN query dimension**

Any Java `NativeQuery` doing `knnSearch` against `recommendations_knn` must pass a 1408-dim query vector, not 512. Update vector size in search service classes.

### Verify

```sql
-- After a post is processed, confirm embedding stored correctly
SELECT media_id,
       array_length(image_embedding, 1) AS dims,
       image_embedding IS NOT NULL        AS has_embedding
FROM read_model_recommendations_knn
ORDER BY media_id DESC
LIMIT 5;
-- Expected: dims = 1408
```

---

## 3. Critical: Face Embeddings Are Now Empty (Google Vision Limitation)

### What happened

Google Cloud Vision Face Detection API returns bounding boxes, landmarks, and confidence scores, but **does not return face embedding vectors**. The `GoogleFaceProvider` therefore publishes each face with `"embedding": []` in the `face-detection-results` stream. The `profile_enrollment` service similarly publishes `"faceEmbedding": "[]"` to `user-profile-face-embedding-results`.

### Affected Java consumers

| Consumer | Impact |
|----------|--------|
| `FaceDetectionConsumer` | Receives `embedding: []` per face. If it guards on `!embedding.isEmpty()` before persisting, **all faces are silently dropped**. |
| `UserProfileFaceEmbeddingConsumer` | Receives `faceEmbedding: "[]"`. If it parses a non-empty array before updating `known_faces_index`, the profile enrollment silently fails. |

### Recommended short-term fix

**For `FaceDetectionConsumer`:** persist faces even with empty embeddings. Store bounding box, confidence, and face_id. Only skip if `facesDetected == 0`. Face search and face matching features will be unavailable until embeddings are added back, but at least the face count and bounding boxes will be persisted and visible:

```java
for (FaceObject face : faces) {
    MediaDetectedFace entity = new MediaDetectedFace();
    entity.setMediaId(mediaId);
    entity.setFaceId(face.getFaceId());
    entity.setBbox(face.getBbox());
    entity.setConfidence(face.getConfidence());
    // Store null/empty embedding — do NOT abort on empty
    entity.setEmbedding(
        face.getEmbedding() != null && !face.getEmbedding().isEmpty()
            ? face.getEmbedding().stream().mapToDouble(Float::doubleValue).toArray()
            : null
    );
    mediaDetectedFacesRepo.save(entity);
}
```

**For `UserProfileFaceEmbeddingConsumer`:** skip the `known_faces_index` write (since there is no embedding to store), but still acknowledge the message and log a warning. Do not throw:

```java
List<Float> embedding = objectMapper.readValue(msg.getFaceEmbedding(),
    new TypeReference<List<Float>>(){});

if (embedding == null || embedding.isEmpty()) {
    log.warn("Profile enrollment for userId={} produced empty face embedding " +
             "(Google Vision does not return face vectors). " +
             "Skipping known_faces_index update.", msg.getUserId());
    // XACK the message — do not let it re-enter PEL
    return;
}
// Normal path continues
```

### Recommended long-term fix (face search restore path)

Google Vision provides bounding boxes per face. To restore face embeddings and re-enable face search/matching, add a dedicated embedding step after face detection. Options:
- **Option A:** Use Google Vertex AI `multimodalembedding@001` — crop each face from the image using the bbox, pass the cropped bytes, and use the resulting 1408-dim vector as the face embedding.
- **Option B:** Use a separate face-specialised model (e.g. ArcFace via a self-hosted container) alongside Google Vision detection.

This is a Python-side change (a new step in `face_recognition/worker.py` or a new `face_embedding` service). No Java contract change is required — the `faces[].embedding` field in `face-detection-results` simply becomes populated again.

---

## 4. B1 — `media_detected_faces` Empty: `FaceDetectionConsumer` Not Persisting

### Live evidence (post_id=6, media_id=6, 2026-04-15)
- Python `face_recognition` worker published `facesDetected: "5"` to `face-detection-results`.
- `SELECT COUNT(*) FROM media_detected_faces WHERE media_id = 6` → **0 rows**.

### Diagnosis

```bash
docker logs kaleidoscope-app 2>&1 \
  | grep -iE "FaceDetection|face-detection-results|media_detected_faces" \
  | head -60
```

Look for: exception stacktraces, a silent `facesDetected == 0` guard skipping persistence, or an `embedding.isEmpty()` guard (especially relevant after the Google migration — see section 3).

### Expected consumer path

```
face-detection-results (Redis Stream)
  → FaceDetectionConsumer.onMessage(FaceDetectionResultMessage msg)
      → int count = Integer.parseInt(msg.getFacesDetected())
      → if (count == 0) return;  // only skip if truly zero faces
      → List<FaceObject> faces = objectMapper.readValue(msg.getFaces(),
            new TypeReference<List<FaceObject>>(){})
      → for (FaceObject f : faces):
            // Do NOT gate on f.getEmbedding().isEmpty() — see section 3
            mediaDetectedFacesRepo.save(
                new MediaDetectedFace(mediaId, f.getFaceId(),
                                      f.getBbox(), f.getEmbedding(),  // may be []
                                      f.getConfidence()))
      → mediaAiInsightsRepo.appendServiceCompleted(mediaId, "face_detection")
      → if (allServicesCompleted(mediaId)):
            esSyncPublisher.publish("face_search", mediaId)
```

### Wire format of `face-detection-results`

All field values are strings in Redis:

| Field | On wire | Parse as |
|-------|---------|----------|
| `mediaId` | `"6"` | `Long.parseLong(...)` |
| `postId` | `"6"` | `Long.parseLong(...)` |
| `facesDetected` | `"5"` | `Integer.parseInt(...)` |
| `faces` | JSON array string | `objectMapper.readValue(msg.getFaces(), new TypeReference<List<FaceObject>>(){})` |
| `correlationId` | UUID string | plain string |
| `timestamp` | ISO-8601 | plain string |
| `version` | `"1"` | plain string |

**Face object schema** (each element in the `faces` JSON array):

| Field | Type | Notes |
|-------|------|-------|
| `faceId` | string (UUID) | Unique per face in this image |
| `bbox` | `[x_min, y_min, x_max, y_max]` | Pixel coordinates from Google Vision |
| `confidence` | float 0–1 | Detection confidence |
| `embedding` | float array | **Now empty `[]` with Google Vision** — see section 3 |

---

## 5. B2 — `read_model_post_search` + `post_search` ES Empty: `PostInsightsEnrichedConsumer` Not Writing

### Live evidence (post_id=6, 2026-04-15)
- Java backend published `post-aggregation-trigger` for `postId=6`.
- `post_aggregator` published to `post-insights-enriched`.
- `SELECT * FROM read_model_post_search WHERE post_id = 6` → NULL.
- `GET /post_search/_doc/6` → 404.
- `GET /post_search/_count` → `count: 0` (index is permanently empty).

### Step 1 — Confirm `post_aggregator` ran to completion

```bash
docker logs post_aggregator 2>&1 \
  | grep -E "postId.*6|1212c3fa|Published enriched insights" \
  | head -40
```

If you do not see `"Published enriched insights"` for `post_id=6`, the `post_aggregator` timed out waiting for `image_embedding` results. With the Google migration now deployed and `image_embedding` working, re-processing the DLQ will unblock this.

To drain the DLQ for the failed `image_embedding` message from the test post:

```bash
docker exec redis redis-cli -a kaleidoscope1-reddis \
  XRANGE ai-processing-dlq - + COUNT 20
# Find the entry with serviceName="image-embedding", correlationId=1212c3fa...
# Then re-publish it to ml-inference-tasks or trigger a new post upload
```

### Step 2 — Fix `PostInsightsEnrichedConsumer`

Once `post-insights-enriched` carries a valid message, the consumer must:

```java
// PostInsightsEnrichedConsumer.onMessage(PostInsightsEnrichedMessage msg)

// 1. Upsert the read model
ReadModelPostSearch row = new ReadModelPostSearch();
row.setPostId(Long.parseLong(msg.getPostId()));
row.setAggregatedTags(objectMapper.readValue(msg.getAggregatedTags(), List.class));
row.setAggregatedScenes(objectMapper.readValue(msg.getAggregatedScenes(), List.class));
row.setCombinedCaption(msg.getCombinedCaption());
row.setInferredEventType(msg.getInferredEventType());
row.setIsSafe(Boolean.parseBoolean(msg.getIsSafe()));
row.setTotalFaces(Integer.parseInt(msg.getTotalFaces()));
row.setMediaCount(Integer.parseInt(msg.getMediaCount()));
postSearchReadModelRepo.save(row);  // or upsert

// 2. Directly save to Elasticsearch via Spring Data ES
// (es_sync does NOT own post_search — Java must write it directly)
PostSearchDocument doc = mapToEsDoc(row);
postSearchEsRepo.save(doc);

// 3. Optional: also publish es-sync-queue if you have a sync path
// esSyncPublisher.publish("post_search", msg.getPostId());
// Note: Python es_sync explicitly excludes post_search from its INDEX_MAPPING
```

### Wire format of `post-insights-enriched`

All field values are strings in Redis:

| Field | Parse as |
|-------|----------|
| `postId` | `Long.parseLong(...)` |
| `aggregatedTags` | `objectMapper.readValue(..., List<String>.class)` |
| `aggregatedScenes` | `objectMapper.readValue(..., List<String>.class)` |
| `allAiTags` | `objectMapper.readValue(..., List<String>.class)` |
| `allAiScenes` | `objectMapper.readValue(..., List<String>.class)` |
| `totalFaces` | `Integer.parseInt(...)` |
| `mediaCount` | `Integer.parseInt(...)` |
| `isSafe` | `Boolean.parseBoolean(...)` |
| `moderationConfidence` | `Double.parseDouble(...)` |
| `combinedCaption` | plain string |
| `inferredEventType` | plain string (`"general"`, `"wedding"`, `"beach_party"`, etc.) |
| `hasMultipleImages` | `Boolean.parseBoolean(...)` |
| `correlationId` | plain string |
| `timestamp` | ISO-8601 string |
| `version` | `"1"` |

---

## 6. B3 — `media_search` ES 404: Java Media Sync Not Triggered After ML Completion

### Live evidence (post_id=6, media_id=6)
- `read_model_media_search` has a row for `media_id=6` (caption, tags, scenes, `is_safe=true`, `image_embedding=null`).
- `GET /media_search/_doc/6` → `found: true` (**this gap appears resolved for Test-1** — `media_search` indexed successfully at `_version: 4`).

If you encounter this on future posts, the fix path is:

### Fix
After `MediaAiInsightsConsumer` sets `media_ai_insights.status = COMPLETED` for a given `mediaId`, it must immediately save the read model row to Elasticsearch:

```java
// In MediaAiInsightsConsumer (or a downstream completion handler)
ReadModelMediaSearch readModel = mediaSearchReadModelRepo.findByMediaId(mediaId);
if (readModel != null) {
    mediaSearchEsRepo.save(mapToEsDoc(readModel));
    log.info("media_search ES doc saved for mediaId={}", mediaId);
} else {
    log.warn("No read_model_media_search row for mediaId={} at COMPLETED — sync skipped", mediaId);
}
```

Note: Python `es_sync` does **not** own `media_search`. Java must write this index directly. Publishing to `es-sync-queue` with `indexType=media_search` has no effect on the Python side.

---

## 7. B4 — `recommendations_knn` ES 404: Unblocked by Embedding Fix

### Dependency chain

```
image_embedding worker (Google Vertex AI, 1408-dim)
  → publishes imageEmbedding (1408-dim float list) to ml-insights-results
  → MediaAiInsightsConsumer receives service="image_embedding"
      → ReadModelUpdateService.updateRecommendationsKnnReadModel(mediaId, embedding)
          → UPSERT read_model_recommendations_knn (media_id, image_embedding)  ← dim must be 1408
          → esSyncPublisher.publish("recommendations_knn", mediaId)
  → Python es_sync reads read_model_recommendations_knn
  → Writes recommendations_knn ES doc (imageEmbedding field, 1408-dim dense_vector)
```

### Live evidence (post_id=6, media_id=6)
- `es_sync` logged `"Document not found in PostgreSQL"` for `recommendations_knn / document_id 6` — because `read_model_recommendations_knn` has no row (embedding never arrived before Google migration).
- With Google `image_embedding` now working, the fix is: **restart all containers** and trigger a new test post. The embedding will flow end-to-end.

### Java-side check

```bash
docker logs kaleidoscope-app 2>&1 \
  | grep -iE "updateRecommendationsKnn|recommendations_knn|image_embedding" \
  | head -40
```

If `updateRecommendationsKnnReadModel()` is still silently returning (dim guard), see section 2 for the fix.

### Verify after fix

```sql
SELECT media_id,
       array_length(image_embedding, 1) AS dims,
       image_embedding IS NOT NULL        AS has_embedding
FROM read_model_recommendations_knn
ORDER BY media_id DESC LIMIT 5;
-- Expected: dims = 1408, has_embedding = true
```

```bash
curl -u elastic:<password> http://localhost:9200/recommendations_knn/_doc/6
# Expected: found: true, imageEmbedding present
```

---

## 8. B5 — `feed_personalized` ES Returns 0 Hits: camelCase Field Name Mismatch

### Root cause
Python `es_sync` converts all PostgreSQL column names from `snake_case` → `camelCase` before writing to Elasticsearch. So `post_id` is stored as `postId`, `media_id` as `mediaId`, `is_safe` as `isSafe`, etc.

### Fix for Java consumers
Any Java code querying `feed_personalized` (or any Python `es_sync`-owned index) must use camelCase field names:

```java
// BAD — uses Postgres column names
NativeQuery query = NativeQuery.builder()
    .withQuery(q -> q.term(t -> t.field("post_id").value(postId)))
    .build();

// GOOD — uses ES camelCase field name
NativeQuery query = NativeQuery.builder()
    .withQuery(q -> q.term(t -> t.field("postId").value(postId)))
    .build();
```

### Full field name mapping for Python es_sync-owned indices

`es_sync` owns: `feed_personalized`, `face_search`, `recommendations_knn`, `known_faces_index`.

| PostgreSQL column | Elasticsearch field |
|-------------------|---------------------|
| `post_id` | `postId` |
| `media_id` | `mediaId` |
| `user_id` | `userId` |
| `image_embedding` | `imageEmbedding` |
| `face_embedding` | `faceEmbedding` |
| `is_safe` | `isSafe` |
| `created_at` | `createdAt` |
| `updated_at` | `updatedAt` |
| `face_id` | `faceId` |
| `suggested_user_id` | `suggestedUserId` |
| `detection_confidence` | `detectionConfidence` |

Java-owned indices (`media_search`, `post_search`, `user_search`) are written directly by Spring Data Elasticsearch `@Document` classes and use whatever field names are configured in those entity classes.

---

## 9. Open Security & Reliability GAPs (GAP-8 through GAP-18)

These are pre-existing items from the April 2026 audit, unrelated to the Google migration. Full details are in `audit_report_and_tech_debt.md`.

### P0 — Security (fix in Sprint 1)

**GAP-8 — No rate limiting on auth endpoints**
- Files: `SecurityConfig.java`, `pom.xml`
- Fix: Add `bucket4j-spring-boot-starter` with Redis-backed rate limiter. Limits: 5 login attempts / 15 min per IP, 3 registrations / hour.

```xml
<!-- pom.xml -->
<dependency>
    <groupId>com.github.vladimir-bukhtoyarov</groupId>
    <artifactId>bucket4j-spring-boot-starter</artifactId>
    <version>8.x</version>
</dependency>
```

**GAP-9 — Weak email verification tokens**
- File: `UserRegistrationServiceImpl.java`
- Current (insecure): `UUID.randomUUID().toString().substring(0, 10)` — ~47 bits
- Fix:
```java
byte[] bytes = new byte[32];
new SecureRandom().nextBytes(bytes);
String token = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
// Store SHA-256(token) in DB; set expiry = now + 24h; enforce single-use
```

**GAP-10 — `MediaAssetTracker` race condition**
- File: `PostServiceImpl.java` lines 154–164
- Current: read-check-write pattern, not atomic under concurrent completions
- Fix: Add `@Version` on `MediaAssetTracker` entity for optimistic locking, or replace with atomic Redis `INCR`:
```java
// Redis atomic counter pattern
Long completedCount = redisTemplate.opsForValue()
    .increment("media_tracker:" + postId);
if (completedCount.equals(Long.valueOf(expectedCount))) {
    triggerPostAggregation(postId);
}
```

**GAP-11 — Near-zero test coverage**
- Files: `backend/src/test/`
- Fix: Sprint to add `@SpringBootTest` integration tests for Redis consumer chain using embedded Redis; unit tests for `PostServiceImpl`, `AuthService`, and all consumer classes with Mockito; contract tests validating DTO field names match Python counterparts.

**GAP-16 — Access token in `localStorage` (XSS vulnerability)**
- Files: `src/store/authSlice.ts`, axios interceptor (React)
- Fix: Remove token from `localStorage`. Keep in Redux memory only. Issue refresh token as HTTP-only `SameSite=Strict` cookie. Reload = call `/api/auth/refresh` for a new in-memory token.

### P1 — Reliability (fix in Sprint 2)

**GAP-12 — No circuit breakers on Redis / ES calls**
- Files: All `*Consumer.java` and `*Publisher.java`
- Fix: Add `resilience4j-spring-boot3`. Annotate `RedisTemplate.opsForStream()` calls with `@CircuitBreaker(name="redis")` and ES calls with `@CircuitBreaker(name="elasticsearch")`. Config: `slidingWindowSize=10`, `failureRateThreshold=50`, `waitDurationInOpenState=30s`.

**GAP-13 — No backend dead letter queue handling**
- Files: `MediaAiInsightsConsumer.java`, `FaceDetectionConsumer.java`, `PostInsightsConsumer.java`, `FaceRecognitionConsumer.java`, `UserProfileFaceEmbeddingConsumer.java`
- Fix: Check `XPENDING` delivery count per message. After 3 failed deliveries, publish to a `java-processing-dlq` stream and `XACK` the original. Without this, poison messages block the PEL indefinitely.

**GAP-14 — `PostServiceImpl` god-class (658+ lines)**
- File: `PostServiceImpl.java`
- Fix: Extract into `PostCreationService`, `PostQueryService`, `PostUpdateService`, `MediaAiOrchestrationService`. Bind via a thin `PostFacadeService`.

### P1 — React Frontend (separate team action)

**GAP-17 — Debug `console.log` in production bundle**
- Files: `EnhancedBodyInput.tsx`, `filterPosts.ts`
- Fix: Remove all `console.log`. Add ESLint `no-console` rule.

**GAP-18 — No React error boundaries on route layouts**
- Files: `app/(auth)/layout.tsx`, `app/(unauth)/layout.tsx`
- Fix: Wrap route group layouts in an `ErrorBoundary` component with fallback UI. Use Next.js `error.tsx` convention.

### P2 — Code Correctness

**GAP-15 — Incorrect `@Transactional(readOnly=true)` on a write method**
- File: `ElasticsearchStartupSyncService.java`
- Fix: Remove `readOnly=true` from the annotation, or remove `@Transactional` entirely if the method performs no DB writes.

---

## 10. Full Redis Stream Contract Reference

### Java → Python (Inbound to AI layer)

#### `post-image-processing`
Producers: Java backend. Consumers: `media_preprocessor`, `content_moderation`, `image_tagger`, `scene_recognition`, `image_captioning`, `face_recognition`.

| Field | Type | Required |
|-------|------|----------|
| `postId` | string | ✅ |
| `mediaId` | string | ✅ |
| `mediaUrl` | string | ✅ (was `imageUrl` — fixed in Phase C GAP-5) |
| `correlationId` | string | ✅ |

#### `profile-picture-processing`
Producer: Java. Consumer: `profile_enrollment`.

| Field | Type | Required |
|-------|------|----------|
| `userId` | string | ✅ |
| `imageUrl` | string | ✅ (was `profilePicUrl` — fixed in Phase C GAP-4) |
| `correlationId` | string | ✅ |

#### `post-aggregation-trigger`
Producer: Java. Consumer: `post_aggregator`.

| Field | Type | Required |
|-------|------|----------|
| `postId` | string | ✅ |
| `allMediaIds` | string (JSON array) | ✅ |
| `totalMedia` | string (integer) | ✅ |
| `mediaInsights` | string (JSON) | ❌ |
| `correlationId` | string | ❌ |

#### `es-sync-queue`
Producer: Java. Consumer: `es_sync`.

| Field | Type | Notes |
|-------|------|-------|
| `indexType` | string | `media_search` \| `face_search` \| `recommendations_knn` \| `feed_personalized` \| `known_faces_index` — **do not publish `post_search`, `user_search`, `media_search` here** (Java writes those directly) |
| `documentId` | string | Primary key from the read-model table |
| `operation` | string | `"index"` (default) or `"delete"` |

### Python → Java (Outbound from AI layer)

#### `ml-insights-results`
Producers: `content_moderation`, `image_tagger`, `scene_recognition`, `image_captioning`, `image_embedding`. Consumer: Java `MediaAiInsightsConsumer`.

| Field | Present when | Value |
|-------|-------------|-------|
| `mediaId` | Always | string |
| `postId` | Always | string |
| `service` | Always | `"moderation"` \| `"tagging"` \| `"scene_recognition"` \| `"image_captioning"` \| `"image_embedding"` |
| `isSafe` | Moderation only | `"true"` or `"false"` |
| `moderationConfidence` | Moderation only | float string |
| `tags` | Tagging only | JSON array string |
| `scenes` | Scene recognition only | JSON array string |
| `caption` | Captioning only | plain string |
| `imageEmbedding` | image_embedding only | JSON array string — **1408 floats** (was 512) |
| `correlationId` | Always | string |
| `timestamp` | Always | ISO-8601 |
| `version` | Always | `"1"` |

#### `face-detection-results`
Producer: `face_recognition`. Consumers: `face_matcher` (Python) + Java `FaceDetectionConsumer`.

| Field | Type | Notes |
|-------|------|-------|
| `mediaId` | string | |
| `postId` | string | |
| `facesDetected` | string (integer) | Parse with `Integer.parseInt` |
| `faces` | string (JSON array) | Each element: `{faceId, bbox:[x,y,x2,y2], confidence, embedding:[]}` — **`embedding` is now `[]` with Google Vision** |
| `correlationId` | string | |
| `timestamp` | ISO-8601 | |
| `version` | `"1"` | |

#### `user-profile-face-embedding-results`
Producer: `profile_enrollment`. Consumer: Java `UserProfileFaceEmbeddingConsumer`.

| Field | Type | Notes |
|-------|------|-------|
| `userId` | string | |
| `faceEmbedding` | string (JSON array) | **Now `"[]"` with Google Vision** — handle gracefully, do not throw |
| `correlationId` | string | |

#### `face-recognition-results`
Producer: `face_matcher`. Consumer: Java `FaceRecognitionConsumer`.

| Field | Type | Notes |
|-------|------|-------|
| `faceId` | string | |
| `mediaId` | string | |
| `postId` | string | |
| `suggestedUserId` | string | (was `matchedUserId` — fixed GAP-1) |
| `matchedUsername` | string | |
| `confidenceScore` | **float** (not string) | (was `confidence: str` — fixed GAP-7) |
| `correlationId` | string | |

#### `post-insights-enriched`
Producer: `post_aggregator`. Consumer: Java `PostInsightsConsumer`.

All fields are strings. See full field table in section 5 above.

### Global encoding rules

| Rule | Detail |
|------|--------|
| All Redis field values | UTF-8 strings |
| Numeric IDs | Always serialised as strings (`"6"`, not `6`) |
| Arrays / objects | JSON-encoded strings (e.g. `"[\"beach\",\"sunset\"]"`) |
| Booleans | `"true"` or `"false"` strings |
| `confidenceScore` in `FaceTagSuggestionDTO` | Native `float` (exception to the string rule) |
| Timestamps | ISO-8601 (`"2026-04-15T15:08:37Z"`) |
| `correlationId` | Mandatory on all inbound messages; echoed by all Python workers |
| Schema version | `version: "1"` on all outbound messages |

---

## 11. Recommended Fix Order

```
Priority  Item                                              Section
────────  ────────────────────────────────────────────────  ────────
P0 NEW    Fix image embedding 1408-dim guard in Java         §2
P0 NEW    Fix FaceDetectionConsumer empty-embedding guard    §3, §4
P0 NEW    Fix UserProfileFaceEmbeddingConsumer empty array   §3
P0 OPEN   PostInsightsEnrichedConsumer → write post_search   §5
P0 OPEN   Verify recommendations_knn after dim fix           §7
P0        Rate limiting on auth endpoints (GAP-8)            §9
P0        Weak verification tokens (GAP-9)                   §9
P0        MediaAssetTracker race condition (GAP-10)          §9
P0        Access token in localStorage (GAP-16)              §9
P1        Add circuit breakers — Redis/ES (GAP-12)           §9
P1        Backend DLQ handling in consumers (GAP-13)         §9
P1        camelCase ES field names in feed queries (B5)      §8
P1        React error boundaries (GAP-18)                    §9
P1        Remove console.log (GAP-17)                        §9
P2        Fix @Transactional readOnly annotation (GAP-15)    §9
P2        Extract PostServiceImpl god-class (GAP-14)         §9
P2        Test coverage sprint (GAP-11)                      §9
```

---

## 12. Verification Runbook

Run all commands on the droplet (`ssh root@165.232.179.167`), inside `~/Kaleidoscope/`.

### After deploying embedding dim fix

```bash
# 1. Trigger a new test post via the API, then:

# 2. Check image_embedding worker processed it
docker logs image_embedding --tail=50 | grep -E "dimensions|embedding|1408"
# Expected: "Generated embedding with 1408 dimensions for mediaId=X"

# 3. Confirm Java stored the row
# (connect to Neon DB or via es_sync container)
docker exec es_sync python3 -c "
import psycopg2, os
conn = psycopg2.connect(os.environ['SPRING_DATASOURCE_URL'].replace('jdbc:',''))
cur = conn.cursor()
cur.execute('SELECT media_id, array_length(image_embedding,1) FROM read_model_recommendations_knn ORDER BY media_id DESC LIMIT 3')
print(cur.fetchall())
"
# Expected: [(X, 1408), ...]

# 4. Confirm ES doc
curl -u elastic:kaleidoscope1-elastic \
  http://localhost:9200/recommendations_knn/_doc/<media_id>
```

### After deploying face persistence fix

```bash
docker logs kaleidoscope-app --tail=200 | grep -iE "FaceDetection|media_detected_faces|face.*persist"
# Should show: saved N faces for mediaId=X (no embedding guard exception)

# SQL check
docker exec es_sync python3 -c "
import psycopg2, os
conn = psycopg2.connect(os.environ['SPRING_DATASOURCE_URL'].replace('jdbc:',''))
cur = conn.cursor()
cur.execute('SELECT media_id, face_id, confidence FROM media_detected_faces ORDER BY id DESC LIMIT 10')
print(cur.fetchall())
"
```

### After deploying post_search fix

```bash
curl -u elastic:kaleidoscope1-elastic \
  http://localhost:9200/post_search/_count
# Expected: count > 0

curl -u elastic:kaleidoscope1-elastic \
  http://localhost:9200/post_search/_doc/<post_id>
# Expected: found: true
```

### Full pipeline smoke test

```bash
# Tail all relevant logs simultaneously
docker-compose -f docker-compose.prod.yml logs -f \
  image_embedding face_recognition post_aggregator es_sync 2>&1 \
  | grep -v "^$"
```

Create a new post via `POST /kaleidoscope/api/posts` and follow the correlation ID through all services. Expected happy path:

```
media_preprocessor  → Downloaded image, published to ml-inference-tasks
content_moderation  → Published result to ml-insights-results (service=moderation)
image_tagger        → Published result to ml-insights-results (service=tagging)
image_captioning    → Published result to ml-insights-results (service=image_captioning)
scene_recognition   → Published result to ml-insights-results (service=scene_recognition)
image_embedding     → Generated embedding with 1408 dimensions, published to ml-insights-results
face_recognition    → Published face-detection-results (N faces, embedding=[])
[Java backend]      → FaceDetectionConsumer: persisted N faces to media_detected_faces
[Java backend]      → MediaAiInsightsConsumer: COMPLETED, wrote read_model_recommendations_knn (1408-dim)
[Java backend]      → Published es-sync-queue: indexType=recommendations_knn
[Java backend]      → Published post-aggregation-trigger
post_aggregator     → Published enriched insights to post-insights-enriched
[Java backend]      → PostInsightsEnrichedConsumer: wrote read_model_post_search, saved to post_search ES
es_sync             → Synced recommendations_knn, feed_personalized, face_search
```
