#!/usr/bin/env python3
"""
Post Aggregator Service
Aggregates AI insights from multiple images in a post to derive post-level insights.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Set
from collections import Counter
from dotenv import load_dotenv

# Add parent directories to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables
load_dotenv()

# Import logger and Redis Streams
from shared.utils.logger import get_logger
from shared.redis_streams import RedisStreamPublisher, RedisStreamConsumer
from shared.redis_streams.utils import decode_message
import redis

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


class PostAggregator:
    """Aggregates AI insights for a post."""
    
    def __init__(self):
        self.logger = LOGGER
    
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
            "aggregatedTags": top_tags,
            "aggregatedScenes": top_scenes,
            "totalFaces": total_faces,
            "isSafe": is_safe,
            "moderationConfidence": min_moderation_confidence,
            "eventType": event_type,
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
        
        Args:
            captions: List of individual captions
            tags: Aggregated tags
            scenes: Aggregated scenes
            
        Returns:
            Combined caption
        """
        if not captions:
            # Generate from tags and scenes
            if tags and scenes:
                return f"A post featuring {', '.join(tags[:3])} in a {scenes[0]} setting"
            elif tags:
                return f"A post about {', '.join(tags[:3])}"
            elif scenes:
                return f"A {scenes[0]} scene"
            else:
                return "A visual post"
        
        # If single caption, return it
        if len(captions) == 1:
            return captions[0]
        
        # Multiple captions - create summary
        # For now, just combine them
        # TODO: Use LLM to create better summary in future
        return " ".join(captions[:3])  # Limit to first 3 captions
    
    def _empty_aggregation(self) -> Dict[str, Any]:
        """Return empty aggregation result."""
        return {
            "mediaCount": 0,
            "aggregatedTags": [],
            "aggregatedScenes": [],
            "totalFaces": 0,
            "isSafe": True,
            "moderationConfidence": 1.0,
            "eventType": "general",
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
        
        LOGGER.info("Received aggregation trigger", extra={
            "message_id": message_id,
            "post_id": post_id
        })
        
        if not post_id:
            LOGGER.error("Invalid message format - missing postId", extra={"data": decoded_data})
            return
        
        # Parse media insights
        media_insights = json.loads(media_insights_str) if isinstance(media_insights_str, str) else media_insights_str

        # If not provided in trigger, fetch from insight streams by postId
        if not media_insights:
            try:
                r = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True)
                collected: List[Dict[str, Any]] = []
                for stream in (INSIGHTS_STREAM, FACES_STREAM):
                    try:
                        entries = r.xrange(stream, "-", "+", count=500)
                    except Exception:
                        continue
                    for _, values in entries:
                        post_val = values.get("postId") or values.get("post_id")
                        if post_val == str(post_id):
                            collected.append(values)
                media_insights = collected
                LOGGER.info("Fetched media insights from streams", extra={
                    "post_id": post_id,
                    "num_collected": len(media_insights)
                })
            except Exception as fetch_err:
                LOGGER.error("Failed to fetch media insights from streams", extra={
                    "error": str(fetch_err),
                    "post_id": post_id
                })
        
        LOGGER.info("Aggregating insights", extra={
            "post_id": post_id,
            "media_count": len(media_insights)
        })
        
        # Aggregate insights
        aggregated = aggregator.aggregate_insights(media_insights)
        
        LOGGER.info("Aggregation complete", extra={
            "post_id": post_id,
            "event_type": aggregated["eventType"],
            "total_faces": aggregated["totalFaces"],
            "tag_count": len(aggregated["aggregatedTags"])
        })
        
        # Publish enriched insights
        result_message = {
            "postId": str(post_id),
            "mediaCount": str(aggregated["mediaCount"]),
            "aggregatedTags": json.dumps(aggregated["aggregatedTags"]),
            "aggregatedScenes": json.dumps(aggregated["aggregatedScenes"]),
            "totalFaces": str(aggregated["totalFaces"]),
            "isSafe": "true" if aggregated["isSafe"] else "false",
            "moderationConfidence": str(aggregated["moderationConfidence"]),
            "eventType": aggregated["eventType"],
            "combinedCaption": aggregated["combinedCaption"],
            "hasMultipleImages": "true" if aggregated["hasMultipleImages"] else "false"
        }
        
        publisher.publish(STREAM_OUTPUT, result_message)
        LOGGER.info("Published enriched insights", extra={
            "post_id": post_id,
            "stream": STREAM_OUTPUT
        })
        
    except Exception as e:
        LOGGER.exception("Error processing aggregation", extra={
            "error": str(e),
            "message_id": message_id
        })


def main():
    """Main worker function."""
    LOGGER.info("Post Aggregator Worker starting (Redis Streams)")
    LOGGER.info("Connecting to Redis Streams", extra={"redis_url": REDIS_URL})
    
    try:
        # Initialize components
        publisher = RedisStreamPublisher(REDIS_URL)
        consumer = RedisStreamConsumer(
            REDIS_URL,
            STREAM_INPUT,
            CONSUMER_GROUP,
            CONSUMER_NAME
        )
        aggregator = PostAggregator()
        
        LOGGER.info("Connected to Redis Streams", extra={
            "input_stream": STREAM_INPUT,
            "output_stream": STREAM_OUTPUT,
            "consumer_group": CONSUMER_GROUP
        })
        
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
        LOGGER.info("Worker shutting down")


if __name__ == "__main__":
    main()

