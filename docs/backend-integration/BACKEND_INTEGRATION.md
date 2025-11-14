# Backend Integration Guide

**Complete guide for integrating Kaleidoscope AI with Spring Boot backend**

---

## Overview

The AI services are **100% complete and tested**. This guide covers what the backend team needs to implement for full integration.

---

## What You Need to Implement

1. **7 PostgreSQL Read Model Tables** - Denormalized tables for Elasticsearch sync
2. **Redis Streams Integration** - Publish/consume messages
3. **Sync Triggers** - Update Elasticsearch when data changes
4. **API Endpoints** - Expose search functionality

---

## Integration Flow

```
1. Backend receives image upload
   ↓
2. Backend publishes to: post-image-processing
   ↓
3. AI services process and publish to: ml-insights-results, face-detection-results
   ↓
4. Backend consumes AI results and updates PostgreSQL read models
   ↓
5. Backend triggers post aggregation (if all media processed)
   ↓
6. Post aggregator publishes to: post-insights-enriched
   ↓
7. Backend consumes enriched insights and updates read models
   ↓
8. Backend publishes to: es-sync-queue
   ↓
9. ES Sync reads from PostgreSQL and indexes to Elasticsearch
```

---

## 1. Database Setup

### Create 7 Read Model Tables

**Location**: Same PostgreSQL database as core tables  
**Design**: Denormalized, no foreign keys, optimized for Elasticsearch

#### Table 1: `read_model_media_search`

```sql
CREATE TABLE read_model_media_search (
    media_id BIGINT PRIMARY KEY,
    post_id BIGINT NOT NULL,
    post_title VARCHAR(200),
    post_all_tags TEXT[],
    media_url VARCHAR(1000) NOT NULL,
    ai_caption TEXT,
    ai_tags TEXT[],
    ai_scenes TEXT[],
    image_embedding TEXT,  -- 512-dim vector as JSON string
    is_safe BOOLEAN DEFAULT true,
    detected_user_ids BIGINT[],
    detected_usernames TEXT[],
    uploader_id BIGINT NOT NULL,
    uploader_username VARCHAR(50) NOT NULL,
    uploader_department VARCHAR(100),
    reaction_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_rms_post ON read_model_media_search(post_id);
CREATE INDEX idx_rms_updated ON read_model_media_search(updated_at DESC);
```

#### Table 2: `read_model_post_search`

```sql
CREATE TABLE read_model_post_search (
    post_id BIGINT PRIMARY KEY,
    author_id BIGINT NOT NULL,
    author_username VARCHAR(50) NOT NULL,
    author_department VARCHAR(100),
    title VARCHAR(200),
    body TEXT,
    all_ai_tags TEXT[],
    all_ai_scenes TEXT[],
    inferred_event_type VARCHAR(50),
    combined_caption TEXT,
    total_faces INTEGER DEFAULT 0,
    media_count INTEGER DEFAULT 0,
    is_safe BOOLEAN DEFAULT true,
    reaction_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

#### Tables 3-7

See detailed SQL in `docs/backend-integration/DATABASE_SCHEMA.md`:

- `read_model_user_search`
- `read_model_face_search`
- `read_model_recommendations_knn`
- `read_model_feed_personalized`
- `read_model_known_faces`

---

## 2. Redis Streams Integration

### Publish Image Processing Job

**Stream**: `post-image-processing`

```java
@Component
public class ImageProcessingPublisher {

    @Autowired
    private RedisTemplate<String, Object> redisTemplate;

    public void publishImageJob(Long postId, Long mediaId, String mediaUrl,
                                Long uploaderId, String correlationId) {
        Map<String, Object> message = Map.of(
            "postId", postId.toString(),
            "mediaId", mediaId.toString(),
            "mediaUrl", mediaUrl,
            "uploaderId", uploaderId.toString(),
            "correlationId", correlationId
        );

        redisTemplate.opsForStream().add("post-image-processing", message);
    }
}
```

### Consume ML Insights Results

**Stream**: `ml-insights-results`

```java
@Component
public class MLInsightsConsumer {

    @StreamListener(target = "ml-insights-results")
    public void handleMLInsights(Map<String, Object> message) {
        Long postId = Long.parseLong((String) message.get("postId"));
        Long mediaId = Long.parseLong((String) message.get("mediaId"));
        String service = (String) message.get("service");

        // Update read_model_media_search based on service type
        switch (service) {
            case "moderation":
                updateModerationResults(mediaId, message);
                break;
            case "tagging":
                updateTaggingResults(mediaId, message);
                break;
            case "scene_recognition":
                updateSceneResults(mediaId, message);
                break;
            case "image_captioning":
                updateCaptionResults(mediaId, message);
                break;
        }

        // Check if all services completed, trigger aggregation
        if (allServicesComplete(postId)) {
            triggerPostAggregation(postId);
        }
    }
}
```

### Consume Face Detection Results

**Stream**: `face-detection-results`

```java
@Component
public class FaceDetectionConsumer {

