# 📊 Simplified Read Model Tables - Backend Team Specification

**Date**: October 15, 2025  
**Owner**: Backend Team (Spring Boot)  
**Consumer**: AI Team (Elasticsearch Sync Service)  
**Database**: Same PostgreSQL as core tables

---

## 🎯 Key Design Principles

1. **Simplified**: Only essential fields for search, no extras
2. **Independent**: No foreign keys, completely denormalized (copy all data)
3. **Backend-Owned**: Backend team creates, updates, and maintains
4. **Read-Only for AI Team**: AI team only reads for ES sync
5. **Single Source of Truth**: These tables feed Elasticsearch

---

## 📋 Table 1: `read_model_media_search`

**Purpose**: Individual media (image) search  
**ES Index**: `media_search`

```sql
CREATE TABLE read_model_media_search (
    -- IDs
    media_id BIGINT PRIMARY KEY,
    post_id BIGINT NOT NULL,

    -- Post Context (copied from posts table)
    post_title VARCHAR(200),
    post_all_tags TEXT[],              -- Aggregated from ALL media in post

    -- Media Info (copied from post_media table)
    media_url VARCHAR(1000) NOT NULL,

    -- AI Insights (copied from media_ai_insights table)
    ai_caption TEXT,
    ai_tags TEXT[],
    ai_scenes TEXT[],
    image_embedding TEXT,              -- 512-dim vector as JSON string "[0.1, 0.2, ...]"
    is_safe BOOLEAN DEFAULT true,

    -- Detected Faces (aggregated from media_detected_faces)
    detected_user_ids BIGINT[],
    detected_usernames TEXT[],

    -- Uploader (copied from users table)
    uploader_id BIGINT NOT NULL,
    uploader_username VARCHAR(50) NOT NULL,
    uploader_department VARCHAR(100),

    -- Engagement (copied from posts/reactions/comments tables)
    reaction_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for performance
CREATE INDEX idx_rms_post ON read_model_media_search(post_id);
CREATE INDEX idx_rms_updated ON read_model_media_search(updated_at DESC);

COMMENT ON TABLE read_model_media_search IS 'Simplified denormalized table for media search - synced to ES media_search index';
```

**When Backend Updates**:

- ✅ When AI insights arrive (from Redis Stream `ml-insights-results`)
- ✅ When post aggregation completes (update `post_all_tags`)
- ✅ When faces identified (update `detected_user_ids`)
- ✅ When engagement changes (reactions, comments)

---

## 📋 Table 2: `read_model_post_search`

**Purpose**: Post-level search  
**ES Index**: `post_search`

```sql
CREATE TABLE read_model_post_search (
    -- IDs
    post_id BIGINT PRIMARY KEY,

    -- Author (copied from users table)
    author_id BIGINT NOT NULL,
    author_username VARCHAR(50) NOT NULL,
    author_department VARCHAR(100),

    -- Post Content (copied from posts table)
    title VARCHAR(200),
    body TEXT,

    -- Aggregated AI (union of all media AI results)
    all_ai_tags TEXT[],
    all_ai_scenes TEXT[],
    all_detected_user_ids BIGINT[],

    -- Post-Level AI (from post_aggregator service via Redis Stream)
    inferred_event_type VARCHAR(50),   -- "party", "meeting", etc.
    inferred_tags TEXT[],              -- ["beach_party", "team_event"]

    -- Categories (copied from posts table)
    categories TEXT[],

    -- Engagement (aggregated from all media)
    total_reactions INTEGER DEFAULT 0,
    total_comments INTEGER DEFAULT 0,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_rps_author ON read_model_post_search(author_id);
CREATE INDEX idx_rps_updated ON read_model_post_search(updated_at DESC);
```

**When Backend Updates**:

- ✅ When post created
- ✅ When all media AI complete (aggregate `all_ai_tags`)
- ✅ When post aggregation enriched data arrives (from Redis Stream)

---

## 📋 Table 3: `read_model_user_search`

**Purpose**: User discovery  
**ES Index**: `user_search`

