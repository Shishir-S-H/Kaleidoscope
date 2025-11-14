# Elasticsearch Guide

**Elasticsearch setup and configuration for Kaleidoscope AI**

---

## Overview

Elasticsearch provides search capabilities across 7 specialized indices. The ES Sync service automatically synchronizes data from PostgreSQL read models to Elasticsearch.

---

## Indices

### 1. media_search

**Purpose**: Search individual images/media

**Key Fields**:

- `ai_caption` (text) - AI-generated caption
- `ai_tags` (keyword array) - AI-generated tags
- `ai_scenes` (keyword array) - Detected scenes
- `image_embedding` (dense_vector, 512-dim) - Image embedding
- `is_safe` (boolean) - Content safety
- `detected_users` (nested) - Detected users

**Use Cases**: Find specific images, filter by tags, vector similarity

---

### 2. post_search

**Purpose**: Search posts (aggregated)

**Key Fields**:

- `post_title` (text) - Post title
- `aggregated_tags` (keyword array) - Aggregated tags
- `combined_caption` (text) - Combined caption
- `inferred_event_type` (keyword) - Event type
- `total_faces` (integer) - Total faces
- `media_count` (integer) - Media count

**Use Cases**: Find posts by event type, search by content

---

### 3. user_search

**Purpose**: User discovery

**Key Fields**:

- `username` (text + keyword) - Username
- `full_name` (text) - Full name
- `bio` (text) - User bio
- `department` (keyword) - Department
- `interests` (keyword array) - Interests

**Use Cases**: Find colleagues, search by interests

---

### 4. face_search

**Purpose**: Search by detected faces

**Key Fields**:

- `face_id` (keyword) - Face ID
- `face_embedding` (dense_vector, 1024-dim) - Face embedding
- `media_id` (long) - Media ID
- `user_id` (long, optional) - Identified user

**Use Cases**: Find images with specific people, face similarity

---

### 5. recommendations_knn

**Purpose**: Content-based recommendations

**Key Fields**:

- `media_id` (long) - Media ID
- `image_embedding` (dense_vector, 512-dim) - Image embedding
- `tags` (keyword array) - Tags

**Use Cases**: Visual similarity, "more like this"

---

### 6. feed_personalized

**Purpose**: Personalized user feeds

**Key Fields**:

- `user_id` (long) - User ID
- `post_id` (long) - Post ID
- `user_interests` (keyword array) - User interests
- `content_tags` (keyword array) - Content tags
- `relevance_score` (float) - Relevance score

**Use Cases**: Personalized content discovery

---

### 7. known_faces_index

**Purpose**: Face enrollment and identification

**Key Fields**:

- `user_id` (long) - User ID
- `username` (keyword) - Username
- `face_embeddings` (dense_vector array, 1024-dim) - Face embeddings
- `enrollment_date` (date) - Enrollment date

**Use Cases**: Face identification, user tagging

---

## Setup

### Create Indices

```bash
# Run setup script
python scripts/setup/setup_es_indices.py
```

### Manual Creation

Index mappings are in `es_mappings/` directory:

- `media_search.json`
- `post_search.json`
- `user_search.json`
- `face_search.json`
- `recommendations_knn.json`
- `feed_personalized.json`
- `known_faces_index.json`

### Verify Indices

```bash
# List all indices
curl -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200/_cat/indices?v

# Check index mapping
curl -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200/media_search/_mapping
```

---

## Search Examples

### Text Search

```bash
curl "http://localhost:9200/media_search/_search?q=beach"
```

### Multi-Field Search

```bash
curl -X POST "http://localhost:9200/media_search/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "multi_match": {
        "query": "beach sunset",
        "fields": ["ai_caption", "ai_tags"]
      }
    }
  }'
```

### Vector Search (KNN)

```bash
curl -X POST "http://localhost:9200/recommendations_knn/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "knn": {
      "field": "image_embedding",
      "query_vector": [0.1, 0.2, ...],
      "k": 10
    }
  }'
```

### Filtered Search

```bash
curl -X POST "http://localhost:9200/media_search/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "bool": {
        "must": [{"match": {"ai_caption": "beach"}}],
        "filter": [{"term": {"is_safe": true}}]
      }
    }
  }'
```

---

## Data Synchronization

### Automatic Sync

ES Sync service automatically syncs data from PostgreSQL read models to Elasticsearch:

1. Backend updates PostgreSQL read model
2. Backend publishes to `es-sync-queue`
3. ES Sync consumes message
4. ES Sync reads from PostgreSQL
5. ES Sync indexes to Elasticsearch

### Manual Sync

```bash
# Trigger sync for a document
docker exec redis redis-cli -a ${REDIS_PASSWORD} XADD es-sync-queue "*" \
  operation index \
  indexType media_search \
  documentId 70001
```

---

## Maintenance

### Check Index Health

```bash
curl -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200/_cluster/health
```

### Check Index Stats

```bash
curl -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200/_cat/indices?v
```

### Delete Index (if needed)

```bash
curl -X DELETE -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200/media_search
```

---

**For search API details, see [API.md](API.md)**
