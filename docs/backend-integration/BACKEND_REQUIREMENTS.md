# 🔗 Backend Team Requirements - Integration Specification

**Date**: October 15, 2025  
**From**: AI/Elasticsearch Team  
**To**: Backend Development Team  
**Status**: Specification for Integration

---

## 📋 Overview

This document specifies the **exact requirements** the backend team must implement to integrate with the AI microservices and Elasticsearch infrastructure.

**Division of Responsibilities**:
- **AI Team** (You): AI microservices, Elasticsearch setup, data indexing
- **Backend Team** (Teammate): Spring Boot backend, PostgreSQL, Redis Streams integration

---

## 🔄 Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Backend Team                             │
│  (Spring Boot + PostgreSQL + Redis Streams)                 │
│                                                              │
│  Responsibilities:                                           │
│  - Create 7 PostgreSQL read model tables                    │
│  - Publish events to Redis Streams                          │
│  - Consume AI results from Redis Streams                    │
│  - Update PostgreSQL with AI insights                       │
│  - Trigger Elasticsearch sync                               │
└─────────────────────────────────────────────────────────────┘
                         │                    ▲
                         │ Publishes          │ Consumes
                         ▼                    │
┌─────────────────────────────────────────────────────────────┐
│                   Redis Streams                              │
│  (Message Queue - Already in your stack)                    │
│                                                              │
│  Streams:                                                    │
│  → post-image-processing (Backend → AI)                     │
│  → ml-insights-results (AI → Backend)                       │
│  → face-detection-results (AI → Backend)                    │
│  → post-aggregation-trigger (Backend → AI)                  │
│  → post-insights-enriched (AI → Backend)                    │
│  → es-sync-queue (Backend → ES Team)                        │
└─────────────────────────────────────────────────────────────┘
                         │                    ▲
                         │ Consumes           │ Publishes
                         ▼                    │
┌─────────────────────────────────────────────────────────────┐
│                    AI Team                                   │
│  (Python Microservices + Elasticsearch)                     │
│                                                              │
│  Responsibilities:                                           │
│  - Process images (5 AI workers)                            │
│  - Generate embeddings (512-dim & 1024-dim)                 │
│  - Aggregate post-level insights                            │
│  - Set up Elasticsearch (7 indices)                         │
│  - Consume from es-sync-queue and index to ES               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Backend Team Must Create: 7 PostgreSQL Read Model Tables

### Table 1: `read_model_media_search`

**Purpose**: Source of truth for media search data

```sql
CREATE TABLE read_model_media_search (
    -- Primary identifiers
    media_id BIGINT PRIMARY KEY,
    post_id BIGINT NOT NULL,
    
    -- Post context (denormalized from posts table)
    post_title VARCHAR(200),
    post_body TEXT,
    post_summary VARCHAR(500),
    post_total_images INTEGER DEFAULT 0,
    post_all_tags TEXT[],              -- CRITICAL: Aggregated from ALL images
    post_all_scenes TEXT[],
    media_position INTEGER DEFAULT 0,
    
    -- Media info
    media_url VARCHAR(1000) NOT NULL,
    media_type VARCHAR(20) NOT NULL,
    thumbnail_url VARCHAR(1000),
    width INTEGER,
    height INTEGER,
    
    -- AI insights (populated from AI results)
    ai_status VARCHAR(20) DEFAULT 'PROCESSING',
    is_safe BOOLEAN,
    ai_caption TEXT,
    ai_tags TEXT[],
    ai_scenes TEXT[],
    ai_confidence_scores JSONB,
    image_embedding VECTOR(512),       -- CLIP embedding
    dominant_colors VARCHAR(20)[],
    
    -- Detected faces (aggregated)
    detected_face_count INTEGER DEFAULT 0,
    identified_user_ids BIGINT[],
    identified_usernames TEXT[],
    identified_confidences FLOAT[],
    unidentified_face_count INTEGER DEFAULT 0,
    
    -- Uploader info (denormalized from users table)
    uploader_id BIGINT NOT NULL,
    uploader_username VARCHAR(50) NOT NULL,
    uploader_full_name VARCHAR(100),
    uploader_profile_pic VARCHAR(255),
    uploader_department VARCHAR(100),
    uploader_designation VARCHAR(100),
    
    -- Engagement metrics
    reaction_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    view_count BIGINT DEFAULT 0,
    save_count INTEGER DEFAULT 0,
    
    -- Metadata
    visibility VARCHAR(20) DEFAULT 'PUBLIC',
    post_status VARCHAR(20) DEFAULT 'PUBLISHED',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Foreign keys
    CONSTRAINT fk_media FOREIGN KEY (media_id) REFERENCES post_media(media_id) ON DELETE CASCADE,
    CONSTRAINT fk_post FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
);

-- Required indexes
CREATE INDEX idx_rms_post ON read_model_media_search(post_id);
CREATE INDEX idx_rms_uploader ON read_model_media_search(uploader_id);
CREATE INDEX idx_rms_created ON read_model_media_search(created_at DESC);
CREATE INDEX idx_rms_ai_tags ON read_model_media_search USING gin(ai_tags);
CREATE INDEX idx_rms_post_all_tags ON read_model_media_search USING gin(post_all_tags);
```

