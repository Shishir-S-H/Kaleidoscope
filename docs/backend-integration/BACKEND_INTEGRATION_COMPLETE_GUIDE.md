# 🔗 Backend Integration Complete Guide

**Date**: January 2025  
**From**: AI/Elasticsearch Team  
**To**: Backend Development Team  
**Status**: Production-Ready Integration Specification

---

## 📋 Executive Summary

This guide provides **everything** the backend team needs to integrate with the Kaleidoscope AI microservices platform. The AI services are **100% complete and tested**, ready for backend integration.

### 🎯 What You Need to Implement

1. **7 PostgreSQL Read Model Tables** - Simplified, backend-owned tables
2. **Redis Streams Integration** - Publish/consume messages
3. **Sync Triggers** - Update Elasticsearch when data changes
4. **API Endpoints** - Expose search and recommendation functionality

### ✅ What's Already Complete (AI Team)

- ✅ All 5 AI microservices operational
- ✅ Post aggregation service
- ✅ Elasticsearch sync service
- ✅ 7 Elasticsearch indices with proper mappings
- ✅ Redis Streams message formats
- ✅ Complete testing and validation
- ✅ Docker containerization

---

## 🏗️ Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Backend Team                             │
│  (Spring Boot + PostgreSQL + Redis Streams)                 │
│                                                              │
│  Your Responsibilities:                                      │
│  ├── Create 7 PostgreSQL read model tables                   │
│  ├── Publish image processing jobs                           │
│  ├── Consume AI results                                      │
│  ├── Update PostgreSQL with AI insights                     │
│  └── Trigger Elasticsearch sync                             │
└─────────────────────────────────────────────────────────────┘
                         │                    ▲
                         │ Publishes          │ Consumes
                         ▼                    │
┌─────────────────────────────────────────────────────────────┐
│                   Redis Streams                              │
│  (Message Queue - Already in your stack)                    │
│                                                              │
│  Streams You'll Use:                                        │
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
│                   AI Team (Complete)                        │
│  (5 AI Services + Post Aggregator + ES Sync)                │
│                                                              │
│  Our Responsibilities:                                       │
│  ├── Process images through AI services                     │
│  ├── Aggregate multi-image insights                         │
│  ├── Sync data to Elasticsearch                             │
│  └── Maintain search indices                                │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ Indexes documents
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                 Elasticsearch (7 Indices)                   │
│                                                              │
│  Indices Ready for Use:                                     │
│  ├── media_search (media content search)                    │
│  ├── post_search (post-level search)                        │
│  ├── user_search (user profile search)                      │
│  ├── face_search (face recognition)                         │
│  ├── recommendations_knn (KNN recommendations)              │
│  ├── feed_personalized (personalized feed)                  │
│  └── known_faces_index (known faces database)               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Database Implementation

### Step 1: Create 7 Read Model Tables

**Location**: Same PostgreSQL database as your core tables  
**Ownership**: 100% backend team responsibility  
**Design**: Simplified, no foreign keys, optimized for Elasticsearch

#### Table 1: `media_search_read_model`

```sql
CREATE TABLE media_search_read_model (
    media_id BIGINT PRIMARY KEY,
    post_id BIGINT NOT NULL,
    post_title VARCHAR(255),
    post_all_tags TEXT[],
    media_url VARCHAR(500),
    ai_caption TEXT,
    ai_tags TEXT[],
    ai_scenes TEXT[],
    image_embedding VECTOR(512),
    is_safe BOOLEAN NOT NULL DEFAULT true,
    detected_users JSONB,
    uploader_id BIGINT,
    uploader_username VARCHAR(50),
    uploader_department VARCHAR(100),
    reaction_count BIGINT DEFAULT 0,
    comment_count BIGINT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_media_search_post_id ON media_search_read_model(post_id);
CREATE INDEX idx_media_search_uploader ON media_search_read_model(uploader_id);
CREATE INDEX idx_media_search_created_at ON media_search_read_model(created_at);
```

#### Table 2: `post_search_read_model`

