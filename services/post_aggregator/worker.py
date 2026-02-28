#!/usr/bin/env python3
"""
Post Aggregator Service
Aggregates AI insights from multiple images in a post to derive post-level insights.
"""

import json
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Dict, List, Any, Set, Optional
from collections import Counter
import time
from datetime import datetime
from dotenv import load_dotenv

# Add parent directories to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables
load_dotenv()

# Import logger and Redis Streams
from shared.utils.logger import get_logger
from shared.redis_streams import RedisStreamPublisher, RedisStreamConsumer
from shared.redis_streams.utils import decode_message
from shared.utils.health_server import start_health_server, mark_ready
from shared.utils.secrets import get_secret
import redis
import requests

# Initialize logger
LOGGER = get_logger("post-aggregator")

# Redis Streams configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STREAM_INPUT = "post-aggregation-trigger"
STREAM_OUTPUT = "post-insights-enriched"
CONSUMER_GROUP = "post-aggregator-group"
CONSUMER_NAME = "post-aggregator-worker-1"
INSIGHTS_STREAM = "ml-insights-results"
FACES_STREAM = "face-detection-results"

AGGREGATION_WAIT_SECONDS = float(os.getenv("AGGREGATION_WAIT_SECONDS", "6"))
AGGREGATION_POLL_INTERVAL = float(os.getenv("AGGREGATION_POLL_INTERVAL", "0.5"))
REQUIRED_SERVICES: Set[str] = {"moderation", "tagging", "scene_recognition", "image_captioning"}
OPTIONAL_SERVICES: Set[str] = {"face"}

# LLM caption summarization (optional)
USE_LLM_CAPTIONS = os.getenv("USE_LLM_CAPTIONS", "false").lower() in ("true", "1", "yes")
LLM_API_URL = get_secret("LLM_API_URL", "")
LLM_API_TOKEN = get_secret("LLM_API_TOKEN", "")

shutdown_event = threading.Event()


def _shutdown_handler(signum, frame):
    LOGGER.info("Shutdown signal received (signal %s)", signum)
    shutdown_event.set()


def _try_parse_json(value: Any) -> Any:
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return None
        try:
            return json.loads(trimmed)
        except ValueError:
            return None
    return value


def _normalize_media_ids(raw_value: Any) -> Set[str]:
    parsed = _try_parse_json(raw_value)
    ids: Set[str] = set()
    if isinstance(parsed, (list, tuple, set)):
        ids = {str(item).strip() for item in parsed if str(item).strip()}
    elif isinstance(raw_value, str):
        cleaned = raw_value.strip().strip("[]")
        if cleaned:
            ids = {item.strip() for item in cleaned.split(",") if item.strip()}
    elif raw_value not in (None, ""):
        ids = {str(raw_value)}
    return ids


# Consumer groups for reading insights/faces streams (instead of XREVRANGE)
INSIGHTS_CONSUMER_GROUP = "post-aggregator-insights-reader"
INSIGHTS_CONSUMER_NAME = "post-aggregator-insights-reader-1"
FACES_CONSUMER_GROUP = "post-aggregator-faces-reader"
FACES_CONSUMER_NAME = "post-aggregator-faces-reader-1"

# In-memory buffer: postId -> list of entries from insights/faces streams
_post_buffer: Dict[str, List[Dict[str, Any]]] = {}
_buffer_lock = threading.Lock()


def _ensure_reader_groups(redis_client: redis.StrictRedis):
    """Create consumer groups for the insights and faces streams if they don't exist."""
    for stream, group in [
        (INSIGHTS_STREAM, INSIGHTS_CONSUMER_GROUP),
        (FACES_STREAM, FACES_CONSUMER_GROUP),
    ]:
        try:
            redis_client.xgroup_create(stream, group, id="0", mkstream=True)
            LOGGER.info("Created reader group '%s' on stream '%s'", group, stream)
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise


