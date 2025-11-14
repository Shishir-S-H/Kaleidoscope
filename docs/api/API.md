# API Reference

**Message formats and API specifications for Kaleidoscope AI**

---

## Redis Streams Message Formats

### Overview

The system uses Redis Streams for event-driven communication. All messages are JSON-encoded strings in Redis Streams.

---

## Outgoing Messages (Backend → AI Services)

### Image Processing Job

**Stream**: `post-image-processing`  
**Purpose**: Trigger AI processing for uploaded images

**Message Format**:

```json
{
  "postId": "string|number",
  "mediaId": "string|number",
  "mediaUrl": "string",
  "uploaderId": "string|number",
  "correlationId": "string (mandatory)"
}
```

**Field Descriptions**:

- `postId`: ID of the post containing this image
- `mediaId`: ID of the specific media/image
- `mediaUrl`: Publicly reachable URL to the image
- `uploaderId`: ID of the user who uploaded the image
- `correlationId`: **Mandatory** - Unique ID for distributed log tracing

**Example**:

```json
{
  "postId": 90001,
  "mediaId": 70001,
  "mediaUrl": "https://example.com/image.jpg",
  "uploaderId": 101,
  "correlationId": "abc-123-xyz-789"
}
```

---

## Incoming Messages (AI Services → Backend)

### ML Insights Results

**Stream**: `ml-insights-results`  
**Purpose**: AI analysis results from content moderation, tagging, captioning, and scene recognition

**Message Format**:

```json
{
  "postId": "string|number",
  "mediaId": "string|number",
  "service": "moderation" | "tagging" | "scene_recognition" | "image_captioning",
  "isSafe": "true" | "false",              // moderation only
  "moderationConfidence": "string",         // moderation only
  "tags": "JSON string array",             // tagging only
  "scenes": "JSON string array",           // scene_recognition only
  "caption": "string",                     // image_captioning only
  "timestamp": "ISO 8601 string"
}
```

**Example (Tagging)**:

```json
{
  "postId": "90001",
  "mediaId": "70001",
  "service": "tagging",
  "tags": "[\"beach\", \"sunset\", \"ocean\"]",
  "timestamp": "2025-01-15T14:30:00Z"
}
```

**Example (Moderation)**:

```json
{
  "postId": "90001",
  "mediaId": "70001",
  "service": "moderation",
  "isSafe": "true",
  "moderationConfidence": "0.95",
  "timestamp": "2025-01-15T14:30:00Z"
}
```

---

### Face Detection Results

**Stream**: `face-detection-results`  
**Purpose**: Face detection results

**Message Format**:

```json
{
  "postId": "string|number",
  "mediaId": "string|number",
  "facesDetected": "string",
  "faces": "JSON string",
  "timestamp": "ISO 8601 string"
}
```

**Faces Array Format** (inside JSON string):

```json
[
  {
    "faceId": "uuid",
    "bbox": [x, y, width, height],
    "embedding": [0.1, 0.2, ...],  // 1024-dim array
    "confidence": 0.95
  }
]
```

**Example**:

```json
{
  "postId": "90001",
  "mediaId": "70001",
  "facesDetected": "2",
  "faces": "[{\"faceId\":\"uuid-1\",\"bbox\":[100,150,80,100],\"embedding\":[0.1,0.2,...],\"confidence\":0.95}]",
  "timestamp": "2025-01-15T14:30:00Z"
}
```

---

### Post Insights Enriched

**Stream**: `post-insights-enriched`  
**Purpose**: Aggregated insights for entire post (after post aggregation)

**Message Format**:

```json
{
  "postId": "string|number",
  "mediaCount": "string",
  "allAiTags": "JSON string array",
  "allAiScenes": "JSON string array",
  "aggregatedTags": "JSON string array",
  "aggregatedScenes": "JSON string array",
  "totalFaces": "string",
  "isSafe": "true" | "false",
  "moderationConfidence": "string",
  "inferredEventType": "string",
  "combinedCaption": "string",
  "hasMultipleImages": "true" | "false",
  "timestamp": "ISO 8601 string",
  "correlationId": "string"
}
```

**Example**:

```json
{
  "postId": "90001",
  "mediaCount": "3",
  "allAiTags": "[\"beach\", \"sunset\", \"ocean\", \"people\"]",
  "allAiScenes": "[\"beach\", \"outdoor\"]",
  "aggregatedTags": "[\"beach\", \"sunset\", \"ocean\"]",
  "aggregatedScenes": "[\"beach\", \"outdoor\"]",
  "totalFaces": "5",
  "isSafe": "true",
  "moderationConfidence": "0.95",
  "inferredEventType": "beach_party",
  "combinedCaption": "A group of people enjoying a beautiful sunset at the beach",
  "hasMultipleImages": "true",
  "timestamp": "2025-01-15T14:35:00Z",
  "correlationId": "abc-123-xyz-789"
}
```

---

## ES Sync Messages (Backend → ES Sync)

### ES Sync Queue Message

**Stream**: `es-sync-queue`  
**Purpose**: Trigger Elasticsearch synchronization for database changes

**Message Format**:

```json
{
  "operation": "index" | "delete",
  "indexType": "media_search" | "post_search" | "user_search" | "face_search" | "recommendations_knn" | "feed_personalized" | "known_faces_index",
  "documentId": "string|number"
}
```

**Field Descriptions**:

- `operation`: `index` (insert/update) or `delete`
- `indexType`: Target Elasticsearch index type
- `documentId`: Document ID (primary key from read model table)

**Example**:

```json
{
  "operation": "index",
  "indexType": "media_search",
  "documentId": "70001"
}
```

**Note**: ES Sync reads the actual data from PostgreSQL read model tables. The message only contains the operation type and document ID.

---

## Index Types

### Available Index Types

1. **media_search** - Individual media/image search
2. **post_search** - Post-level aggregated search
3. **user_search** - User profiles and discovery
4. **face_search** - Face detection and search
5. **recommendations_knn** - Content-based recommendations
6. **feed_personalized** - Personalized user feeds
7. **known_faces_index** - Face enrollment and identification

---

## Implementation Examples

### Java Spring Boot Publisher

```java
@Component
public class RedisStreamPublisher {

    @Autowired
    private RedisTemplate<String, Object> redisTemplate;

    public void publishImageProcessingJob(Long postId, Long mediaId,
                                         String mediaUrl, Long uploaderId,
                                         String correlationId) {
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

### Java Spring Boot Consumer

```java
@Component
public class MLInsightsConsumer {

    @StreamListener(target = "ml-insights-results")
    public void handleMLInsights(Map<String, Object> message) {
        Long postId = Long.parseLong((String) message.get("postId"));
        Long mediaId = Long.parseLong((String) message.get("mediaId"));
        String service = (String) message.get("service");

        // Process based on service type
        switch (service) {
            case "moderation":
                handleModeration(message);
                break;
            case "tagging":
                handleTagging(message);
                break;
            // ... other services
        }
    }
}
```

---

## Testing Message Formats

### Publish Test Image Job

```bash
docker exec redis redis-cli -a ${REDIS_PASSWORD} XADD post-image-processing "*" \
  postId 90001 \
  mediaId 70001 \
  mediaUrl "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png" \
  uploaderId 101 \
  correlationId "test-001"
```

### Check Results

```bash
# Check ML insights
docker exec redis redis-cli -a ${REDIS_PASSWORD} XREAD STREAMS ml-insights-results 0

# Check face detection
docker exec redis redis-cli -a ${REDIS_PASSWORD} XREAD STREAMS face-detection-results 0
```

---

## Message Validation

### Required Fields

**Image Processing Job**:

- ✅ postId
- ✅ mediaId
- ✅ mediaUrl
- ✅ uploaderId
- ✅ correlationId

**ML Insights Results**:

- ✅ postId
- ✅ mediaId
- ✅ service
- ✅ Service-specific fields (isSafe, tags, scenes, caption)

**Face Detection Results**:

- ✅ postId
- ✅ mediaId
- ✅ facesDetected
- ✅ faces

**Post Insights Enriched**:

- ✅ postId
- ✅ mediaCount
- ✅ allAiTags
- ✅ allAiScenes
- ✅ aggregatedTags
- ✅ aggregatedScenes
- ✅ totalFaces
- ✅ isSafe
- ✅ inferredEventType

**ES Sync Queue**:

- ✅ operation
- ✅ indexType
- ✅ documentId

---

## Notes

- All string values in Redis Streams are JSON-encoded
- Arrays are JSON-encoded as strings (e.g., `"[\"tag1\", \"tag2\"]"`)
- Timestamps are ISO 8601 format strings
- Correlation IDs should be unique per request for distributed tracing

---

**For backend integration details, see [BACKEND_INTEGRATION.md](BACKEND_INTEGRATION.md)**