```sql
CREATE TABLE read_model_user_search (
    -- IDs
    user_id BIGINT PRIMARY KEY,

    -- User Info (copied from users table)
    username VARCHAR(50) NOT NULL,
    full_name VARCHAR(100),
    department VARCHAR(100),
    bio TEXT,

    -- Stats (calculated)
    total_posts INTEGER DEFAULT 0,
    total_followers INTEGER DEFAULT 0,

    -- Face Enrollment (copied from read_model_known_faces)
    face_enrolled BOOLEAN DEFAULT false,

    -- Metadata
    joined_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_rus_department ON read_model_user_search(department);
```

**When Backend Updates**:

- ✅ When user profile updated
- ✅ When user posts/follows change
- ✅ When face enrolled

---

## 📋 Table 4: `read_model_face_search`

**Purpose**: Face-based media search  
**ES Index**: `face_search`

```sql
CREATE TABLE read_model_face_search (
    -- IDs
    id BIGSERIAL PRIMARY KEY,
    face_id VARCHAR(50) UNIQUE NOT NULL,
    media_id BIGINT NOT NULL,
    post_id BIGINT NOT NULL,

    -- Face Data (copied from media_detected_faces)
    face_embedding TEXT NOT NULL,      -- 1024-dim vector as JSON string
    bbox INTEGER[],                    -- [x, y, w, h]

    -- Identification (computed by backend)
    identified_user_id BIGINT,
    identified_username VARCHAR(50),
    match_confidence FLOAT,

    -- Context (copied for search display)
    uploader_id BIGINT NOT NULL,
    post_title VARCHAR(200),
    media_url VARCHAR(1000),

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_rfs_identified_user ON read_model_face_search(identified_user_id);
CREATE INDEX idx_rfs_media ON read_model_face_search(media_id);
```

**When Backend Updates**:

- ✅ When face detected (from Redis Stream `face-detection-results`)
- ✅ When face identified (after KNN matching)

---

## 📋 Table 5: `read_model_recommendations_knn`

**Purpose**: Lightweight visual similarity  
**ES Index**: `recommendations_knn`

```sql
CREATE TABLE read_model_recommendations_knn (
    -- IDs
    media_id BIGINT PRIMARY KEY,

    -- Minimal fields for KNN
    image_embedding TEXT NOT NULL,     -- 512-dim vector as JSON string
    media_url VARCHAR(1000) NOT NULL,
    caption TEXT,
    is_safe BOOLEAN DEFAULT true,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL
);
```

**When Backend Updates**:

- ✅ When AI insights arrive with embedding

---

## 📋 Table 6: `read_model_feed_personalized`

**Purpose**: Pre-computed personalized feed  
**ES Index**: `feed_personalized`

```sql
CREATE TABLE read_model_feed_personalized (
    -- IDs
    id BIGSERIAL PRIMARY KEY,
    feed_item_id VARCHAR(100) UNIQUE NOT NULL,
    target_user_id BIGINT NOT NULL,    -- User who will see this in feed
    media_id BIGINT NOT NULL,

    -- Content (copied)
    media_url VARCHAR(1000),
    caption TEXT,

    -- Uploader (copied from users table)
    uploader_id BIGINT NOT NULL,
    uploader_username VARCHAR(50),

    -- Relevance (computed by backend algorithm)
    combined_score FLOAT DEFAULT 0,    -- Higher = more relevant

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ             -- TTL for feed items (e.g., 7 days)
);

CREATE INDEX idx_rfp_target_score ON read_model_feed_personalized(target_user_id, combined_score DESC);
CREATE INDEX idx_rfp_expires ON read_model_feed_personalized(expires_at);
```

**When Backend Updates**:

- ✅ Periodically (e.g., every hour) - compute personalized feeds
- ✅ When new post published - add to relevant user feeds

---

## 📋 Table 7: `read_model_known_faces`

**Purpose**: Face enrollment database  
**ES Index**: `known_faces_index`

```sql
CREATE TABLE read_model_known_faces (
    -- IDs
    user_id BIGINT PRIMARY KEY,

    -- User Info (copied from users table)
    username VARCHAR(50) NOT NULL,
    department VARCHAR(100),
    profile_pic_url VARCHAR(255),

    -- Face Data (from face enrollment API)
    face_embedding TEXT NOT NULL,      -- 1024-dim vector as JSON string

    -- Metadata
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active BOOLEAN DEFAULT true
);

CREATE INDEX idx_rkf_active ON read_model_known_faces(is_active) WHERE is_active = true;
```