def _drain_stream(
    redis_client: redis.StrictRedis,
    stream: str,
    group: str,
    consumer_name: str,
    batch: int = 100,
):
    """Read all pending + new messages from a stream via its consumer group and buffer them by postId."""
    try:
        messages = redis_client.xreadgroup(
            groupname=group,
            consumername=consumer_name,
            streams={stream: ">"},
            count=batch,
            block=0,
        )
    except Exception as err:
        LOGGER.error("Failed to drain stream", extra={"stream": stream, "error": str(err)})
        return

    if not messages:
        return

    for _stream_name, stream_messages in messages:
        for msg_id, values in stream_messages:
            post_val = values.get("postId") or values.get("post_id")
            if not post_val:
                redis_client.xack(stream, group, msg_id)
                continue

            entry = dict(values)
            entry["_id"] = msg_id
            entry["_stream"] = stream

            with _buffer_lock:
                _post_buffer.setdefault(post_val, []).append(entry)

            redis_client.xack(stream, group, msg_id)


def _fetch_buffered_entries(post_id: int) -> List[Dict[str, Any]]:
    """Return and clear all buffered entries for a given postId."""
    target = str(post_id)
    with _buffer_lock:
        entries = _post_buffer.pop(target, [])
    return entries


def _fetch_stream_entries_via_groups(
    redis_client: redis.StrictRedis,
    post_id: int,
) -> List[Dict[str, Any]]:
    """Drain both streams into the buffer and return entries for the given post."""
    _drain_stream(redis_client, INSIGHTS_STREAM, INSIGHTS_CONSUMER_GROUP, INSIGHTS_CONSUMER_NAME)
    _drain_stream(redis_client, FACES_STREAM, FACES_CONSUMER_GROUP, FACES_CONSUMER_NAME)
    return _fetch_buffered_entries(post_id)


def _merge_media_entry(media_map: Dict[str, Dict[str, Any]], entry: Any) -> None:
    if isinstance(entry, str):
        parsed = _try_parse_json(entry)
        if not isinstance(parsed, dict):
            return
        entry = parsed
    if not isinstance(entry, dict):
        return

    media_id = entry.get("mediaId") or entry.get("media_id")
    if not media_id:
        return
    media_id = str(media_id)

    media_entry = media_map.setdefault(media_id, {"mediaId": media_id, "_services": set()})

    service = entry.get("service")
    if not service and ("facesDetected" in entry or "faces" in entry):
        service = "face"

    if service:
        media_entry["_services"].add(service)

    for key in (
        "tags",
        "scenes",
        "caption",
        "isSafe",
        "moderationConfidence",
        "facesDetected",
        "faces",
        "mediaUrl",
        "timestamp",
    ):
        if key in entry and entry[key] not in (None, ""):
            media_entry[key] = entry[key]