```sql
CREATE TABLE post_search_read_model (
    post_id BIGINT PRIMARY KEY,
    post_title VARCHAR(255),
    post_description TEXT,
    aggregated_tags TEXT[],
    combined_caption TEXT,
    event_type VARCHAR(50),
    total_faces BIGINT DEFAULT 0,
    total_media_count BIGINT DEFAULT 0,
    is_safe BOOLEAN NOT NULL DEFAULT true,
    uploader_id BIGINT,
    uploader_username VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_post_search_uploader ON post_search_read_model(uploader_id);
CREATE INDEX idx_post_search_event_type ON post_search_read_model(event_type);
CREATE INDEX idx_post_search_created_at ON post_search_read_model(created_at);
```

#### Table 3: `user_search_read_model`

```sql
CREATE TABLE user_search_read_model (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    full_name VARCHAR(100),
    bio TEXT,
    interests TEXT[],
    department VARCHAR(100),
    profile_picture_url VARCHAR(500),
    follower_count BIGINT DEFAULT 0,
    following_count BIGINT DEFAULT 0,
    post_count BIGINT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_user_search_username ON user_search_read_model(username);
CREATE INDEX idx_user_search_department ON user_search_read_model(department);
```

#### Table 4: `face_search_read_model`

```sql
CREATE TABLE face_search_read_model (
    face_id BIGSERIAL PRIMARY KEY,
    media_id BIGINT NOT NULL,
    post_id BIGINT NOT NULL,
    face_embedding VECTOR(1024),
    confidence FLOAT,
    bounding_box JSONB,
    detected_user_id BIGINT,
    detected_username VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_face_search_media_id ON face_search_read_model(media_id);
CREATE INDEX idx_face_search_post_id ON face_search_read_model(post_id);
CREATE INDEX idx_face_search_detected_user ON face_search_read_model(detected_user_id);
```

#### Table 5: `recommendations_knn_read_model`

```sql
CREATE TABLE recommendations_knn_read_model (
    media_id BIGINT PRIMARY KEY,
    image_embedding VECTOR(512),
    content_type VARCHAR(50),
    tags TEXT[],
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_recommendations_content_type ON recommendations_knn_read_model(content_type);
CREATE INDEX idx_recommendations_created_at ON recommendations_knn_read_model(created_at);
```

#### Table 6: `feed_personalized_read_model`

```sql
CREATE TABLE feed_personalized_read_model (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    post_id BIGINT NOT NULL,
    score FLOAT NOT NULL,
    reason VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_feed_personalized_user_id ON feed_personalized_read_model(user_id);
CREATE INDEX idx_feed_personalized_score ON feed_personalized_read_model(score);
CREATE UNIQUE INDEX idx_feed_personalized_user_post ON feed_personalized_read_model(user_id, post_id);
```

#### Table 7: `known_faces_index_read_model`

```sql
CREATE TABLE known_faces_index_read_model (
    face_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(50) NOT NULL,
    face_embedding VECTOR(1024),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_known_faces_user_id ON known_faces_index_read_model(user_id);
CREATE INDEX idx_known_faces_username ON known_faces_index_read_model(username);
```

### Step 2: Enable pgvector Extension

```sql
-- Enable pgvector extension for vector operations
CREATE EXTENSION IF NOT EXISTS vector;
```

---

## 🔄 Redis Streams Integration

### Message Formats

#### 1. Publish Image Processing Job

**Stream**: `post-image-processing`  
**When**: User uploads images to a post  
**Format**:

```json
{
  "job_id": "job_12345",
  "post_id": 100,
  "media_id": 500,
  "image_url": "https://your-cdn.com/image.jpg",
  "user_id": 1,
  "timestamp": "2025-01-15T10:00:00Z"
}
```

**Java Implementation**:

```java
@Service
public class ImageProcessingService {

    @Autowired
    private RedisTemplate<String, Object> redisTemplate;

    public void publishImageProcessingJob(Long postId, Long mediaId, String imageUrl, Long userId) {
        Map<String, Object> jobData = new HashMap<>();
        jobData.put("job_id", UUID.randomUUID().toString());
        jobData.put("post_id", postId);
        jobData.put("media_id", mediaId);
        jobData.put("image_url", imageUrl);
        jobData.put("user_id", userId);
        jobData.put("timestamp", Instant.now().toString());

        redisTemplate.opsForStream().add("post-image-processing", jobData);
    }
}
```