    @StreamListener(target = "face-detection-results")
    public void handleFaceDetection(Map<String, Object> message) {
        Long postId = Long.parseLong((String) message.get("postId"));
        Long mediaId = Long.parseLong((String) message.get("mediaId"));
        Integer facesDetected = Integer.parseInt((String) message.get("facesDetected"));
        String facesJson = (String) message.get("faces");

        // Parse faces array
        List<Face> faces = parseFaces(facesJson);

        // Store faces in database
        storeFaces(mediaId, faces);

        // Update read_model_media_search
        updateMediaSearchWithFaces(mediaId, faces);
    }
}
```

### Consume Post Insights Enriched

**Stream**: `post-insights-enriched`

```java
@Component
public class PostInsightsConsumer {

    @StreamListener(target = "post-insights-enriched")
    public void handleEnrichedInsights(Map<String, Object> message) {
        Long postId = Long.parseLong((String) message.get("postId"));

        // Update read_model_post_search
        updatePostSearch(postId, message);

        // Update all media in post with aggregated tags
        updateMediaWithAggregatedTags(postId, message);

        // Trigger ES sync
        triggerESSync("post_search", postId);
    }
}
```

### Trigger ES Sync

**Stream**: `es-sync-queue`

```java
public void triggerESSync(String indexType, Long documentId) {
    Map<String, Object> message = Map.of(
        "operation", "index",
        "indexType", indexType,
        "documentId", documentId.toString()
    );

    redisTemplate.opsForStream().add("es-sync-queue", message);
}
```

---

## 3. Update Triggers

### When to Update Read Models

1. **When AI insights arrive** (from `ml-insights-results`):

   - Update `read_model_media_search` with AI data
   - Check if all services completed → trigger aggregation

2. **When faces detected** (from `face-detection-results`):

   - Store faces in `media_detected_faces` table
   - Update `read_model_media_search.detected_user_ids`

3. **When post aggregation completes** (from `post-insights-enriched`):

   - Update `read_model_post_search` with aggregated data
   - Update all media in post with `post_all_tags`

4. **When engagement changes**:

   - Update `reaction_count` and `comment_count` in read models

5. **After any read model update**:
   - Publish to `es-sync-queue` to sync to Elasticsearch

---

## 4. Message Formats

See **[../api/API.md](../api/API.md)** for complete message format specifications.

### Key Points:

- All messages use camelCase field names
- Arrays are JSON-encoded as strings
- Timestamps are ISO 8601 format
- `correlationId` is mandatory for tracing

---

## 5. Implementation Checklist

### Week 1: Database Setup

- [ ] Create 7 read model tables
- [ ] Add indexes for performance
- [ ] Test table creation scripts

### Week 2: Redis Integration

- [ ] Add Redis Streams dependencies
- [ ] Configure Redis connection
- [ ] Implement image processing publisher
- [ ] Implement ML insights consumer
- [ ] Implement face detection consumer
- [ ] Implement post insights consumer

### Week 3: Business Logic

- [ ] Update read models on AI results
- [ ] Implement post aggregation trigger
- [ ] Implement ES sync trigger
- [ ] Add error handling and retries

### Week 4: Testing & Optimization

- [ ] Integration testing
- [ ] Performance optimization
- [ ] Error handling validation
- [ ] Documentation review

---

## 6. Verification

### Verify Read Models

```sql
-- Check media search read model
SELECT * FROM read_model_media_search WHERE media_id = 70001;

-- Check post search read model
SELECT * FROM read_model_post_search WHERE post_id = 90001;
```

### Verify ES Sync

```bash
# Check ES sync queue
docker exec redis redis-cli -a ${REDIS_PASSWORD} XLEN es-sync-queue

# Check Elasticsearch
curl http://localhost:9200/media_search/_doc/70001
```

---

## 7. Reference Documentation

- **[../api/API.md](../api/API.md)** - Complete message format specifications
- **[DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)** - Full database schema
- **[READ_MODELS.md](READ_MODELS.md)** - Detailed read model specifications
- **[CODE_EXAMPLES.md](CODE_EXAMPLES.md)** - Code examples

---

## 8. Support

For questions or issues:

1. Check **[../guides/TROUBLESHOOTING.md](../guides/TROUBLESHOOTING.md)**
2. Review service logs
3. Check Redis Streams for message flow

---

**The AI services are ready and waiting for your integration! 🚀**