def _finalize_media_map(media_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    finalized: List[Dict[str, Any]] = []
    for data in media_map.values():
        record = dict(data)
        record.pop("_services", None)
        finalized.append(record)
    return finalized


def _has_required_services(
    media_map: Dict[str, Dict[str, Any]],
    expected_media_ids: Set[str],
    expected_media_count: Optional[int],
) -> bool:
    if expected_media_ids:
        targets = {str(media_id) for media_id in expected_media_ids}
    elif expected_media_count:
        if len(media_map) < expected_media_count:
            return False
        targets = set(media_map.keys())
    else:
        return False

    for media_id in targets:
        record = media_map.get(media_id)
        if not record:
            return False
        services: Set[str] = record.get("_services", set())
        if not REQUIRED_SERVICES.issubset(services):
            return False
    return True


def collect_media_insights(
    post_id: int,
    correlation_id: str,
    initial_insights: List[Dict[str, Any]],
    expected_media_ids: Set[str],
    expected_media_count: Optional[int],
) -> List[Dict[str, Any]]:
    media_map: Dict[str, Dict[str, Any]] = {}
    for insight in initial_insights or []:
        _merge_media_entry(media_map, insight)

    try:
        redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True)
        _ensure_reader_groups(redis_client)
    except Exception as err:
        LOGGER.error("Failed to initialize Redis client for aggregation fetch", extra={
            "post_id": post_id,
            "error": str(err),
            "correlation_id": correlation_id
        })
        return _finalize_media_map(media_map)

    seen_ids: Set[str] = set()
    deadline = time.time() + AGGREGATION_WAIT_SECONDS

    while True:
        if _has_required_services(media_map, expected_media_ids, expected_media_count):
            break

        if time.time() >= deadline:
            break

        entries = _fetch_stream_entries_via_groups(redis_client, post_id)
        new_entries: List[Dict[str, Any]] = []
        for entry in entries:
            entry_id = entry.pop("_id", None)
            if entry_id and entry_id in seen_ids:
                continue
            if entry_id:
                seen_ids.add(entry_id)
            new_entries.append(entry)

        if not new_entries:
            if not expected_media_ids and expected_media_count is None and media_map:
                break
            time.sleep(AGGREGATION_POLL_INTERVAL)
            continue

        for entry in new_entries:
            _merge_media_entry(media_map, entry)

        if not expected_media_ids and expected_media_count is None and media_map:
            break

    if expected_media_ids:
        for media_id in expected_media_ids:
            record = media_map.get(str(media_id))
            if not record:
                LOGGER.warning("Aggregation missing media insights", extra={
                    "post_id": post_id,
                    "media_id": media_id,
                    "correlation_id": correlation_id
                })
                continue
            services = record.get("_services", set())
            missing_required = sorted(REQUIRED_SERVICES - services)
            missing_optional = sorted(OPTIONAL_SERVICES - services)
            if missing_required or missing_optional:
                LOGGER.warning("Aggregation incomplete for media", extra={
                    "post_id": post_id,
                    "media_id": media_id,
                    "missing_required": missing_required,
                    "missing_optional": missing_optional,
                    "correlation_id": correlation_id
                })

    return _finalize_media_map(media_map)


# Event type detection patterns
EVENT_PATTERNS = {
    "beach_party": {
        "required_tags": ["beach", "people"],
        "required_scenes": ["beach", "outdoor"],
        "min_images": 2
    },
    "wedding": {
        "required_tags": ["people", "formal"],
        "required_scenes": ["indoor", "outdoor"],
        "min_images": 3
    },
    "meeting": {
        "required_tags": ["people", "indoor"],
        "required_scenes": ["office", "indoor"],
        "min_images": 2
    },
    "concert": {
        "required_tags": ["people", "music"],
        "required_scenes": ["indoor", "outdoor"],
        "min_images": 2
    },
    "vacation": {
        "required_scenes": ["beach", "mountains", "outdoor"],
        "min_images": 3
    },
    "restaurant": {
        "required_tags": ["food", "people"],
        "required_scenes": ["restaurant", "indoor"],
        "min_images": 2
    },
    "outdoor_activity": {
        "required_scenes": ["outdoor", "nature", "mountains", "forest"],
        "min_images": 2
    },
    "indoor_gathering": {
        "required_tags": ["people"],
        "required_scenes": ["indoor"],
        "min_images": 3
    }
}


