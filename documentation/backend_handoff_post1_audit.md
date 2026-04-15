# Backend Handoff — Post Pipeline Gaps (post_id = 1 audit)

> **Audience:** Java / Spring Boot developer  
> **Context:** A full-stack audit of post_id=1 (title "test", media_id=1) on 2026-04-15 revealed five backend-owned gaps after the AI services pipeline ran successfully. This document describes each gap, its root cause, the expected fix, and the verification queries / log commands to confirm resolution.  
> **Pre-condition:** AI fix A1 (deploy `image_embedding` service) and A2 (face embedding dim correction) must be deployed first before B1 and B4 make sense to debug.

---

## B1 — `media_detected_faces` empty: `FaceDetectionConsumer` not persisting

### What happened
The Python `face_recognition` service detected **7 faces** for `mediaId=1`, `postId=1` at ~08:04:56 and published a well-formed message to the `face-detection-results` Redis Stream:

```
Stream: face-detection-results
Fields:
  mediaId        = "1"
  postId         = "1"
  facesDetected  = "7"
  faces          = "[{\"faceId\":\"...\",\"bbox\":[...],\"embedding\":[...1024 floats...],\"confidence\":0.97}, ...]"
  correlationId  = "71b74f92-1440-45af-bd0c-8e1ee2ed7771"
  timestamp      = "2026-04-15T08:04:56.xxxZ"
  version        = "1"
```

Despite this, `SELECT * FROM media_detected_faces WHERE media_id = 1` returns zero rows.

### Diagnosis
```bash
docker logs kaleidoscope-app 2>&1 | grep -i "FaceDetection\|face-detection-results\|media_detected_faces" | head -60
```

Look for the consumer acknowledgement, any exception stacktraces, or a silent no-op (e.g. `facesDetected == 0` guard skipping persistence).

### Expected consumer path
```
face-detection-results (Redis Stream)
  → FaceDetectionConsumer.onMessage(FaceDetectionResultMessage msg)
      → int count = Integer.parseInt(msg.getFacesDetected())
      → if (count == 0) return;   // ← check this guard is not erroneously blocking
      → List<FaceObject> faces = objectMapper.readValue(msg.getFaces(), ...)
      → for (FaceObject f : faces):
            mediaDetectedFacesRepo.save(
                new MediaDetectedFace(msg.getMediaId(), f.getFaceId(),
                                      f.getBbox(), f.getEmbedding(), f.getConfidence()))
      → mediaAiInsightsRepo.appendServiceCompleted(msg.getMediaId(), "face_detection")
      → if (readModelFaceSearchRepo.existsByMediaId(msg.getMediaId())):
            esSyncPublisher.publish("face_search", msg.getMediaId())
```

### Wire format reminder (all string values in Redis)
| Field | Type on wire | Parse as |
|---|---|---|
| `facesDetected` | `"7"` | `Integer.parseInt(...)` |
| `faces` | JSON array string | `objectMapper.readValue(msg.getFaces(), new TypeReference<List<FaceObject>>(){})` |
| `bbox` | JSON array within each face object | `List<Integer>` |
| `embedding` | JSON array of floats within each face | `List<Float>` or `float[]` |

### Important note
Until AI fix A2 is deployed, the `embedding` arrays are zero-padded (real dim 32, padded to 1024). After A2 is deployed and the face API is switched to a 1024-dim model, the embeddings will be meaningful. Test face persistence with A2 in place.

---

## B2 — `read_model_post_search` NULL + `post_search` ES 404: `PostInsightsEnrichedConsumer` not writing

### What happened
- Java backend published `post-aggregation-trigger` (messageId `1776240313059-0`) for `postId=1`.
- The `post_aggregator` published to `post-insights-enriched` (confirmed by the published messageId).
- `SELECT * FROM read_model_post_search WHERE post_id = 1` → NULL.
- `GET /post_search/_doc/1` → 404.