**When Backend Updates**:

- ✅ When user enrolls face (from your face enrollment API)
- ✅ When user updates profile picture (trigger re-enrollment)
- ✅ When user deactivates enrollment

---

## 🔄 Backend Update Flow

### Example: Post with 3 Images Published

```
1. User uploads post → Backend saves to posts, post_media tables

2. Backend publishes to Redis Stream: post-image-processing (3 messages)

3. AI workers process → Publish results to ml-insights-results

4. Backend consumes ml-insights-results:
   a. Update media_ai_insights table (existing)
   b. Update read_model_media_search table (NEW)
      - Copy: post_title, media_url, uploader info
      - Insert: ai_caption, ai_tags, ai_scenes, image_embedding
   c. Publish to es-sync-queue: { indexName: "media_search", documentId: 201 }

5. When all 3 media done → Backend triggers post-aggregation-trigger

6. AI Post Aggregator analyzes → Publishes to post-insights-enriched

7. Backend consumes post-insights-enriched:
   a. Update read_model_post_search table
      - Insert: all_ai_tags, inferred_event_type
   b. Update ALL 3 read_model_media_search rows
      - Update: post_all_tags (same for all 3)
   c. Publish to es-sync-queue: { indexName: "post_search", documentId: 100 }
   c. Publish to es-sync-queue: { indexName: "media_search", operation: "BULK", documentId: 100 }

8. AI ES Sync Worker:
   a. Read from read_model_media_search table
   b. Transform to ES document format
   c. Index to Elasticsearch
```

---

## 📝 Backend Implementation Guide

### Step 1: Create Tables (Migration Script)

```sql
-- File: V2__create_read_models.sql
-- All 7 tables above
```

### Step 2: Create JPA Entities

```java
@Entity
@Table(name = "read_model_media_search")
public class ReadModelMediaSearch {
    @Id
    private Long mediaId;
    private Long postId;
    private String postTitle;

    @Type(type = "string-array")
    @Column(columnDefinition = "text[]")
    private String[] postAllTags;

    private String mediaUrl;
    private String aiCaption;

    @Type(type = "string-array")
    @Column(columnDefinition = "text[]")
    private String[] aiTags;

    @Type(type = "string-array")
    @Column(columnDefinition = "text[]")
    private String[] aiScenes;

    private String imageEmbedding;  // JSON string
    private Boolean isSafe;

    @Type(type = "long-array")
    @Column(columnDefinition = "bigint[]")
    private Long[] detectedUserIds;

    @Type(type = "string-array")
    @Column(columnDefinition = "text[]")
    private String[] detectedUsernames;

    private Long uploaderId;
    private String uploaderUsername;
    private String uploaderDepartment;

    private Integer reactionCount;
    private Integer commentCount;

    private Instant createdAt;
    private Instant updatedAt;

    // Getters, setters, builder
}
```

### Step 3: Update Read Models After AI Results

```java
@Service
public class ReadModelUpdater {

    @Autowired
    private ReadModelMediaSearchRepository readModelMediaSearchRepo;

    @Autowired
    private RedisStreamPublisher redisPublisher;

    @Transactional
    public void updateMediaSearch(Long mediaId, MediaAiInsightsResultDTO aiResult) {
        // Get data from core tables
        PostMedia media = postMediaRepo.findById(mediaId).orElseThrow();
        Post post = media.getPost();
        User uploader = post.getUser();

        // Build read model
        ReadModelMediaSearch readModel = ReadModelMediaSearch.builder()
            .mediaId(mediaId)
            .postId(post.getPostId())
            .postTitle(post.getTitle())
            .postAllTags(new String[0])  // Will be updated after aggregation
            .mediaUrl(media.getMediaUrl())
            .aiCaption(aiResult.getCaption())
            .aiTags(aiResult.getTags())
            .aiScenes(aiResult.getScenes())
            .imageEmbedding(aiResult.getImageEmbedding())  // Already JSON string
            .isSafe(aiResult.getIsSafe())
            .uploaderId(uploader.getUserId())
            .uploaderUsername(uploader.getUsername())
            .uploaderDepartment(uploader.getDepartment())
            .reactionCount(post.getReactions().size())
            .commentCount(post.getComments().size())
            .createdAt(media.getCreatedAt())
            .build();

        // Save to read model table
        readModelMediaSearchRepo.save(readModel);

        // Trigger ES sync
        redisPublisher.publish("es-sync-queue", Map.of(
            "indexName", "media_search",
            "operation", "INDEX",
            "documentId", String.valueOf(mediaId)
        ));
    }
}
```

