# 🚀 Complete curl Commands Reference

**Kaleidoscope AI - All curl Commands for API Testing**

This document provides all curl commands needed to test every aspect of the Kaleidoscope AI system.

---

## 📋 Quick Reference

### Infrastructure Health Checks

```bash
# Elasticsearch Health
curl -X GET "http://localhost:9200" \
  -H "Content-Type: application/json"

# Docker Services Status
curl -X GET "http://localhost:2375/containers/json" \
  -H "Content-Type: application/json"

# Redis Health (via Docker)
docker exec -it kaleidoscope-ai-redis-1 redis-cli ping
```

### Elasticsearch Management

```bash
# List All Indices
curl -X GET "http://localhost:9200/_cat/indices?v" \
  -H "Content-Type: application/json"

# Get Index Mapping
curl -X GET "http://localhost:9200/media_search/_mapping" \
  -H "Content-Type: application/json"

# Create Test Index
curl -X PUT "http://localhost:9200/test_index" \
  -H "Content-Type: application/json" \
  -d '{
    "mappings": {
      "properties": {
        "test_field": {"type": "text"},
        "created_at": {"type": "date"}
      }
    }
  }'

# Delete Test Index
curl -X DELETE "http://localhost:9200/test_index" \
  -H "Content-Type: application/json"

# Cluster Health
curl -X GET "http://localhost:9200/_cluster/health" \
  -H "Content-Type: application/json"

# Node Stats
curl -X GET "http://localhost:9200/_nodes/stats" \
  -H "Content-Type: application/json"
```

### Document Operations

```bash
# Index Document
curl -X POST "http://localhost:9200/media_search/_doc/test_doc_1" \
  -H "Content-Type: application/json" \
  -d '{
    "media_id": 12345,
    "post_id": 100,
    "post_title": "Test Post - Beach Vacation",
    "ai_caption": "Beautiful sunset at the beach with people enjoying the view",
    "ai_tags": ["beach", "sunset", "people", "vacation"],
    "ai_scenes": ["beach", "outdoor"],
    "image_embedding": [0.1, 0.2, 0.3, 0.4, 0.5],
    "is_safe": true,
    "detected_users": [
      {"user_id": 1, "username": "alice"},
      {"user_id": 2, "username": "bob"}
    ],
    "uploader_id": 1,
    "uploader_username": "alice",
    "uploader_department": "Engineering",
    "reaction_count": 42,
    "comment_count": 10,
    "created_at": "2025-10-15T10:00:00Z",
    "updated_at": "2025-10-15T10:00:00Z"
  }'

# Get Document by ID
curl -X GET "http://localhost:9200/media_search/_doc/test_doc_1" \
  -H "Content-Type: application/json"

# Update Document
curl -X POST "http://localhost:9200/media_search/_update/test_doc_1" \
  -H "Content-Type: application/json" \
  -d '{
    "doc": {
      "reaction_count": 50,
      "comment_count": 12,
      "updated_at": "2025-10-15T11:00:00Z"
    }
  }'

# Delete Document
curl -X DELETE "http://localhost:9200/media_search/_doc/test_doc_1" \
  -H "Content-Type: application/json"
```

### Search Operations

```bash
# Simple Text Search
curl -X GET "http://localhost:9200/media_search/_search?q=beach" \
  -H "Content-Type: application/json"

# Multi-Field Search
curl -X POST "http://localhost:9200/media_search/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "multi_match": {
        "query": "beach sunset",
        "fields": ["ai_caption", "ai_tags", "post_title"]
      }
    }
  }'

# Filtered Search
curl -X POST "http://localhost:9200/media_search/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "bool": {
        "must": [
          {"match": {"ai_caption": "beach"}}
        ],
        "filter": [
          {"term": {"is_safe": true}},
          {"range": {"reaction_count": {"gte": 40}}}
        ]
      }
    }
  }'

# Aggregations
curl -X POST "http://localhost:9200/media_search/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "size": 0,
    "aggs": {
      "popular_tags": {
        "terms": {
          "field": "ai_tags",
          "size": 10
        }
      },
      "avg_reactions": {
        "avg": {
          "field": "reaction_count"
        }
      },
      "safe_content": {
        "terms": {
          "field": "is_safe"
        }
      }
    }
  }'
```

### Vector Search (KNN)