**When to Update**:
- ✅ When AI results arrive from Redis Stream
- ✅ When post is updated (title, body)
- ✅ When engagement metrics change (reactions, comments)
- ✅ When face identified

---

### Table 2: `read_model_post_search`

**Purpose**: Post-level search with aggregated media insights

```sql
CREATE TABLE read_model_post_search (
    post_id BIGINT PRIMARY KEY,
    
    -- Author (denormalized from users)
    author_id BIGINT NOT NULL,
    author_username VARCHAR(50) NOT NULL,
    author_full_name VARCHAR(100),
    author_department VARCHAR(100),
    
    -- Content
    title VARCHAR(200),
    body TEXT,
    summary VARCHAR(500),
    
    -- Media summary (aggregated from all media AI results)
    total_media INTEGER DEFAULT 0,
    total_images INTEGER DEFAULT 0,
    all_ai_tags TEXT[],                -- Union of ALL media tags
    all_ai_scenes TEXT[],
    all_detected_user_ids BIGINT[],
    all_detected_usernames TEXT[],
    has_unsafe_media BOOLEAN DEFAULT false,
    
    -- Post-level AI (from post_aggregator service)
    inferred_event_type VARCHAR(50),   -- e.g., "party", "meeting"
    inferred_tags TEXT[],              -- e.g., ["beach_party", "team"]
    
    -- Categories & tags
    categories TEXT[],
    user_tagged_ids BIGINT[],
    user_tagged_usernames TEXT[],
    
    -- Location (denormalized)
    location_name VARCHAR(100),
    location_city VARCHAR(100),
    
    -- Engagement (aggregated from all media)
    total_reactions INTEGER DEFAULT 0,
    total_comments INTEGER DEFAULT 0,
    total_views BIGINT DEFAULT 0,
    
    -- Metadata
    status VARCHAR(20) DEFAULT 'PUBLISHED',
    visibility VARCHAR(20) DEFAULT 'PUBLIC',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    CONSTRAINT fk_post FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
);

CREATE INDEX idx_rps_author ON read_model_post_search(author_id);
CREATE INDEX idx_rps_created ON read_model_post_search(created_at DESC);
CREATE INDEX idx_rps_all_tags ON read_model_post_search USING gin(all_ai_tags);
```

**When to Update**:
- ✅ When post created/updated
- ✅ When all media AI processing complete
- ✅ When post aggregation enriched data arrives

---

### Table 3: `read_model_user_search`

```sql
CREATE TABLE read_model_user_search (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100),
    full_name VARCHAR(100),
    department VARCHAR(100),
    designation VARCHAR(100),
    bio TEXT,
    
    -- Statistics
    total_posts INTEGER DEFAULT 0,
    total_followers INTEGER DEFAULT 0,
    total_following INTEGER DEFAULT 0,
    
    -- Face enrollment
    face_enrolled BOOLEAN DEFAULT false,
    
    -- Metadata
    joined_at TIMESTAMPTZ NOT NULL,
    last_active TIMESTAMPTZ,
    account_status VARCHAR(20) DEFAULT 'ACTIVE',
    
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
```