### Step 4: Update After Post Aggregation

```java
@StreamListener("post-insights-enriched")
@Transactional
public void onPostAggregationComplete(PostInsightsEnrichedDTO enriched) {
    Long postId = enriched.getPostId();
    String[] allAiTags = enriched.getAllAiTags();

    // 1. Update post search read model
    ReadModelPostSearch postSearch = ReadModelPostSearch.builder()
        .postId(postId)
        .allAiTags(allAiTags)
        .inferredEventType(enriched.getInferredEventType())
        .inferredTags(enriched.getInferredTags())
        // ... other fields
        .build();
    readModelPostSearchRepo.save(postSearch);

    // 2. Update ALL media in this post with post_all_tags
    List<ReadModelMediaSearch> mediaModels =
        readModelMediaSearchRepo.findByPostId(postId);

    for (ReadModelMediaSearch media : mediaModels) {
        media.setPostAllTags(allAiTags);
    }
    readModelMediaSearchRepo.saveAll(mediaModels);

    // 3. Trigger ES sync
    redisPublisher.publish("es-sync-queue", Map.of(
        "indexName", "post_search",
        "documentId", String.valueOf(postId)
    ));

    redisPublisher.publish("es-sync-queue", Map.of(
        "indexName", "media_search",
        "operation", "BULK",
        "documentId", String.valueOf(postId)  // Sync all media in post
    ));
}
```

---

## ✅ Backend Team Checklist

### Database Setup

- [ ] Create migration `V2__create_read_models.sql` with all 7 tables
- [ ] Run migration on dev database
- [ ] Verify tables created successfully

### JPA Entities

- [ ] Create 7 JPA entity classes for read models
- [ ] Create 7 repository interfaces
- [ ] Test basic CRUD operations

### Update Logic

- [ ] Implement `ReadModelUpdater` service
- [ ] Hook into `MediaAiInsightsConsumer` to update `read_model_media_search`
- [ ] Hook into `PostAggregationConsumer` to update `read_model_post_search`
- [ ] Hook into `FaceDetectionConsumer` to update `read_model_face_search`

### ES Sync Publishing

- [ ] Publish to `es-sync-queue` after each read model update
- [ ] Test Redis Stream publishing

### Testing

- [ ] Test with 1 image post → verify read model populated
- [ ] Test with 3 image post → verify post aggregation updates all 3 media
- [ ] Test face detection → verify face search table populated

---

## 🤝 AI Team Responsibilities

**AI team (you) will**:

1. ✅ Create 7 Elasticsearch indices with mappings
2. ✅ Build ES sync service that:
   - Consumes from `es-sync-queue`
   - Reads from these 7 read model tables
   - Maps to ES documents
   - Indexes to Elasticsearch
3. ✅ Build post aggregator that analyzes multi-image posts

**AI team will NOT touch these tables directly** - only read for ES sync.

---

## 📄 Summary

**7 Simplified Read Model Tables**:

1. `read_model_media_search` - 16 fields (media search)
2. `read_model_post_search` - 13 fields (post search)
3. `read_model_user_search` - 9 fields (user discovery)
4. `read_model_face_search` - 12 fields (face search)
5. `read_model_recommendations_knn` - 5 fields (visual similarity)
6. `read_model_feed_personalized` - 9 fields (personalized feeds)
7. `read_model_known_faces` - 7 fields (face enrollment)

**Key Benefits**:

- ✅ Simplified (only essential fields)
- ✅ Independent (no foreign keys)
- ✅ Backend-owned (clear ownership)
- ✅ Easy to maintain
- ✅ Optimized for search

**Share this document with your backend teammate!** 🚀