### Confirm post_aggregator ran end-to-end
```bash
docker logs post_aggregator 2>&1 | grep "71b74f92-1440-45af-bd0c-8e1ee2ed7771\|postId.*\b1\b" | head -40
```
You should see "Published enriched insights" with `post_id=1`. If not, the aggregator timed out waiting for `image_embedding` results — which will be resolved by AI fix A1.

### Expected consumer path
```
post-insights-enriched (Redis Stream)
  → PostInsightsEnrichedConsumer.onMessage(PostInsightsEnrichedMessage msg)
      → postSearchReadModelRepo.upsert(
            post_id          = Long.parseLong(msg.getPostId()),
            aggregated_tags  = objectMapper.readValue(msg.getAggregatedTags(), List.class),
            aggregated_scenes= objectMapper.readValue(msg.getAggregatedScenes(), List.class),
            combined_caption = msg.getCombinedCaption(),
            inferred_event_type = msg.getInferredEventType(),
            is_safe          = Boolean.parseBoolean(msg.getIsSafe()),
            total_faces      = Integer.parseInt(msg.getTotalFaces()),
            media_count      = Integer.parseInt(msg.getMediaCount())
        )
      → esSyncPublisher.publish("post_search", msg.getPostId())
```

### Wire format — all string values
| Field | Decode as |
|---|---|
| `postId` | `Long.parseLong(...)` |
| `aggregatedTags` | `objectMapper.readValue(..., List<String>.class)` |
| `aggregatedScenes` | `objectMapper.readValue(..., List<String>.class)` |
| `allAiTags` | `objectMapper.readValue(..., List<String>.class)` (raw, pre-dedup) |
| `allAiScenes` | `objectMapper.readValue(..., List<String>.class)` |
| `totalFaces` | `Integer.parseInt(...)` |
| `mediaCount` | `Integer.parseInt(...)` |
| `isSafe` | `Boolean.parseBoolean(...)` |
| `combinedCaption` | plain string |
| `inferredEventType` | plain string (`"general"`, `"wedding"`, etc.) |
| `correlationId` | plain string |

### es-sync-queue message to publish after upsert
```json
{
  "indexType": "post_search",
  "documentId": "<post_id>",
  "operation": "index"
}
```
The Python `es_sync` worker does **not** own `post_search` — Java must write this index directly via Spring Data Elasticsearch `ElasticsearchRepository.save(postSearchDocument)`.

---

## B3 — `media_search` ES 404: Java media sync not triggered after ML completion

### What happened
- `read_model_media_search` row exists for `media_id=1` (caption, tags, scenes, is_safe all populated).
- `image_embedding` is null in that row (will be populated after AI fix A1).
- `GET /media_search/_doc/1` → 404.

### Diagnosis
```bash
docker logs kaleidoscope-app 2>&1 | grep -i "media_search\|MediaSearch\|mediaSearch" | head -40
```

Check whether `media_search` is populated via:
- **Path A:** Spring Data ES `MediaSearchRepository.save(doc)` called directly after `media_ai_insights.status = COMPLETED`, or
- **Path B:** `es-sync-queue` with `indexType=media_search` (note: the Python `es_sync` worker intentionally does not process `media_search` — Java must handle it end-to-end).

### Expected fix
After `MediaAiInsightsConsumer` sets `media_ai_insights.status = COMPLETED`, it should:
```java
MediaSearchDocument doc = mediaSearchReadModelRepo.findByMediaId(mediaId);
if (doc != null) {
    mediaSearchEsRepo.save(doc);   // direct Spring Data ES save
}
```

If the save is already there, verify the ES credentials and index name match (`media_search` in ES).

### Verify after fix
```bash
curl -u elastic:<password> http://localhost:9200/media_search/_doc/1
```

---

## B4 — `recommendations_knn` ES 404: unblocked by AI fix A1

