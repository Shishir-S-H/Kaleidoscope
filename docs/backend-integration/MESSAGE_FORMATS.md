# Redis Streams Message Formats

**Complete Message Format Specifications for Backend Integration**

---

## 📋 Overview

This document defines the exact message formats for all Redis Streams used in the Kaleidoscope AI system. Use these specifications to implement your Redis Streams publishers and consumers.

---

## 🔄 Message Flow

```
Backend → post-image-processing → AI Services
AI Services → ml-insights-results → Post Aggregator
AI Services → face-detection-results → Post Aggregator
Post Aggregator → post-insights-enriched → Backend
Backend → es-sync-queue → ES Sync Service
```

---

## 📤 Outgoing Messages (Backend → AI Services)

### 1. Image Processing Job

**Stream**: `post-image-processing`  
**Purpose**: Trigger AI processing for uploaded images

```json
{
  "jobId": "string",
  "postId": "uuid",
  "mediaId": "uuid", 
  "userId": "uuid",
  "imageUrl": "string",
  "timestamp": "long"
}
```

**Field Descriptions**:
- `jobId`: Unique identifier for this processing job
- `postId`: ID of the post containing this image
- `mediaId`: ID of the specific media/image
- `userId`: ID of the user who uploaded the image
- `imageUrl`: URL to the image file (must be accessible by AI services)
- `timestamp`: Unix timestamp in milliseconds

**Example**:
```json
{
  "jobId": "job_2025_01_21_001",
  "postId": "550e8400-e29b-41d4-a716-446655440000",
  "mediaId": "550e8400-e29b-41d4-a716-446655440001",
  "userId": "550e8400-e29b-41d4-a716-446655440002",
  "imageUrl": "https://your-cdn.com/images/beach-sunset.jpg",
  "timestamp": 1737504000000
}
```

---

## 📥 Incoming Messages (AI Services → Backend)

### 1. ML Insights Results

**Stream**: `ml-insights-results`  
**Purpose**: AI analysis results from content moderation, tagging, captioning, and scene recognition

```json
{
  "jobId": "string",
  "postId": "uuid",
  "mediaId": "uuid",
  "userId": "uuid",
  "serviceType": "string",
  "results": {
    "contentModeration": {
      "isSafe": "boolean",
      "confidence": "float"
    },
    "imageTagging": {
      "tags": ["string"],
      "confidences": ["float"]
    },
    "sceneRecognition": {
      "scenes": ["string"],
      "confidences": ["float"]
    },
    "imageCaptioning": {
      "caption": "string",
      "confidence": "float"
    }
  },
  "timestamp": "long"
}
```

**Field Descriptions**:
- `jobId`: Original job ID from image processing
- `postId`: ID of the post containing this image
- `mediaId`: ID of the specific media/image
- `userId`: ID of the user who uploaded the image
- `serviceType`: Type of AI service ("content_moderation", "image_tagger", "scene_recognition", "image_captioning")
- `results`: AI analysis results (only relevant fields populated based on serviceType)
- `timestamp`: Unix timestamp in milliseconds

**Example**:
```json
{
  "jobId": "job_2025_01_21_001",
  "postId": "550e8400-e29b-41d4-a716-446655440000",
  "mediaId": "550e8400-e29b-41d4-a716-446655440001",
  "userId": "550e8400-e29b-41d4-a716-446655440002",
  "serviceType": "image_tagger",
  "results": {
    "imageTagging": {
      "tags": ["beach", "sunset", "ocean", "sky"],
      "confidences": [0.95, 0.89, 0.92, 0.87]
    }
  },
  "timestamp": 1737504030000
}
```

### 2. Face Detection Results

**Stream**: `face-detection-results`  
**Purpose**: Face detection and recognition results

```json
{
  "jobId": "string",
  "postId": "uuid",
  "mediaId": "uuid",
  "userId": "uuid",
  "faces": [
    {
      "faceId": "string",
      "boundingBox": [float, float, float, float],
      "embedding": [float, ...],
      "confidence": "float"
    }
  ],
  "timestamp": "long"
}
```

**Field Descriptions**:
- `jobId`: Original job ID from image processing
- `postId`: ID of the post containing this image
- `mediaId`: ID of the specific media/image
- `userId`: ID of the user who uploaded the image
- `faces`: Array of detected faces
- `faceId`: Unique identifier for this face detection
- `boundingBox`: [x, y, width, height] in normalized coordinates (0-1)
- `embedding`: 1024-dimensional face embedding vector
- `confidence`: Detection confidence (0-1)
- `timestamp`: Unix timestamp in milliseconds