#### 2. Consume AI Results

**Stream**: `ml-insights-results`  
**When**: AI services complete processing  
**Format**:

```json
{
  "job_id": "job_12345",
  "media_id": 500,
  "post_id": 100,
  "ai_insights": {
    "content_moderation": {
      "is_safe": true,
      "confidence": 0.95
    },
    "image_tagger": {
      "tags": ["beach", "sunset", "ocean"],
      "confidence": 0.89
    },
    "scene_recognition": {
      "scenes": ["beach", "outdoor"],
      "confidence": 0.92
    },
    "image_captioning": {
      "caption": "Beautiful sunset at the beach with calm ocean waves"
    }
  },
  "timestamp": "2025-01-15T10:00:30Z"
}
```

**Java Implementation**:

```java
@Component
public class AIResultsConsumer {

    @Autowired
    private MediaAiInsightsService mediaAiInsightsService;

    @StreamListener("ml-insights-results")
    public void handleAIResults(Map<String, Object> message) {
        String jobId = (String) message.get("job_id");
        Long mediaId = Long.valueOf(message.get("media_id").toString());
        Long postId = Long.valueOf(message.get("post_id").toString());

        @SuppressWarnings("unchecked")
        Map<String, Object> aiInsights = (Map<String, Object>) message.get("ai_insights");

        // Update your core MediaAiInsights table
        mediaAiInsightsService.updateAIInsights(mediaId, aiInsights);

        // Update read model table
        updateMediaSearchReadModel(mediaId, postId, aiInsights);

        // Trigger Elasticsearch sync
        triggerElasticsearchSync("media_search", mediaId);
    }
}
```

#### 3. Consume Face Detection Results

**Stream**: `face-detection-results`  
**When**: Face recognition service completes  
**Format**:

```json
{
  "job_id": "job_12345",
  "media_id": 500,
  "post_id": 100,
  "faces": [
    {
      "face_id": 1001,
      "confidence": 0.95,
      "bounding_box": {
        "x": 100,
        "y": 150,
        "width": 200,
        "height": 250
      },
      "detected_user_id": 1,
      "detected_username": "alice"
    }
  ],
  "timestamp": "2025-01-15T10:00:35Z"
}
```

#### 4. Trigger Post Aggregation

**Stream**: `post-aggregation-trigger`  
**When**: All images in a post are processed  
**Format**:

```json
{
  "post_id": 100,
  "trigger_reason": "all_images_processed",
  "timestamp": "2025-01-15T10:01:00Z"
}
```

#### 5. Consume Enriched Post Insights

**Stream**: `post-insights-enriched`  
**When**: Post aggregator completes  
**Format**:

```json
{
  "post_id": 100,
  "enriched_insights": {
    "aggregated_tags": ["beach", "sunset", "team", "outdoor"],
    "combined_caption": "Team outing at the beach during sunset",
    "event_type": "team_outing",
    "total_faces": 5,
    "total_media_count": 3,
    "is_safe": true
  },
  "timestamp": "2025-01-15T10:01:30Z"
}
```

#### 6. Trigger Elasticsearch Sync

**Stream**: `es-sync-queue`  
**When**: Read model data changes  
**Format**:

```json
{
  "operation": "index",
  "indexType": "media_search",
  "documentId": "media_500",
  "documentData": "{...full document data...}"
}
```

---

## 🔧 Implementation Steps

### Phase 1: Database Setup (Week 1)

1. **Create Read Model Tables**

   ```sql
   -- Run all CREATE TABLE statements above
   -- Enable pgvector extension
   ```

2. **Create JPA Entities**

   ```java
   @Entity
   @Table(name = "media_search_read_model")
   public class MediaSearchReadModel {
       @Id
       private Long mediaId;

       @Column(name = "post_id")
       private Long postId;

       @Column(name = "ai_caption")
       private String aiCaption;

       @Column(name = "ai_tags", columnDefinition = "text[]")
       private String[] aiTags;

       @Column(name = "image_embedding", columnDefinition = "vector(512)")
       private float[] imageEmbedding;

       // ... other fields
   }
   ```

