"""Redis Stream Publisher for publishing messages to Redis Streams."""

import json
import logging
from typing import Dict, Any, List
import redis

logger = logging.getLogger(__name__)


class RedisStreamPublisher:
    """Publishes messages to Redis Streams."""
    
    def __init__(self, redis_url: str):
        """
        Initialize Redis Stream Publisher.
        
        Args:
            redis_url: Redis connection URL (e.g., 'redis://localhost:6379')
        """
        self.redis_client = redis.from_url(redis_url, decode_responses=False)
        logger.info(f"RedisStreamPublisher initialized with URL: {redis_url}")
    
    def publish(self, stream_name: str, data: Dict[str, Any]) -> str:
        """
        Publish a single message to a Redis Stream.
        
        Args:
            stream_name: Name of the stream
            data: Dictionary of field-value pairs to publish
        
        Returns:
            Message ID assigned by Redis
        """
        try:
            # Convert all values to strings (Redis requirement)
            redis_data = {k: str(v) if not isinstance(v, bytes) else v 
                         for k, v in data.items()}
            
            message_id = self.redis_client.xadd(stream_name, redis_data)
            logger.debug(f"Published to {stream_name}: {message_id}")
            return message_id.decode('utf-8') if isinstance(message_id, bytes) else message_id
            
        except Exception as e:
            logger.error(f"Error publishing to {stream_name}: {e}")
            raise
    
    def publish_batch(self, stream_name: str, messages: List[Dict[str, Any]]) -> List[str]:
        """
        Publish multiple messages to a Redis Stream (uses pipeline for efficiency).
        
        Args:
            stream_name: Name of the stream
            messages: List of dictionaries to publish
        
        Returns:
            List of message IDs
        """
        try:
            pipeline = self.redis_client.pipeline()
            
            for message in messages:
                redis_data = {k: str(v) if not isinstance(v, bytes) else v 
                             for k, v in message.items()}
                pipeline.xadd(stream_name, redis_data)
            
            message_ids = pipeline.execute()
            logger.info(f"Published {len(messages)} messages to {stream_name}")
            
            return [mid.decode('utf-8') if isinstance(mid, bytes) else mid 
                    for mid in message_ids]
            
        except Exception as e:
            logger.error(f"Error publishing batch to {stream_name}: {e}")
            raise
    
    def close(self):
        """Close Redis connection."""
        self.redis_client.close()
        logger.info("RedisStreamPublisher connection closed")