```bash
# KNN Similarity Search
curl -X POST "http://localhost:9200/media_search/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "knn": {
      "field": "image_embedding",
      "query_vector": [0.1, 0.2, 0.3, 0.4, 0.5],
      "k": 5,
      "num_candidates": 100
    }
  }'

# Hybrid Search (Text + Vector)
curl -X POST "http://localhost:9200/media_search/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "bool": {
        "should": [
          {
            "multi_match": {
              "query": "beach sunset",
              "fields": ["ai_caption", "ai_tags"]
            }
          },
          {
            "knn": {
              "field": "image_embedding",
              "query_vector": [0.1, 0.2, 0.3, 0.4, 0.5],
              "k": 5,
              "num_candidates": 100
            }
          }
        ]
      }
    }
  }'
```

### Redis Streams Operations

```bash
# Check Stream Information
docker exec -it kaleidoscope-ai-redis-1 redis-cli XINFO STREAM post-image-processing

# List All Streams
docker exec -it kaleidoscope-ai-redis-1 redis-cli KEYS "*"

# Add Message to Stream
docker exec -it kaleidoscope-ai-redis-1 redis-cli XADD post-image-processing "*" job_id "test_job_123" post_id "100" media_id "500" image_url "https://example.com/test.jpg" user_id "1"

# Read Messages from Stream
docker exec -it kaleidoscope-ai-redis-1 redis-cli XREAD STREAMS post-image-processing 0

# Create Consumer Group
docker exec -it kaleidoscope-ai-redis-1 redis-cli XGROUP CREATE post-image-processing test-group 0 MKSTREAM

# Read from Consumer Group
docker exec -it kaleidoscope-ai-redis-1 redis-cli XREADGROUP GROUP test-group consumer1 COUNT 1 STREAMS post-image-processing ">"
```

### Service Health Checks

```bash
# Check Service Logs
curl -X GET "http://localhost:2375/containers/kaleidoscope-ai-content_moderation-1/logs?stdout=true&stderr=true&tail=10"

# Check Service Stats
curl -X GET "http://localhost:2375/containers/kaleidoscope-ai-content_moderation-1/stats"

# Check All Services Status
docker compose ps
```

### Advanced Elasticsearch Operations

```bash
# Bulk Index Operations
curl -X POST "http://localhost:9200/_bulk" \
  -H "Content-Type: application/x-ndjson" \
  --data-binary @- << EOF
{"index":{"_index":"media_search","_id":"bulk_doc_1"}}
{"media_id":11111,"post_id":200,"ai_caption":"Test bulk document 1","ai_tags":["test","bulk"],"is_safe":true}
{"index":{"_index":"media_search","_id":"bulk_doc_2"}}
{"media_id":22222,"post_id":201,"ai_caption":"Test bulk document 2","ai_tags":["test","bulk"],"is_safe":true}
{"delete":{"_index":"media_search","_id":"bulk_doc_1"}}
EOF

# Multi-Index Search
curl -X POST "http://localhost:9200/media_search,post_search/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "match_all": {}
    },
    "size": 10
  }'

# Search with Profile
curl -X POST "http://localhost:9200/media_search/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "match_all": {}
    },
    "size": 100,
    "profile": true
  }'

# Index Templates
curl -X PUT "http://localhost:9200/_index_template/test_template" \
  -H "Content-Type: application/json" \
  -d '{
    "index_patterns": ["test_*"],
    "template": {
      "mappings": {
        "properties": {
          "test_field": {"type": "text"},
          "created_at": {"type": "date"}
        }
      }
    }
  }'

# Delete Index Template
curl -X DELETE "http://localhost:9200/_index_template/test_template" \
  -H "Content-Type: application/json"

# Clear Test Data
curl -X POST "http://localhost:9200/media_search/_delete_by_query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "match_all": {}
    }
  }'
```

### Performance Testing

```bash
# Create Bulk Test Data
cat > bulk_test.json << EOF
{"index":{"_index":"media_search"}}
{"media_id":1,"ai_caption":"Performance test document 1","ai_tags":["test","performance"]}
{"index":{"_index":"media_search"}}
{"media_id":2,"ai_caption":"Performance test document 2","ai_tags":["test","performance"]}
{"index":{"_index":"media_search"}}
{"media_id":3,"ai_caption":"Performance test document 3","ai_tags":["test","performance"]}
{"index":{"_index":"media_search"}}
{"media_id":4,"ai_caption":"Performance test document 4","ai_tags":["test","performance"]}
{"index":{"_index":"media_search"}}
{"media_id":5,"ai_caption":"Performance test document 5","ai_tags":["test","performance"]}
EOF

# Execute Bulk Operation
curl -X POST "http://localhost:9200/_bulk" \
  -H "Content-Type: application/x-ndjson" \
  --data-binary @bulk_test.json

# Performance Search Test
curl -X POST "http://localhost:9200/media_search/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "match_all": {}
    },
    "size": 100,
    "profile": true
  }'
```