**Example**:
```json
{
  "jobId": "job_2025_01_21_001",
  "postId": "550e8400-e29b-41d4-a716-446655440000",
  "mediaId": "550e8400-e29b-41d4-a716-446655440001",
  "userId": "550e8400-e29b-41d4-a716-446655440002",
  "faces": [
    {
      "faceId": "face_001",
      "boundingBox": [0.1, 0.2, 0.3, 0.4],
      "embedding": [0.1, 0.2, 0.3, ...],
      "confidence": 0.95
    }
  ],
  "timestamp": 1737504035000
}
```

### 3. Post Insights Enriched

**Stream**: `post-insights-enriched`  
**Purpose**: Aggregated insights for entire post (after post aggregation)

```json
{
  "postId": "uuid",
  "userId": "uuid",
  "aggregatedTags": ["string"],
  "eventType": "string",
  "totalMediaCount": "integer",
  "totalFaceCount": "integer",
  "isSafe": "boolean",
  "mediaInsights": [
    {
      "mediaId": "uuid",
      "caption": "string",
      "tags": ["string"],
      "scenes": ["string"],
      "isSafe": "boolean",
      "confidenceScore": "float",
      "faceCount": "integer"
    }
  ],
  "timestamp": "long"
}
```

**Field Descriptions**:
- `postId`: ID of the post
- `userId`: ID of the user who created the post
- `aggregatedTags`: Combined tags from all media in the post
- `eventType`: Detected event type ("team_outing", "birthday_party", "conference", etc.)
- `totalMediaCount`: Total number of media items in the post
- `totalFaceCount`: Total number of faces across all media
- `isSafe`: Overall safety status (true if all media are safe)
- `mediaInsights`: Detailed insights for each media item
- `timestamp`: Unix timestamp in milliseconds

**Example**:
```json
{
  "postId": "550e8400-e29b-41d4-a716-446655440000",
  "userId": "550e8400-e29b-41d4-a716-446655440002",
  "aggregatedTags": ["beach", "sunset", "ocean", "team", "outdoor"],
  "eventType": "team_outing",
  "totalMediaCount": 3,
  "totalFaceCount": 8,
  "isSafe": true,
  "mediaInsights": [
    {
      "mediaId": "550e8400-e29b-41d4-a716-446655440001",
      "caption": "Beautiful sunset at the beach",
      "tags": ["beach", "sunset", "ocean"],
      "scenes": ["beach", "outdoor"],
      "isSafe": true,
      "confidenceScore": 0.95,
      "faceCount": 3
    }
  ],
  "timestamp": 1737504040000
}
```

---

## 🔄 ES Sync Messages (Backend → ES Sync)

### ES Sync Queue Message

**Stream**: `es-sync-queue`  
**Purpose**: Trigger Elasticsearch synchronization for database changes

```json
{
  "tableName": "string",
  "operation": "string",
  "recordId": "string",
  "data": "object",
  "timestamp": "long"
}
```

**Field Descriptions**:
- `tableName`: Name of the read model table that changed
- `operation`: Type of operation ("INSERT", "UPDATE", "DELETE")
- `recordId`: ID of the record that changed
- `data`: Complete record data (for INSERT/UPDATE) or null (for DELETE)
- `timestamp`: Unix timestamp in milliseconds

**Example**:
```json
{
  "tableName": "media_search_read_model",
  "operation": "INSERT",
  "recordId": "550e8400-e29b-41d4-a716-446655440001",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "postId": "550e8400-e29b-41d4-a716-446655440000",
    "mediaId": "550e8400-e29b-41d4-a716-446655440001",
    "userId": "550e8400-e29b-41d4-a716-446655440002",
    "caption": "Beautiful sunset at the beach",
    "tags": ["beach", "sunset", "ocean"],
    "scenes": ["beach", "outdoor"],
    "isSafe": true,
    "confidenceScore": 0.95,
    "faceCount": 3,
    "createdAt": "2025-01-21T10:00:00Z",
    "updatedAt": "2025-01-21T10:00:00Z"
  },
  "timestamp": 1737504045000
}
```

---

## 🔧 Implementation Examples

### Java Spring Boot Publisher

```java
@Component
public class RedisStreamPublisher {
    
    @Autowired
    private RedisTemplate<String, Object> redisTemplate;
    
    public void publishImageProcessingJob(ImageProcessingJob job) {
        Map<String, Object> message = Map.of(
            "jobId", job.getJobId(),
            "postId", job.getPostId().toString(),
            "mediaId", job.getMediaId().toString(),
            "userId", job.getUserId().toString(),
            "imageUrl", job.getImageUrl(),
            "timestamp", System.currentTimeMillis()
        );
        
        redisTemplate.opsForStream().add("post-image-processing", message);
    }
}
```

### Java Spring Boot Consumer