### Phase 2: Redis Streams Integration (Week 2)

1. **Add Redis Streams Dependencies**

   ```xml
   <dependency>
       <groupId>org.springframework.boot</groupId>
       <artifactId>spring-boot-starter-data-redis</artifactId>
   </dependency>
   ```

2. **Configure Redis Streams**

   ```yaml
   spring:
     redis:
       host: localhost
       port: 6379
       stream:
         consumer:
           group: backend-group
   ```

3. **Implement Publishers and Consumers**
   - Image processing job publisher
   - AI results consumer
   - Face detection consumer
   - Post aggregation trigger
   - Enriched insights consumer
   - Elasticsearch sync trigger

### Phase 3: Business Logic (Week 3)

1. **Update Read Models**

   - When AI results arrive
   - When post aggregation completes
   - When user data changes

2. **Trigger Elasticsearch Sync**

   - After read model updates
   - Batch processing for efficiency

3. **Error Handling**
   - Retry mechanisms
   - Dead letter queues
   - Monitoring and alerting

### Phase 4: API Endpoints (Week 4)

1. **Search APIs**

   ```java
   @RestController
   @RequestMapping("/api/search")
   public class SearchController {

       @GetMapping("/media")
       public ResponseEntity<SearchResult> searchMedia(
           @RequestParam String query,
           @RequestParam(defaultValue = "0") int page,
           @RequestParam(defaultValue = "20") int size) {
           // Query Elasticsearch media_search index
       }

       @GetMapping("/posts")
       public ResponseEntity<SearchResult> searchPosts(
           @RequestParam String query,
           @RequestParam(required = false) String eventType) {
           // Query Elasticsearch post_search index
       }

       @GetMapping("/users")
       public ResponseEntity<SearchResult> searchUsers(
           @RequestParam String query,
           @RequestParam(required = false) String department) {
           // Query Elasticsearch user_search index
       }
   }
   ```

2. **Recommendation APIs**

   ```java
   @GetMapping("/recommendations/{userId}")
   public ResponseEntity<List<Recommendation>> getRecommendations(
       @PathVariable Long userId,
       @RequestParam(defaultValue = "10") int limit) {
       // Query Elasticsearch recommendations_knn index
   }
   ```

3. **Face Recognition APIs**
   ```java
   @PostMapping("/faces/search")
   public ResponseEntity<List<FaceMatch>> searchFaces(
       @RequestBody FaceSearchRequest request) {
       // Query Elasticsearch face_search index
   }
   ```

---

## 🧪 Testing Integration

### Test Data Setup

1. **Create Test Users**

   ```sql
   INSERT INTO users (username, email, full_name, department) VALUES
   ('alice', 'alice@company.com', 'Alice Smith', 'Engineering'),
   ('bob', 'bob@company.com', 'Bob Johnson', 'Marketing');
   ```

2. **Create Test Posts**

   ```sql
   INSERT INTO posts (user_id, title, description) VALUES
   (1, 'Team Outing', 'Great day at the beach'),
   (2, 'Product Launch', 'Exciting new features');
   ```

3. **Upload Test Images**
   - Use your existing image upload functionality
   - Images will automatically trigger AI processing

### Integration Testing

1. **End-to-End Flow Test**

   ```java
   @Test
   public void testCompleteImageProcessingFlow() {
       // 1. Upload image
       Long mediaId = uploadTestImage();

       // 2. Verify AI processing
       await().atMost(30, SECONDS).until(() ->
           mediaAiInsightsService.hasAIInsights(mediaId));

       // 3. Verify read model update
       assertThat(mediaSearchReadModelRepository.findById(mediaId))
           .isPresent();

       // 4. Verify Elasticsearch sync
       await().atMost(10, SECONDS).until(() ->
           elasticsearchService.documentExists("media_search", "media_" + mediaId));
   }
   ```

2. **Search Functionality Test**

   ```java
   @Test
   public void testSearchFunctionality() {
       // Search for media
       SearchResult result = searchService.searchMedia("beach", 0, 10);
       assertThat(result.getHits()).isNotEmpty();

       // Search for posts
       SearchResult posts = searchService.searchPosts("team", null);
       assertThat(posts.getHits()).isNotEmpty();
   }
   ```