---

### Table 4: `read_model_face_search`

```sql
CREATE TABLE read_model_face_search (
    id BIGSERIAL PRIMARY KEY,
    face_id VARCHAR(50) UNIQUE NOT NULL,
    media_id BIGINT NOT NULL,
    post_id BIGINT NOT NULL,
    
    -- Detection (from AI)
    bbox INTEGER[],
    confidence FLOAT NOT NULL,
    face_embedding VECTOR(1024) NOT NULL,  -- AdaFace 1024-dim
    
    -- Identification
    identification_status VARCHAR(20) DEFAULT 'UNKNOWN',
    identified_user_id BIGINT,
    identified_username VARCHAR(50),
    match_confidence FLOAT,
    
    -- Context (denormalized)
    uploader_id BIGINT NOT NULL,
    post_title VARCHAR(200),
    media_caption TEXT,
    
    created_at TIMESTAMPTZ NOT NULL,
    
    CONSTRAINT fk_media FOREIGN KEY (media_id) REFERENCES post_media(media_id) ON DELETE CASCADE
);

CREATE INDEX idx_rfs_identified_user ON read_model_face_search(identified_user_id);
```

---

### Table 5: `read_model_recommendations_knn`

```sql
CREATE TABLE read_model_recommendations_knn (
    media_id BIGINT PRIMARY KEY,
    image_embedding VECTOR(512) NOT NULL,
    media_url VARCHAR(1000) NOT NULL,
    thumbnail_url VARCHAR(1000),
    post_id BIGINT NOT NULL,
    caption TEXT,
    is_safe BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL,
    
    CONSTRAINT fk_media FOREIGN KEY (media_id) REFERENCES post_media(media_id) ON DELETE CASCADE
);
```

---

### Table 6: `read_model_feed_personalized`

```sql
CREATE TABLE read_model_feed_personalized (
    id BIGSERIAL PRIMARY KEY,
    feed_item_id VARCHAR(100) UNIQUE NOT NULL,
    target_user_id BIGINT NOT NULL,
    media_id BIGINT NOT NULL,
    
    -- Content
    media_url VARCHAR(1000),
    caption TEXT,
    
    -- Uploader
    uploader_id BIGINT NOT NULL,
    uploader_username VARCHAR(50),
    
    -- Relevance
    combined_score FLOAT DEFAULT 0,
    
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    
    CONSTRAINT fk_target_user FOREIGN KEY (target_user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_rfp_target_score ON read_model_feed_personalized(target_user_id, combined_score DESC);
```

---

### Table 7: `read_model_known_faces`

```sql
CREATE TABLE read_model_known_faces (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    face_embedding VECTOR(1024) NOT NULL,
    profile_pic_url VARCHAR(255),
    department VARCHAR(100),
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active BOOLEAN DEFAULT true,
    
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_rkf_active ON read_model_known_faces(is_active) WHERE is_active = true;
```

---

## 🔄 Redis Streams Integration

### Stream 1: `post-image-processing` (Backend Publishes)

**When to Publish**: After user uploads post with images and images saved to Cloudinary

**Message Format**:
```json
{
  "postId": 100,
  "mediaId": 201,
  "imageUrl": "https://res.cloudinary.com/.../image.jpg",
  "position": 0,
  "userId": 15,
  "timestamp": "2024-08-15T14:30:00Z"
}
```