```java
@Component
public class MLInsightsConsumer {
    
    @StreamListener(target = "ml-insights-results")
    public void handleMLInsights(Map<String, Object> message) {
        String jobId = (String) message.get("jobId");
        String postId = (String) message.get("postId");
        String mediaId = (String) message.get("mediaId");
        String userId = (String) message.get("userId");
        String serviceType = (String) message.get("serviceType");
        
        @SuppressWarnings("unchecked")
        Map<String, Object> results = (Map<String, Object>) message.get("results");
        
        // Process the results
        processMLInsights(jobId, postId, mediaId, userId, serviceType, results);
    }
}
```

### Python Consumer (Reference)

```python
import redis
import json

def consume_messages():
    r = redis.Redis(host='localhost', port=6379, db=0)
    
    while True:
        messages = r.xread({
            'ml-insights-results': '$'
        }, count=1, block=1000)
        
        for stream, msgs in messages:
            for msg_id, fields in msgs:
                # Decode message
                message = {k.decode(): v.decode() for k, v in fields.items()}
                
                # Process message
                process_message(message)
```

---

## 🧪 Testing Message Formats

### Test Image Processing Job

```bash
# Publish test message
redis-cli XADD post-image-processing "*" \
  jobId "test-job-001" \
  postId "550e8400-e29b-41d4-a716-446655440000" \
  mediaId "550e8400-e29b-41d4-a716-446655440001" \
  userId "550e8400-e29b-41d4-a716-446655440002" \
  imageUrl "https://example.com/test-image.jpg" \
  timestamp "1737504000000"
```

### Test ML Insights Result

```bash
# Publish test result
redis-cli XADD ml-insights-results "*" \
  jobId "test-job-001" \
  postId "550e8400-e29b-41d4-a716-446655440000" \
  mediaId "550e8400-e29b-41d4-a716-446655440001" \
  userId "550e8400-e29b-41d4-a716-446655440002" \
  serviceType "image_tagger" \
  results '{"imageTagging":{"tags":["beach","sunset"],"confidences":[0.95,0.89]}}' \
  timestamp "1737504030000"
```

### Verify Messages

```bash
# Check stream length
redis-cli XLEN post-image-processing

# Read messages
redis-cli XREAD STREAMS post-image-processing 0

# Read latest messages
redis-cli XREAD STREAMS post-image-processing $
```

---

## 📊 Message Validation

### Required Fields

Each message type has required fields that must be present:

**Image Processing Job**:
- ✅ jobId (string)
- ✅ postId (uuid)
- ✅ mediaId (uuid)
- ✅ userId (uuid)
- ✅ imageUrl (string)
- ✅ timestamp (long)

**ML Insights Results**:
- ✅ jobId (string)
- ✅ postId (uuid)
- ✅ mediaId (uuid)
- ✅ userId (uuid)
- ✅ serviceType (string)
- ✅ results (object)
- ✅ timestamp (long)

**Face Detection Results**:
- ✅ jobId (string)
- ✅ postId (uuid)
- ✅ mediaId (uuid)
- ✅ userId (uuid)
- ✅ faces (array)
- ✅ timestamp (long)

**Post Insights Enriched**:
- ✅ postId (uuid)
- ✅ userId (uuid)
- ✅ aggregatedTags (array)
- ✅ eventType (string)
- ✅ totalMediaCount (integer)
- ✅ totalFaceCount (integer)
- ✅ isSafe (boolean)
- ✅ mediaInsights (array)
- ✅ timestamp (long)

**ES Sync Queue**:
- ✅ tableName (string)
- ✅ operation (string)
- ✅ recordId (string)
- ✅ data (object)
- ✅ timestamp (long)

---

## 🔍 Troubleshooting

### Common Issues

1. **Message Not Published**
   - Check Redis connection
   - Verify stream name
   - Check message format

2. **Message Not Consumed**
   - Check consumer configuration
   - Verify stream exists
   - Check consumer group

3. **Invalid Message Format**
   - Validate JSON structure
   - Check required fields
   - Verify data types

### Debug Commands

```bash
# Check Redis connection
redis-cli ping

# List all streams
redis-cli XINFO STREAMS

# Check stream info
redis-cli XINFO STREAM post-image-processing

# Check consumer groups
redis-cli XINFO GROUPS post-image-processing
```

---

## 📈 Performance Considerations

### Message Size
- Keep messages under 1MB
- Use efficient JSON serialization
- Consider compression for large payloads

### Throughput
- Use connection pooling
- Implement batch processing
- Monitor memory usage

### Reliability
- Implement retry logic
- Use consumer groups
- Monitor failed messages

---

**Use these message formats to ensure seamless integration between your backend and the Kaleidoscope AI services!** 🚀
