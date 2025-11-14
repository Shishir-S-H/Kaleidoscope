# System Architecture

**Architecture overview for Kaleidoscope AI**

---

## High-Level Architecture

```
Backend (Spring Boot)
    │
    │ Publishes image job
    ▼
Redis Stream: post-image-processing
    │
    │ Consumed by 5 AI services
    ▼
┌─────────────┬─────────────┬─────────────┐
│ Content Mod │ Image Tagger│ Scene Recog │
└──────┬──────┴──────┬──────┴──────┬──────┘
       │             │              │
       ▼             ▼              ▼
Redis Stream: ml-insights-results
    │
    │ Consumed by Post Aggregator
    ▼
Redis Stream: post-insights-enriched
    │
    │ Consumed by Backend
    ▼
PostgreSQL Read Models
    │
    │ Triggers ES sync
    ▼
Redis Stream: es-sync-queue
    │
    │ Consumed by ES Sync
    ▼
Elasticsearch (7 Indices)
```

---

## Components

### AI Services (5 Services)

1. **Content Moderation** - NSFW detection
2. **Image Tagger** - Object/scene tagging
3. **Scene Recognition** - Environment detection
4. **Image Captioning** - Natural language descriptions
5. **Face Recognition** - Face detection & embeddings

**Technology**: HuggingFace Inference API  
**Input Stream**: `post-image-processing`  
**Output Streams**: `ml-insights-results`, `face-detection-results`

### Processing Services (2 Services)

1. **Post Aggregator** - Multi-image insights aggregation
2. **ES Sync** - PostgreSQL → Elasticsearch synchronization

**Technology**: Python 3.10, Redis Streams, Elasticsearch

---

## Data Flow

### Write Path (Image Processing)

1. Backend publishes image job to `post-image-processing`
2. 5 AI services consume and process in parallel
3. AI services publish results to `ml-insights-results` and `face-detection-results`
4. Post Aggregator collects all insights for a post
5. Post Aggregator publishes enriched insights to `post-insights-enriched`
6. Backend consumes enriched insights and updates PostgreSQL
7. Backend triggers ES sync via `es-sync-queue`
8. ES Sync reads from PostgreSQL and indexes to Elasticsearch

### Read Path (Search)

1. User performs search query
2. Backend queries Elasticsearch
3. Elasticsearch returns results
4. Backend returns results to user

---

## Infrastructure

### Redis Streams

- **Purpose**: Message broker for event-driven communication
- **Streams Used**:
  - `post-image-processing` - Image jobs
  - `ml-insights-results` - AI results
  - `face-detection-results` - Face detection results
  - `post-insights-enriched` - Aggregated insights
  - `es-sync-queue` - ES sync triggers
  - `ai-processing-dlq` - Dead letter queue

### Elasticsearch

- **Version**: 8.10.2
- **Indices**: 7 specialized indices
  - `media_search` - Individual media search
  - `post_search` - Post-level search
  - `user_search` - User profiles
  - `face_search` - Face search
  - `recommendations_knn` - Recommendations
  - `feed_personalized` - Personalized feeds
  - `known_faces_index` - Known faces

### PostgreSQL

- **Purpose**: Core database and read models
- **Read Models**: 7 denormalized tables for Elasticsearch sync

---

## Technology Stack

- **Python 3.10**: All microservices
- **Redis Streams**: Message broker
- **Elasticsearch 8.10.2**: Search engine
- **PostgreSQL**: Database
- **Docker**: Containerization
- **HuggingFace API**: AI model inference

---

## Service Details

### AI Services Pattern

All AI services follow the same pattern:

1. Consume from `post-image-processing`
2. Download image from URL
3. Call HuggingFace API
4. Process results
5. Publish to output stream
6. Handle errors and retries

### Post Aggregator

- Collects insights from all images in a post
- Waits for all required services to complete
- Aggregates tags, scenes, captions
- Detects event type
- Publishes enriched insights

### ES Sync

- Consumes from `es-sync-queue`
- Reads data from PostgreSQL read models
- Maps PostgreSQL data to Elasticsearch format
- Indexes to appropriate Elasticsearch index
- Handles retries and errors

---

## Performance

- **AI Processing**: 10-30s per image
- **Post Aggregation**: < 100ms
- **ES Sync**: < 100ms per document
- **Search**: ~44ms average

---

**For detailed integration, see [../backend-integration/BACKEND_INTEGRATION.md](../backend-integration/BACKEND_INTEGRATION.md)**