**Backend Code Example**:
```java
@Service
public class PostService {
    @Autowired
    private RedisStreamPublisher redisStreamPublisher;
    
    public Post createPost(CreatePostDto dto, User author) {
        // 1. Save post
        Post post = postRepository.save(newPost);
        
        // 2. Upload images to Cloudinary and save
        for (MultipartFile file : dto.getMedia()) {
            String cloudinaryUrl = cloudinaryService.upload(file);
            PostMedia media = saveMedia(cloudinaryUrl, post);
            
            // 3. Publish to Redis Stream for AI processing
            Map<String, String> event = Map.of(
                "postId", String.valueOf(post.getPostId()),
                "mediaId", String.valueOf(media.getMediaId()),
                "imageUrl", media.getMediaUrl(),
                "position", String.valueOf(media.getPosition()),
                "userId", String.valueOf(author.getUserId()),
                "timestamp", Instant.now().toString()
            );
            
            redisStreamPublisher.publish("post-image-processing", event);
        }
        
        return post;
    }
}
```

---

### Stream 2: `ml-insights-results` (Backend Consumes)

**AI Team Publishes**: After processing each image

**Message Format**:
```json
{
  "mediaId": 201,
  "postId": 100,
  "isSafe": true,
  "caption": "Beach sunset over the ocean",
  "tags": ["beach", "sunset", "ocean"],
  "scenes": ["outdoor", "beach", "coastal"],
  "confidenceScores": {
    "beach": 0.95,
    "sunset": 0.87
  },
  "imageEmbedding": "[0.123, -0.456, 0.789, ...]",  // 512-dim array as JSON string
  "dominantColors": ["#FF6B35", "#004E89"],
  "timestamp": "2024-08-15T14:32:00Z"
}
```

**Backend Must**:
1. Consume from `ml-insights-results` stream
2. Update `media_ai_insights` table (your existing table)
3. Update `read_model_media_search` table
4. Publish to `es-sync-queue` for Elasticsearch indexing

**Backend Code Example**:
```java
@Service
public class MediaAiInsightsConsumer {
    
    @StreamListener("ml-insights-results")
    @Transactional
    public void onMessage(MapRecord<String, String, String> record) {
        Map<String, String> data = record.getValue();
        
        // 1. Parse message
        Long mediaId = Long.parseLong(data.get("mediaId"));
        Long postId = Long.parseLong(data.get("postId"));
        Boolean isSafe = Boolean.parseBoolean(data.get("isSafe"));
        String caption = data.get("caption");
        List<String> tags = parseJsonArray(data.get("tags"));
        String imageEmbedding = data.get("imageEmbedding");
        
        // 2. Update media_ai_insights (existing table)
        MediaAiInsights insights = MediaAiInsights.builder()
            .mediaId(mediaId)
            .postId(postId)
            .isSafe(isSafe)
            .caption(caption)
            .tags(tags.toArray(new String[0]))
            .imageEmbedding(imageEmbedding)
            .build();
        mediaAiInsightsRepository.save(insights);
        
        // 3. Update read_model_media_search (NEW TABLE)
        updateMediaSearchReadModel(mediaId, insights);
        
        // 4. Publish to ES sync queue
        publishToESSyncQueue("media_search", mediaId);
        
        // 5. Check if all media in post processed
        if (allMediaProcessedForPost(postId)) {
            triggerPostAggregation(postId);
        }
    }
    
    private void updateMediaSearchReadModel(Long mediaId, MediaAiInsights insights) {
        PostMedia media = postMediaRepository.findById(mediaId).get();
        Post post = media.getPost();
        User uploader = post.getUser();
        
        ReadModelMediaSearch searchModel = ReadModelMediaSearch.builder()
            .mediaId(mediaId)
            .postId(post.getPostId())
            // Post context
            .postTitle(post.getTitle())
            .postBody(post.getBody())
            .postTotalImages(post.getMedia().size())
            // AI insights
            .aiStatus("COMPLETED")
            .isSafe(insights.getIsSafe())
            .aiCaption(insights.getCaption())
            .aiTags(insights.getTags())
            .imageEmbedding(insights.getImageEmbedding())
            // Uploader (denormalized)
            .uploaderId(uploader.getUserId())
            .uploaderUsername(uploader.getUsername())
            .uploaderDepartment(uploader.getDepartment())
            .build();
        
        readModelMediaSearchRepository.save(searchModel);
    }
}
```

---

### Stream 3: `face-detection-results` (Backend Consumes)

**AI Team Publishes**: After detecting faces in image

