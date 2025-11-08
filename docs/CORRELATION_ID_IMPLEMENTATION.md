# CorrelationId Implementation - AI Services

**Date**: January 15, 2025  
**Status**: ✅ Complete  
**Backend Request**: URGENT - Add correlationId support to post-image-processing stream

---

## 📋 Summary

The backend team requested that the `correlationId` field be added to the `post-image-processing` stream message format. This field is **mandatory** and is used for distributed log tracing across all microservices.

**AI Team Response**: ✅ **IMPLEMENTED** - All AI services now extract and log `correlationId` in all log statements.

---

## ✅ Implementation Status

### 1. All AI Service Workers Updated

All 5 AI service workers now:
- ✅ Extract `correlationId` from incoming `post-image-processing` messages
- ✅ Include `correlationId` in all log statements (info, error, debug)
- ✅ Handle missing `correlationId` gracefully (empty string if not present)

**Updated Services**:
- ✅ `content_moderation/worker.py`
- ✅ `image_tagger/worker.py`
- ✅ `scene_recognition/worker.py`
- ✅ `image_captioning/worker.py`
- ✅ `face_recognition/worker.py`

### 2. Post Aggregator Updated

- ✅ Extracts `correlationId` from `post-aggregation-trigger` messages
- ✅ Includes `correlationId` in all log statements
- ✅ Handles missing `correlationId` gracefully

### 3. Documentation Updated

- ✅ `MESSAGE_FORMATS.md` updated with `correlationId` field specification
- ✅ Field marked as **mandatory** in documentation
- ✅ Example message includes `correlationId`

---

## 📝 Final Message Format

### `post-image-processing` Stream (Backend → AI Services)

```json
{
  "postId": 100,
  "mediaId": 201,
  "mediaUrl": "https://res.cloudinary.com/.../image.jpg",
  "uploaderId": 15,
  "timestamp": "2025-01-15T14:30:00Z",
  "correlationId": "abc-123-xyz-789"
}
```

**Field Descriptions**:
- `postId`: ID of the post
- `mediaId`: ID of the media
- `mediaUrl`: Public URL of the media (renamed from `imageUrl`)
- `uploaderId`: The userId of the user who uploaded the post
- `timestamp`: ISO 8601 timestamp string (optional)
- `correlationId`: **Mandatory** - The unique ID for log tracing. All AI services log this ID.

---

## 🔍 Logging Implementation

### How correlationId is Logged

All AI services now include `correlationId` in their JSON log output:

```json
{
  "timestamp": "2025-01-15T14:30:00Z",
  "level": "INFO",
  "logger": "content-moderation",
  "message": "Received moderation job",
  "source": {
    "file": "/app/worker.py",
    "line": 161,
    "function": "handle_message"
  },
  "extra": {
    "message_id": "1234567890-0",
    "media_id": 201,
    "post_id": 100,
    "media_url": "https://...",
    "correlation_id": "abc-123-xyz-789"
  }
}
```

### Log Tracing Benefits

With `correlationId` in all logs, you can now:
1. **Trace a request end-to-end**: Search logs by `correlationId` to see all AI processing steps for a single user request
2. **Debug distributed issues**: Find all related logs across all AI services for a specific post upload
3. **Monitor request flow**: Track how long each AI service takes to process a specific request
4. **Correlate errors**: When an error occurs, find all related logs using the `correlationId`

---

## 🧪 Testing

### Test Message Format

When testing, ensure your test messages include `correlationId`:

```bash
docker exec kaleidoscope-redis-1 redis-cli XADD post-image-processing "*" \
  postId 100 \
  mediaId 201 \
  mediaUrl "https://picsum.photos/400/300" \
  uploaderId 15 \
  timestamp "2025-01-15T14:30:00Z" \
  correlationId "test-correlation-123"
```

### Verify Logging

Check AI service logs to verify `correlationId` is being logged:

```bash
docker-compose logs content_moderation | grep "correlation_id"
docker-compose logs image_tagger | grep "correlation_id"
docker-compose logs scene_recognition | grep "correlation_id"
docker-compose logs image_captioning | grep "correlation_id"
docker-compose logs face_recognition | grep "correlation_id"
docker-compose logs post_aggregator | grep "correlation_id"
```

---

## 📋 Backend Team Checklist

### ✅ Backend Must Provide

1. ✅ **Include `correlationId` in all `post-image-processing` messages**
   - Backend already has `CorrelationIdFilter` that generates correlation IDs
   - Backend already includes `correlationId` in `PostImageEventDTO`
   - **Action**: Ensure `correlationId` is included when publishing to `post-image-processing` stream

2. ✅ **Include `correlationId` in `post-aggregation-trigger` messages** (if applicable)
   - Post aggregator can extract `correlationId` from trigger messages
   - **Action**: Include `correlationId` when publishing aggregation triggers

### ✅ AI Services Now Support

1. ✅ Extract `correlationId` from messages
2. ✅ Log `correlationId` in all log statements
3. ✅ Handle missing `correlationId` gracefully (won't crash if missing)

---

## 🔄 Message Flow with correlationId

```
Backend Request
  ↓
[CorrelationIdFilter generates: "abc-123-xyz-789"]
  ↓
Backend publishes to post-image-processing:
  {
    postId: 100,
    mediaId: 201,
    mediaUrl: "...",
    uploaderId: 15,
    correlationId: "abc-123-xyz-789"  ← Backend provides
  }
  ↓
AI Services (all 5):
  - Extract correlationId
  - Log all operations with correlationId
  - Process image
  - Publish results (correlationId not needed in output)
  ↓
Post Aggregator:
  - Extract correlationId from trigger (if provided)
  - Log aggregation with correlationId
  - Publish enriched insights
```

---

## 📝 Notes

1. **correlationId is NOT propagated to output streams**: AI services do NOT include `correlationId` in their output messages (`ml-insights-results`, `face-detection-results`, `post-insights-enriched`). This is intentional - the correlationId is only for log tracing, not for data flow.

2. **Backward Compatibility**: If `correlationId` is missing from a message, AI services will log an empty string for `correlation_id`. This ensures backward compatibility but logs will be less useful for tracing.

3. **Post Aggregator**: The post aggregator extracts `correlationId` from the `post-aggregation-trigger` message. If the backend includes `correlationId` in the trigger, it will be logged. If not, it will be an empty string.

---

## ✅ Status: READY FOR BACKEND INTEGRATION

All AI services are now ready to receive and log `correlationId` from backend messages. The implementation is complete and tested.

**Next Steps**:
1. Backend team: Ensure `correlationId` is included in all `post-image-processing` messages
2. Test end-to-end: Upload a post and verify `correlationId` appears in all AI service logs
3. Verify log tracing: Search logs by `correlationId` to trace a single request through all services

---

**Questions or Issues?**
- All AI services handle `correlationId` gracefully
- If `correlationId` is missing, services will still process messages but logs won't be traceable
- For best results, ensure backend always includes `correlationId` in messages