### Dependency chain
```
image_embedding worker [AI Fix A1]
  → publishes imageEmbedding (512-dim float list) to ml-insights-results
  → MediaAiInsightsConsumer receives service="image_embedding"
      → ReadModelUpdateService.updateRecommendationsKnnReadModel(mediaId, embedding)
          → UPSERT read_model_recommendations_knn (media_id, image_embedding)
          → esSyncPublisher.publish("recommendations_knn", mediaId)
  → Python es_sync reads read_model_recommendations_knn, writes recommendations_knn ES doc
```

### Verify after deploying AI fix A1
```sql
SELECT media_id, image_embedding IS NOT NULL AS has_embedding
FROM read_model_recommendations_knn WHERE media_id = 1;
```

If the row still does not appear, check `ReadModelUpdateService.updateRecommendationsKnnReadModel()` — it may be guarded by a null check that silently returns when embedding is null (which was the pre-A1 state). Confirm the method is invoked for `service="image_embedding"` messages.

```bash
docker logs kaleidoscope-app 2>&1 | grep -i "recommendations_knn\|updateRecommendationsKnn\|image_embedding" | head -40
```

### Wire format of the embedding message
```
Stream: ml-insights-results
Fields:
  mediaId        = "1"
  postId         = "1"
  service        = "image_embedding"
  imageEmbedding = "[0.123, -0.456, ...]"   ← JSON array string, 512 floats
  correlationId  = "..."
```

Deserialize: `objectMapper.readValue(msg.getImageEmbedding(), new TypeReference<List<Float>>(){})` then store as `float[]` or `List<Float>` in `read_model_recommendations_knn.image_embedding`.

---

## B5 — `feed_personalized` ES 0 hits despite successful sync (camelCase field name)

### What happened
- `read_model_feed_personalized` has a row for `media_id=1`, `post_id=1`.
- Python `es_sync` logged **"Bulk sync completed, count 1"** for `feed_personalized`.
- Search query `{"query": {"term": {"post_id": "1"}}}` returned **0 hits**.

### Root cause
Python `es_sync` converts all PostgreSQL column names from `snake_case` → `camelCase` before writing to Elasticsearch (via `_snake_to_camel`). So `post_id` is stored in ES as **`postId`**, not `post_id`.

### Verification (run on server)
```bash
# Step 1: confirm the document exists
curl -u elastic:<password> http://localhost:9200/feed_personalized/_doc/1

# Step 2: search with the correct camelCase field name
curl -u elastic:<password> -H "Content-Type: application/json" \
  http://localhost:9200/feed_personalized/_search \
  -d '{"query": {"term": {"postId": "1"}}}'
```

### Fix for Java consumers
Any Java code querying `feed_personalized` that uses `post_id` as the field name needs to use `postId` instead. This applies to:
- Feed generation queries
- Personalization ranking queries
- Any `NativeQuery` or `CriteriaQuery` against the `feed_personalized` index

The same camelCase rule applies to all other Python `es_sync`-owned indices (`face_search`, `recommendations_knn`, `known_faces_index`). Column name → camelCase field name mapping examples:

| PostgreSQL column | ES field |
|---|---|
| `post_id` | `postId` |
| `media_id` | `mediaId` |
| `user_id` | `userId` |
| `image_embedding` | `imageEmbedding` |
| `face_embedding` | `faceEmbedding` |
| `is_safe` | `isSafe` |
| `created_at` | `createdAt` |

---

## Deployment order

```
1. Deploy AI fix A1 (image_embedding container) + set HF_API_URL_IMAGE_EMBEDDING in .env
2. Deploy AI fix A2 (switch face API to 1024-dim model, set FACE_EMBEDDING_DIM=1024)
3. Fix and deploy: PostInsightsEnrichedConsumer writes read_model_post_search + ES save (B2)
4. Fix and deploy: media_search ES save after media_ai_insights COMPLETED (B3)
5. Verify read_model_recommendations_knn populated after A1 deploy (B4)
6. Fix and deploy: FaceDetectionConsumer persists media_detected_faces (B1) — after A2
7. Verify feed_personalized ES queries use postId camelCase (B5) — no deploy needed
```