**Message Format**:
```json
{
  "mediaId": 202,
  "postId": 100,
  "facesDetected": 2,
  "faces": [
    {
      "faceId": "face_uuid_12345",
      "bbox": [100, 50, 200, 150],
      "confidence": 0.98,
      "embedding": "[0.234, -0.567, ...]",  // 1024-dim AdaFace
      "quality": 0.92
    },
    {
      "faceId": "face_uuid_67890",
      "bbox": [300, 50, 400, 150],
      "confidence": 0.95,
      "embedding": "[0.345, -0.678, ...]",
      "quality": 0.88
    }
  ],
  "timestamp": "2024-08-15T14:32:30Z"
}
```

**Backend Must**:
1. For each detected face:
   - Save to `media_detected_faces` table
   - Perform KNN search against `read_model_known_faces` to identify user
   - Update identification status (IDENTIFIED, SUGGESTED, UNKNOWN)
   - Update `read_model_face_search`
   - Update `read_model_media_search` with detected users
2. Publish to `es-sync-queue`

**Backend Code Example**:
```java
@StreamListener("face-detection-results")
@Transactional
public void onFaceDetected(MapRecord<String, String, String> record) {
    // Parse faces
    List<DetectedFace> faces = parseFaces(record);
    
    for (DetectedFace face : faces) {
        // 1. Save to media_detected_faces
        MediaDetectedFace detectedFace = saveDetectedFace(face);
        
        // 2. Try to identify using KNN search
        List<KnownFace> matches = knownFacesRepository
            .findSimilarFaces(face.getEmbedding(), 5);
        
        if (!matches.isEmpty()) {
            float topScore = matches.get(0).getSimilarity();
            
            if (topScore >= 0.85) {
                // High confidence - IDENTIFIED
                detectedFace.setIdentifiedUser(matches.get(0).getUser());
                detectedFace.setStatus(FaceDetectionStatus.IDENTIFIED);
                detectedFace.setMatchConfidence(topScore);
            } else if (topScore >= 0.70) {
                // Medium confidence - SUGGESTED
                detectedFace.setSuggestedUser(matches.get(0).getUser());
                detectedFace.setStatus(FaceDetectionStatus.SUGGESTED);
                detectedFace.setMatchConfidence(topScore);
            }
        }
        
        mediaDetectedFaceRepository.save(detectedFace);
        
        // 3. Update read models
        updateFaceSearchReadModel(detectedFace);
        updateMediaSearchWithDetectedUsers(face.getMediaId());
    }
}
```

---

### Stream 4: `post-aggregation-trigger` (Backend Publishes)

**When to Publish**: After ALL media in a post complete AI processing

**Message Format**:
```json
{
  "postId": 100,
  "totalMedia": 3,
  "allMediaIds": [201, 202, 203],
  "timestamp": "2024-08-15T14:35:00Z"
}
```

**Backend Code**:
```java
private void triggerPostAggregation(Long postId) {
    Post post = postRepository.findById(postId).get();
    
    Map<String, String> event = Map.of(
        "postId", String.valueOf(postId),
        "totalMedia", String.valueOf(post.getMedia().size()),
        "allMediaIds", post.getMedia().stream()
            .map(m -> String.valueOf(m.getMediaId()))
            .collect(Collectors.joining(",")),
        "timestamp", Instant.now().toString()
    );
    
    redisStreamPublisher.publish("post-aggregation-trigger", event);
}
```

---

### Stream 5: `post-insights-enriched` (Backend Consumes)

**AI Team Publishes**: After analyzing all images in post together

**Message Format**:
```json
{
  "postId": 100,
  "allAiTags": ["beach", "sunset", "person", "smile", "food", "drinks"],
  "allAiScenes": ["outdoor", "beach", "party"],
  "inferredEventType": "party",
  "inferredLocationType": "beach",
  "inferredTags": ["team", "party", "beach_party", "social"],
  "confidence": 0.91,
  "timestamp": "2024-08-15T14:35:30Z"
}
```

