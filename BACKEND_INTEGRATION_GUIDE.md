# Kaleidoscope AI - Backend Integration Guide

## 🚀 **Deployment Status: LIVE**

**Server:** `165.232.179.167`  
**Status:** ✅ All services running  
**Last Updated:** October 28, 2025  

## 📋 **Service Overview**

| Service | Type | Status | Purpose |
|---------|------|--------|---------|
| Redis | Message Broker | ✅ Running | Redis Streams for message queuing |
| Elasticsearch | Search Engine | ✅ Running | Vector search and indexing |
| Content Moderation | AI Worker | ✅ Running | NSFW detection and content filtering |
| Image Tagger | AI Worker | ✅ Running | Object detection and tagging |
| Scene Recognition | AI Worker | ✅ Running | Scene classification |
| Image Captioning | AI Worker | ✅ Running | Image description generation |
| Face Recognition | AI Worker | ✅ Running | Face detection and embedding |
| Post Aggregator | AI Worker | ✅ Running | Post-level insight aggregation |
| ES Sync | Sync Worker | ✅ Running | PostgreSQL to Elasticsearch sync |

## 🔌 **Connection Details**

### **Redis Streams**
```yaml
Host: 165.232.179.167
Port: 6379
Protocol: redis
Input Stream: post-image-processing
Output Stream: ml-insights-results
Consumer Group: [service-name]-group
```

### **Elasticsearch**
```yaml
Host: 165.232.179.167
Port: 9200
Protocol: http
Indices:
  - media_search
  - post_search
  - user_search
  - face_search
  - recommendations_knn
  - feed_personalized
  - known_faces_index
```

## 📨 **Message Formats**

### **Input Message (to AI Services)**
```json
{
  "mediaId": 12345,
  "postId": 67890,
  "mediaUrl": "https://example.com/image.jpg",
  "uploaderId": 11111,
  "timestamp": "2025-10-22T07:35:25Z"
}
```

### **Output Message (from AI Services)**
```json
{
  "mediaId": 12345,
  "postId": 67890,
  "service": "moderation" | "tagging" | "scene_recognition" | "captioning",
  "isSafe": true,
  "moderationConfidence": 0.95,
  "tags": ["tag1", "tag2"],
  "scenes": ["indoor"],
  "caption": "...",
  "timestamp": "2025-10-22T07:35:30Z"
}
```

## 🔄 **Integration Flow**

### **1. Send Image for Processing**
```python
import redis

# Connect to Redis
r = redis.Redis(host='165.232.179.167', port=6379, decode_responses=True)

# Send image for processing
message = {
    "mediaId": 12345,
    "postId": 67890,
    "mediaUrl": "https://example.com/image.jpg",
    "uploaderId": 11111,
    "timestamp": "2025-10-22T07:35:25Z"
}

# Add to Redis Stream
r.xadd("post-image-processing", message)
```

### **2. Consume AI Results**
```python
# Create consumer group
r.xgroup_create("post-image-processing", "backend-group", id="0", mkstream=True)

# Read messages
messages = r.xreadgroup("backend-group", "consumer-1", {"post-image-processing": ">"}, count=10)

for stream, msgs in messages:
    for msg_id, fields in msgs:
        # Process AI results
        print(f"AI Result: {fields}")
```

### **3. Trigger Post Aggregation and Read Enriched Results**
```bash
# Trigger aggregation for a post
redis-cli -h 165.232.179.167 -p 6379 XADD post-aggregation-trigger "*" postId 67890 action aggregate

# Read enriched results
redis-cli -h 165.232.179.167 -p 6379 XREAD STREAMS post-insights-enriched 0
```

## 🗄️ **Database Schema**