---

## 📊 Monitoring & Observability

### Key Metrics to Track

1. **Processing Metrics**

   - Images processed per minute
   - AI processing latency
   - Error rates by service

2. **Search Metrics**

   - Search query latency
   - Search result relevance
   - Popular search terms

3. **System Health**
   - Redis Stream lag
   - Elasticsearch cluster health
   - Database connection pool

### Logging Strategy

```java
@Slf4j
@Service
public class ImageProcessingService {

    public void publishImageProcessingJob(Long postId, Long mediaId, String imageUrl, Long userId) {
        log.info("Publishing image processing job: postId={}, mediaId={}, userId={}",
                 postId, mediaId, userId);

        try {
            // Publish to Redis Stream
            redisTemplate.opsForStream().add("post-image-processing", jobData);

            log.info("Successfully published image processing job: jobId={}", jobId);
        } catch (Exception e) {
            log.error("Failed to publish image processing job: postId={}, error={}",
                     postId, e.getMessage(), e);
            throw e;
        }
    }
}
```

---

## 🚀 Production Deployment

### Environment Configuration

```yaml
# application-prod.yml
spring:
  redis:
    host: ${REDIS_HOST:redis-cluster.company.com}
    port: ${REDIS_PORT:6379}
    password: ${REDIS_PASSWORD}
    ssl: true

  datasource:
    url: jdbc:postgresql://${DB_HOST:postgres-cluster.company.com}:5432/kaleidoscope
    username: ${DB_USERNAME}
    password: ${DB_PASSWORD}
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5

elasticsearch:
  host: ${ES_HOST:elasticsearch-cluster.company.com}
  port: ${ES_PORT:9200}
  username: ${ES_USERNAME}
  password: ${ES_PASSWORD}
  ssl: true
```

### Security Considerations

1. **Redis Security**

   - Enable authentication
   - Use TLS encryption
   - Network isolation

2. **Database Security**

   - Connection encryption
   - Role-based access
   - Audit logging

3. **Elasticsearch Security**
   - X-Pack security
   - API key authentication
   - Index-level permissions

---

## 📞 Support & Resources

### Documentation References

- **[DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)** - Full database schema
- **[READ_MODELS.md](READ_MODELS.md)** - Read model implementation
- **[POST_AGGREGATION_EXPLAINED.md](POST_AGGREGATION_EXPLAINED.md)** - Post aggregation strategy

### Testing Resources

- **[Kaleidoscope_AI_API_Tests.postman_collection.json](Kaleidoscope_AI_API_Tests.postman_collection.json)** - Postman collection

### Contact Information

- **AI Team Lead**: [Your Name]
- **Technical Questions**: [Your Email]
- **Integration Support**: [Your Slack Channel]

---

## ✅ Checklist for Backend Team

### Week 1: Database Setup

- [ ] Create 7 read model tables
- [ ] Enable pgvector extension
- [ ] Create JPA entities
- [ ] Set up database migrations

### Week 2: Redis Integration

- [ ] Add Redis Streams dependencies
- [ ] Configure Redis connection
- [ ] Implement image processing publisher
- [ ] Implement AI results consumer
- [ ] Implement face detection consumer

### Week 3: Business Logic

- [ ] Update read models on AI results
- [ ] Implement post aggregation trigger
- [ ] Implement enriched insights consumer
- [ ] Implement Elasticsearch sync trigger
- [ ] Add error handling and retries

### Week 4: API Development

- [ ] Implement search APIs
- [ ] Implement recommendation APIs
- [ ] Implement face recognition APIs
- [ ] Add comprehensive testing
- [ ] Performance optimization

### Week 5: Production Ready

- [ ] Security review
- [ ] Performance testing
- [ ] Monitoring setup
- [ ] Documentation review
- [ ] Deployment preparation

---

**🎉 The AI services are ready and waiting for your integration!**

**Next Step**: Start with Week 1 - Database Setup. All the SQL scripts and JPA entity examples are provided above.

**Questions?** Refer to the detailed documentation or contact the AI team for support.