**Backend Must**:
1. Update `read_model_post_search` with inferred data
2. Update ALL `read_model_media_search` rows for this post with `post_all_tags`
3. Publish to `es-sync-queue` for bulk ES update

**Backend Code**:
```java
@StreamListener("post-insights-enriched")
@Transactional
public void onPostEnriched(MapRecord<String, String, String> record) {
    Map<String, String> data = record.getValue();
    Long postId = Long.parseLong(data.get("postId"));
    List<String> allAiTags = parseJsonArray(data.get("allAiTags"));
    String inferredEventType = data.get("inferredEventType");
    List<String> inferredTags = parseJsonArray(data.get("inferredTags"));
    
    // 1. Update post search read model
    ReadModelPostSearch postSearch = readModelPostSearchRepository
        .findById(postId).orElse(new ReadModelPostSearch());
    
    postSearch.setAllAiTags(allAiTags.toArray(new String[0]));
    postSearch.setInferredEventType(inferredEventType);
    postSearch.setInferredTags(inferredTags.toArray(new String[0]));
    readModelPostSearchRepository.save(postSearch);
    
    // 2. Update ALL media in this post with post_all_tags
    List<ReadModelMediaSearch> mediaModels = 
        readModelMediaSearchRepository.findByPostId(postId);
    
    for (ReadModelMediaSearch media : mediaModels) {
        media.setPostAllTags(allAiTags.toArray(new String[0]));
    }
    readModelMediaSearchRepository.saveAll(mediaModels);
    
    // 3. Publish to ES sync (bulk for all media + post)
    publishToESSyncQueue("post_search", postId);
    publishToESSyncQueue("media_search_bulk", postId);
}
```

---

### Stream 6: `es-sync-queue` (Backend Publishes, AI Team Consumes)

**When to Publish**: After updating any read model table

**Message Format**:
```json
{
  "indexName": "media_search",
  "operation": "INDEX",
  "documentId": 201,
  "timestamp": "2024-08-15T14:35:00Z"
}
```

**AI Team Responsibility**: 
- Consume from this stream
- Read from PostgreSQL read model table
- Map to Elasticsearch document
- Index to Elasticsearch

**Backend Code**:
```java
private void publishToESSyncQueue(String indexName, Long documentId) {
    Map<String, String> event = Map.of(
        "indexName", indexName,
        "operation", "INDEX",
        "documentId", String.valueOf(documentId),
        "timestamp", Instant.now().toString()
    );
    
    redisStreamPublisher.publish("es-sync-queue", event);
}
```

---

## ✅ Backend Team Checklist

### Phase 1: Database (Week 1)
- [ ] Create migration script `V2__create_read_models.sql` with all 7 tables
- [ ] Run migration on development database
- [ ] Verify pgvector extension installed
- [ ] Create JPA entities for all 7 read model tables
- [ ] Test basic CRUD operations

### Phase 2: Redis Streams Setup (Week 1)
- [ ] Verify Redis Streams configured in Spring Boot
- [ ] Create `RedisStreamPublisher` service
- [ ] Create stream listener configuration
- [ ] Test publishing to `post-image-processing` stream

### Phase 3: AI Result Consumers (Week 2)
- [ ] Implement `MediaAiInsightsConsumer` (consume `ml-insights-results`)
- [ ] Implement `FaceDetectionConsumer` (consume `face-detection-results`)
- [ ] Implement `PostAggregationConsumer` (consume `post-insights-enriched`)
- [ ] Test each consumer with mock data

### Phase 4: Read Model Updates (Week 2)
- [ ] Implement logic to update `read_model_media_search`
- [ ] Implement logic to update `read_model_post_search`
- [ ] Implement logic to update `read_model_face_search`
- [ ] Implement logic to update `read_model_user_search`
- [ ] Implement logic to update `read_model_known_faces`

### Phase 5: Sync Queue Publishing (Week 2)
- [ ] Publish to `es-sync-queue` after each read model update
- [ ] Implement error handling for failed publishes

### Phase 6: Post Upload Flow (Week 2)
- [ ] Update `PostService.createPost()` to publish to `post-image-processing`
- [ ] Publish ONE event per media item (not batch)
- [ ] Include all required fields in message