def _llm_summarize_captions(captions: List[str], http_session: requests.Session) -> Optional[str]:
    """Call HuggingFace text-generation API to summarize multiple captions into one."""
    if not LLM_API_URL or not LLM_API_TOKEN:
        return None

    prompt = (
        "Summarize the following image captions into a single cohesive sentence "
        "that describes the overall post:\n\n"
        + "\n".join(f"- {c}" for c in captions)
        + "\n\nSummary:"
    )

    try:
        resp = http_session.post(
            LLM_API_URL,
            headers={"Authorization": f"Bearer {LLM_API_TOKEN}"},
            json={"inputs": prompt, "parameters": {"max_new_tokens": 80, "temperature": 0.5}},
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()
        if isinstance(result, list) and result:
            text = result[0].get("generated_text", "").strip()
            if text:
                return text
    except Exception as exc:
        LOGGER.warning("LLM caption summarization failed, falling back", extra={"error": str(exc)})
    return None


class PostAggregator:
    """Aggregates AI insights for a post."""
    
    def __init__(self, http_session: Optional[requests.Session] = None):
        self.logger = LOGGER
        self._http_session = http_session or requests.Session()
    
    def aggregate_insights(self, media_insights: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate insights from multiple media items.
        
        Args:
            media_insights: List of media insight dictionaries
            
        Returns:
            Aggregated post-level insights
        """
        if not media_insights:
            return self._empty_aggregation()
        
        # Collect all tags and scenes
        all_tags = []
        all_scenes = []
        all_captions = []
        total_faces = 0
        is_safe = True
        min_moderation_confidence = 1.0
        
        for insight in media_insights:
            # Parse tags
            if insight.get("tags"):
                tags = json.loads(insight["tags"]) if isinstance(insight["tags"], str) else insight["tags"]
                all_tags.extend(tags)
            
            # Parse scenes
            if insight.get("scenes"):
                scenes = json.loads(insight["scenes"]) if isinstance(insight["scenes"], str) else insight["scenes"]
                all_scenes.extend(scenes)
            
            # Collect captions
            if insight.get("caption"):
                all_captions.append(insight["caption"])
            
            # Count faces
            if insight.get("facesDetected"):
                faces = int(insight["facesDetected"]) if isinstance(insight["facesDetected"], str) else insight["facesDetected"]
                total_faces += faces
            
            # Check moderation
            if insight.get("isSafe"):
                safe = insight["isSafe"] == "true" if isinstance(insight["isSafe"], str) else insight["isSafe"]
                is_safe = is_safe and safe
            
            if insight.get("moderationConfidence"):
                conf = float(insight["moderationConfidence"])
                min_moderation_confidence = min(min_moderation_confidence, conf)
        
        # Aggregate tags (top tags by frequency)
        tag_counts = Counter(all_tags)
        top_tags = [tag for tag, count in tag_counts.most_common(10)]
        
        # Aggregate scenes (top scenes by frequency)
        scene_counts = Counter(all_scenes)
        top_scenes = [scene for scene, count in scene_counts.most_common(5)]
        
        # Detect event type
        event_type = self._detect_event_type(top_tags, top_scenes, len(media_insights))
        
        # Generate combined caption
        combined_caption = self._generate_combined_caption(all_captions, top_tags, top_scenes)
        
        # Build aggregation result
        return {
            "mediaCount": len(media_insights),
            "allAiTags": all_tags,  # Raw collected tags before aggregation
            "allAiScenes": all_scenes,  # Raw collected scenes before aggregation
            "aggregatedTags": top_tags,  # Top tags after aggregation
            "aggregatedScenes": top_scenes,  # Top scenes after aggregation
            "totalFaces": total_faces,
            "isSafe": is_safe,
            "moderationConfidence": min_moderation_confidence,
            "inferredEventType": event_type,  # Renamed from eventType
            "combinedCaption": combined_caption,
            "hasMultipleImages": len(media_insights) > 1
        }
    
    def _detect_event_type(self, tags: List[str], scenes: List[str], num_images: int) -> str:
        """
        Detect event type based on tags, scenes, and image count.
        
        Args:
            tags: List of aggregated tags
            scenes: List of aggregated scenes
            num_images: Number of images in post
            
        Returns:
            Detected event type or "general"
        """
        tags_set = set(tag.lower() for tag in tags)
        scenes_set = set(scene.lower() for scene in scenes)
        
        # Score each event pattern
        scores = {}
        for event_name, pattern in EVENT_PATTERNS.items():
            score = 0
            
            # Check minimum images requirement
            if num_images < pattern.get("min_images", 1):
                continue
            
            # Check required tags
            if "required_tags" in pattern:
                required_tags = set(tag.lower() for tag in pattern["required_tags"])
                matching_tags = required_tags.intersection(tags_set)
                score += len(matching_tags) * 2  # Tags are weighted more
            
            # Check required scenes
            if "required_scenes" in pattern:
                required_scenes = set(scene.lower() for scene in pattern["required_scenes"])
                matching_scenes = required_scenes.intersection(scenes_set)
                score += len(matching_scenes)
            
            if score > 0:
                scores[event_name] = score
        
        # Return highest scoring event type
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        
        return "general"
    
    def _generate_combined_caption(self, captions: List[str], tags: List[str], scenes: List[str]) -> str:
        """
        Generate a combined caption from individual captions and aggregated data.
        Optionally uses an LLM to summarize when USE_LLM_CAPTIONS is enabled.
        
        Args:
            captions: List of individual captions
            tags: Aggregated tags
            scenes: Aggregated scenes
            
        Returns:
            Combined caption
        """
        if not captions:
            if tags and scenes:
                return f"A post featuring {', '.join(tags[:3])} in a {scenes[0]} setting"
            elif tags:
                return f"A post about {', '.join(tags[:3])}"
            elif scenes:
                return f"A {scenes[0]} scene"
            else:
                return "A visual post"
        
        if len(captions) == 1:
            return captions[0]
        
        # Multiple captions — try LLM summarization if enabled
        if USE_LLM_CAPTIONS:
            llm_summary = _llm_summarize_captions(captions, self._http_session)
            if llm_summary:
                return llm_summary

        # Fallback: concatenate first 3 captions
        return " ".join(captions[:3])
    
    def _empty_aggregation(self) -> Dict[str, Any]:
        """Return empty aggregation result."""
        return {
            "mediaCount": 0,
            "allAiTags": [],  # Raw collected tags
            "allAiScenes": [],  # Raw collected scenes
            "aggregatedTags": [],
            "aggregatedScenes": [],
            "totalFaces": 0,
            "isSafe": True,
            "moderationConfidence": 1.0,
            "inferredEventType": "general",  # Renamed from eventType
            "combinedCaption": "",
            "hasMultipleImages": False
        }


def handle_message(message_id: str, data: dict, publisher: RedisStreamPublisher, aggregator: PostAggregator):
    """
    Handle aggregation trigger message.
    
    Args:
        message_id: Redis Stream message ID
        data: Message data
        publisher: Redis Stream publisher
        aggregator: PostAggregator instance
    """
    try:
        # Decode message data
        decoded_data = decode_message(data)
        post_id = int(decoded_data.get("postId", 0))
        media_insights_str = decoded_data.get("mediaInsights", "[]")
        correlation_id = decoded_data.get("correlationId", "")  # Extract correlationId for log tracing
        
        LOGGER.info("Received aggregation trigger", extra={
            "message_id": message_id,
            "post_id": post_id,
            "correlation_id": correlation_id
        })
        
        if not post_id:
            LOGGER.error("Invalid message format - missing postId", extra={"data": decoded_data})
            return
        
        # Parse media insights
        media_insights = json.loads(media_insights_str) if isinstance(media_insights_str, str) and media_insights_str else media_insights_str
        if not isinstance(media_insights, list):
            media_insights = [media_insights] if media_insights else []

        expected_media_ids = _normalize_media_ids(decoded_data.get("allMediaIds"))
        total_media_raw = decoded_data.get("totalMedia")
        try:
            expected_media_count = int(total_media_raw) if total_media_raw not in (None, "") else None
        except ValueError:
            expected_media_count = None

        media_insights = collect_media_insights(
            post_id=post_id,
            correlation_id=correlation_id,
            initial_insights=media_insights,
            expected_media_ids=expected_media_ids,
            expected_media_count=expected_media_count,
        )

        LOGGER.info("Collected media insights", extra={
            "post_id": post_id,
            "media_count": len(media_insights),
            "expected_media_ids": list(expected_media_ids),
            "expected_media_count": expected_media_count,
            "correlation_id": correlation_id
        })
        
        LOGGER.info("Aggregating insights", extra={
            "post_id": post_id,
            "media_count": len(media_insights),
            "correlation_id": correlation_id
        })
        
        # Aggregate insights
        aggregated = aggregator.aggregate_insights(media_insights)
        
        LOGGER.info("Aggregation complete", extra={
            "post_id": post_id,
            "event_type": aggregated["inferredEventType"],
            "total_faces": aggregated["totalFaces"],
            "tag_count": len(aggregated["aggregatedTags"]),
            "correlation_id": correlation_id
        })
        
        # Publish enriched insights
        # Convert arrays to JSON strings for backend deserialization
        # Backend expects JSON strings that it will parse into List<String>
        all_ai_tags_json = json.dumps(aggregated["allAiTags"]) if aggregated["allAiTags"] else "[]"
        all_ai_scenes_json = json.dumps(aggregated["allAiScenes"]) if aggregated["allAiScenes"] else "[]"
        aggregated_tags_json = json.dumps(aggregated["aggregatedTags"]) if aggregated["aggregatedTags"] else "[]"
        aggregated_scenes_json = json.dumps(aggregated["aggregatedScenes"]) if aggregated["aggregatedScenes"] else "[]"
        
        result_message = {
            "postId": str(post_id),
            "mediaCount": str(aggregated["mediaCount"]),
            "allAiTags": all_ai_tags_json,
            "allAiScenes": all_ai_scenes_json,
            "aggregatedTags": aggregated_tags_json,
            "aggregatedScenes": aggregated_scenes_json,
            "totalFaces": str(aggregated["totalFaces"]),
            "isSafe": "true" if aggregated["isSafe"] else "false",
            "moderationConfidence": str(aggregated["moderationConfidence"]),
            "inferredEventType": aggregated["inferredEventType"],
            "combinedCaption": aggregated["combinedCaption"],
            "hasMultipleImages": "true" if aggregated["hasMultipleImages"] else "false",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "correlationId": correlation_id,
            "version": "1",
        }
        
        publisher.publish(STREAM_OUTPUT, result_message)
        LOGGER.info("Published enriched insights", extra={
            "post_id": post_id,
            "correlation_id": correlation_id,
            "stream": STREAM_OUTPUT
        })
        
    except Exception as e:
        LOGGER.exception("Error processing aggregation", extra={
            "error": str(e),
            "message_id": message_id,
            "correlation_id": decoded_data.get("correlationId", "") if 'decoded_data' in locals() else ""
        })


def main():
    """Main worker function."""
    LOGGER.info("Post Aggregator Worker starting (Redis Streams)")
    LOGGER.info("Connecting to Redis Streams", extra={"redis_url": REDIS_URL})

    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    consumer = None
    publisher = None
    http_session = None

    try:
        http_session = requests.Session()
        publisher = RedisStreamPublisher(REDIS_URL)
        consumer = RedisStreamConsumer(
            REDIS_URL,
            STREAM_INPUT,
            CONSUMER_GROUP,
            CONSUMER_NAME,
            shutdown_event=shutdown_event,
        )
        aggregator = PostAggregator(http_session=http_session)
        
        LOGGER.info("Connected to Redis Streams", extra={
            "input_stream": STREAM_INPUT,
            "output_stream": STREAM_OUTPUT,
            "consumer_group": CONSUMER_GROUP
        })

        start_health_server(
            service_name="post-aggregator",
            health_fn=lambda: {"status": "healthy", "service": "post-aggregator"},
        )
        mark_ready()
        
        # Define handler with dependencies bound
        def message_handler(message_id: str, data: dict):
            handle_message(message_id, data, publisher, aggregator)
        
        LOGGER.info("Worker ready - waiting for aggregation triggers")
        
        # Start consuming (blocks indefinitely)
        consumer.consume(message_handler, block_ms=5000, count=1)
        
    except KeyboardInterrupt:
        LOGGER.warning("Interrupted by user")
    except Exception as e:
        LOGGER.exception("Unexpected error in main loop", extra={"error": str(e)})
    finally:
        shutdown_event.set()
        if consumer:
            consumer.close()
        if publisher:
            publisher.close()
        if http_session:
            http_session.close()
        LOGGER.info("Worker shut down complete")


if __name__ == "__main__":
    main()