### **Read Model Tables (for Elasticsearch)**
```sql
-- Media Search Table
CREATE TABLE media_search (
    media_id BIGINT PRIMARY KEY,
    post_id BIGINT,
    user_id BIGINT,
    image_url TEXT,
    tags TEXT[],
    caption TEXT,
    scene TEXT,
    is_safe BOOLEAN,
    face_count INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Post Search Table
CREATE TABLE post_search (
    post_id BIGINT PRIMARY KEY,
    user_id BIGINT,
    content TEXT,
    tags TEXT[],
    event_type TEXT,
    face_count INTEGER,
    is_safe BOOLEAN,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- User Search Table
CREATE TABLE user_search (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    display_name TEXT,
    bio TEXT,
    interests TEXT[],
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Face Search Table
CREATE TABLE face_search (
    face_id BIGINT PRIMARY KEY,
    media_id BIGINT,
    post_id BIGINT,
    user_id BIGINT,
    embedding VECTOR(1024),
    confidence FLOAT,
    bounding_box JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Recommendations KNN Table
CREATE TABLE recommendations_knn (
    user_id BIGINT PRIMARY KEY,
    interests TEXT[],
    behavior_vector VECTOR(512),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Feed Personalized Table
CREATE TABLE feed_personalized (
    user_id BIGINT PRIMARY KEY,
    preferences JSONB,
    feed_vector VECTOR(512),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Known Faces Index Table
CREATE TABLE known_faces_index (
    face_id BIGINT PRIMARY KEY,
    person_name TEXT,
    embedding VECTOR(1024),
    confidence FLOAT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## 🔧 **Backend Implementation**

### **Spring Boot Configuration**
```yaml
# application.yml
spring:
  redis:
    host: 165.232.179.167
    port: 6379
    timeout: 2000ms
    lettuce:
      pool:
        max-active: 8
        max-idle: 8
        min-idle: 0

elasticsearch:
  host: 165.232.179.167
  port: 9200
  protocol: http
```

### **Redis Stream Consumer (Java example)**
```java
@Component
public class AIResultsConsumer {
    
    @Autowired
    private RedisTemplate<String, String> redisTemplate;
    
    @EventListener
    public void consumeAIResults() {
        // Read from Redis Stream
        List<MapRecord<String, String, String>> messages = redisTemplate
            .opsForStream()
            .read(Consumer.from("backend-group", "consumer-1"),
                  StreamReadOptions.empty().count(10),
                  StreamOffset.create("ml-insights-results", ReadOffset.lastConsumed()));
        
        for (MapRecord<String, String, String> message : messages) {
            // Process AI results
            processAIResult(message.getValue());
        }
    }
}
```

## 🧪 **Testing**

### **Test Redis Connection**
```bash
redis-cli -h 165.232.179.167 -p 6379 ping
# Should return: PONG
```

### **Test Elasticsearch**
```bash
curl http://165.232.179.167:9200
# Should return: Elasticsearch version info
```

### **Test AI Services**
```bash
# Send test message (camelCase)
redis-cli -h 165.232.179.167 -p 6379 XADD post-image-processing "*" mediaId 12345 postId 67890 mediaUrl "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png" uploaderId 11111

# Check results
redis-cli -h 165.232.179.167 -p 6379 XREAD STREAMS ml-insights-results 0
```

## 📊 **Monitoring**

### **Service Health Check**
```bash
# Check all services
docker-compose -f docker-compose.yml ps

# Check logs
docker-compose -f docker-compose.yml logs -f

# Check Redis
redis-cli -h 165.232.179.167 -p 6379 info

# Check Elasticsearch
curl http://165.232.179.167:9200/_cluster/health
```

## 🚨 **Troubleshooting**

### **Common Issues**

1. **BLOCK $ returns (nil)**
   - You started blocking after the message was published. Use XRANGE/XREVRANGE to read existing entries or start blocking before the trigger.
2. **HTTP 521/403 on image download**
   - Use reliable URLs (GitHub asset, Wikimedia). Avoid placekitten/picsum during outages.
3. **ml-insights vs aggregator**
   - Aggregator now fetches insights from `ml-insights-results` and `face-detection-results` by postId if none are inline.
4. **Elasticsearch OOM (exit 137)**
   - Add 2–4 GB swap or cap heap: `ES_JAVA_OPTS=-Xms1g -Xmx1g`.
5. **NOGROUP on es-sync**
   - Create group: `XGROUP CREATE es-sync-queue es-sync-group $ MKSTREAM`.

### **Logs Location**
```bash
# Service logs
docker-compose -f docker-compose.yml logs [service-name]

# System logs
journalctl -u docker
```

## 📞 **Support**

**For issues with:**
- **AI Services:** Check Redis Streams and HuggingFace API
- **Elasticsearch:** Check index mappings and queries
- **Redis:** Check connection and stream configuration
- **Deployment:** Check Docker containers and logs

**Contact:** [Your contact information]

---

**Last Updated:** October 28, 2025  
**Version:** 1.0  
**Status:** Production Ready ✅