### Phase 7: Face Matching (Week 3)
- [ ] Implement KNN search in `read_model_known_faces`
- [ ] Implement identification logic (thresholds: 0.85, 0.70)
- [ ] Update `media_detected_faces` with identification status

### Phase 8: Testing (Week 3)
- [ ] Test complete flow: upload → AI → results → DB → ES sync
- [ ] Test with 1 image post
- [ ] Test with 3 image post
- [ ] Test face detection and matching
- [ ] Verify all read models populated correctly

---

## 🔍 SQL Queries Backend Needs

### Check if all media in post processed
```java
public boolean allMediaProcessedForPost(Long postId) {
    Long total = postMediaRepository.countByPostId(postId);
    Long processed = readModelMediaSearchRepository
        .countByPostIdAndAiStatus(postId, "COMPLETED");
    return total.equals(processed);
}
```

### Get similar faces (KNN search)
```java
@Repository
public interface KnownFacesRepository extends JpaRepository<ReadModelKnownFaces, Long> {
    
    @Query(value = """
        SELECT *, 1 - (face_embedding <=> CAST(:embedding AS vector)) as similarity
        FROM read_model_known_faces
        WHERE is_active = true
        ORDER BY face_embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
        """, nativeQuery = true)
    List<KnownFace> findSimilarFaces(
        @Param("embedding") String embedding, 
        @Param("limit") int limit
    );
}
```

---

## 📞 Communication Protocol

### Daily Sync
- **Slack/Teams channel**: `#kaleidoscope-integration`
- **Daily standup**: Sync on integration progress

### Questions & Issues
- **Tag**: `@backend-team` or `@ai-team`
- **Response time**: Within 4 hours during work hours

### Testing Coordination
- **Shared test environment**: staging.kaleidoscope.internal
- **Test data**: Both teams use same test images/posts
- **Integration testing**: Weekly joint testing sessions

---

## 📝 Sample Test Scenarios

### Scenario 1: Single Image Post
```
1. Backend: User uploads post with 1 image
2. Backend: Publish to post-image-processing
3. AI: Process image, publish to ml-insights-results
4. Backend: Consume result, update DB
5. Backend: Publish to es-sync-queue
6. AI: Index to Elasticsearch
7. Backend: Query /api/search, verify result appears
```

### Scenario 2: Multi-Image Post with Faces
```
1. Backend: User uploads post with 3 images
2. Backend: Publish 3 events to post-image-processing
3. AI: Process all 3 in parallel
4. AI: Detect 2 faces in image #2
5. Backend: Receive face results, match against known faces
6. Backend: After all 3 done, trigger post aggregation
7. AI: Analyze 3 images together, publish enriched data
8. Backend: Update all media with post_all_tags
9. Backend: Publish to es-sync-queue
10. AI: Bulk index to ES
11. Search "beach party" → returns all 3 images
```

---

## 🚨 Critical Integration Points

### 1. Vector Dimensions MUST MATCH
- **Image embeddings**: 512 dimensions (CLIP)
- **Face embeddings**: 1024 dimensions (AdaFace)
- Backend PostgreSQL vector columns MUST use these exact dimensions

### 2. Message Format MUST MATCH
- AI team will send exact JSON format specified
- Backend must parse exactly as shown
- Any changes MUST be communicated to both teams

### 3. Timing
- AI processing takes 5-15 seconds per image
- Backend should NOT wait synchronously
- Use Redis Streams async pattern

### 4. Error Handling
- If AI worker fails, it publishes error message
- Backend should log and continue
- Retry logic in AI workers (3 attempts)

---

## 📄 What AI Team Needs From Backend

1. **Confirmation** that all 7 read model tables are created
2. **Confirmation** that Redis Streams consumers are implemented
3. **Test data** - sample posts with images for integration testing
4. **Access** to staging database to verify data
5. **Notification** when backend changes are deployed

---

**Any questions? Let's discuss on Slack: #kaleidoscope-integration** 🚀