### Index Management

```bash
# Create All Indices
python scripts/setup_es_indices.py

# Check Index Status
curl -X GET "http://localhost:9200/_cat/indices?v"

# Get Index Settings
curl -X GET "http://localhost:9200/media_search/_settings"

# Get Index Stats
curl -X GET "http://localhost:9200/media_search/_stats"

# Refresh Index
curl -X POST "http://localhost:9200/media_search/_refresh"

# Force Merge Index
curl -X POST "http://localhost:9200/media_search/_forcemerge"
```

### Error Testing

```bash
# Test Invalid Index
curl -X GET "http://localhost:9200/invalid_index/_search" \
  -H "Content-Type: application/json"

# Test Invalid Document ID
curl -X GET "http://localhost:9200/media_search/_doc/invalid_id" \
  -H "Content-Type: application/json"

# Test Malformed Query
curl -X POST "http://localhost:9200/media_search/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "invalid_query": {}
    }
  }'
```

### Data Validation

```bash
# Count Documents in Index
curl -X GET "http://localhost:9200/media_search/_count" \
  -H "Content-Type: application/json"

# Get Document Count by Query
curl -X POST "http://localhost:9200/media_search/_count" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "term": {
        "is_safe": true
      }
    }
  }'

# Validate Index Mapping
curl -X GET "http://localhost:9200/media_search/_mapping" \
  -H "Content-Type: application/json"

# Check Index Health
curl -X GET "http://localhost:9200/_cat/health?v"
```

---

## 🎯 Testing Workflow

### Quick Test Sequence

```bash
# 1. Start System
cd kaleidoscope-ai
docker compose up -d

# 2. Wait for Services
sleep 30

# 3. Create Indices
python scripts/setup_es_indices.py

# 4. Test Basic Operations
curl -X GET "http://localhost:9200"
curl -X GET "http://localhost:9200/_cat/indices?v"

# 5. Index Test Document
curl -X POST "http://localhost:9200/media_search/_doc/test_1" \
  -H "Content-Type: application/json" \
  -d '{"media_id":1,"ai_caption":"Test document","ai_tags":["test"]}'

# 6. Search Test
curl -X GET "http://localhost:9200/media_search/_search?q=test" \
  -H "Content-Type: application/json"

# 7. Cleanup
curl -X DELETE "http://localhost:9200/media_search/_doc/test_1" \
  -H "Content-Type: application/json"
```

### Comprehensive Test Sequence

```bash
# Run all tests in sequence
./run_comprehensive_tests.sh
```

---

## 📊 Expected Results

### Response Times

- **Basic queries**: < 50ms
- **Complex searches**: < 100ms
- **Bulk operations**: < 500ms
- **Vector searches**: < 200ms

### Success Indicators

- **HTTP 200**: Successful operations
- **HTTP 201**: Document created
- **HTTP 404**: Document not found (expected for some tests)
- **HTTP 400**: Bad request (expected for error tests)

### Error Handling

- **Connection refused**: Service not running
- **Timeout**: Service overloaded
- **JSON parse error**: Malformed request
- **Index not found**: Index doesn't exist

---

## 🔧 Troubleshooting

### Common Issues

1. **Connection Refused**

   ```bash
   # Check if services are running
   docker compose ps
   ```

2. **Index Not Found**

   ```bash
   # Create indices
   python scripts/setup_es_indices.py
   ```

3. **Permission Denied**

   ```bash
   # Check Docker permissions
   sudo docker compose up -d
   ```

4. **JSON Parse Error**
   ```bash
   # Validate JSON syntax
   echo '{"test": "value"}' | jq .
   ```

### Debug Commands

```bash
# Check service logs
docker compose logs elasticsearch
docker compose logs redis

# Check service status
docker compose ps
docker compose top

# Check resource usage
docker stats
```

---

**🎉 Use these curl commands to thoroughly test every aspect of your Kaleidoscope AI system!**
