"""Redis Stream Consumer for consuming messages from Redis Streams."""

import logging
import time
from typing import Callable, Optional
import redis

logger = logging.getLogger(__name__)


class RedisStreamConsumer:
    """Consumes messages from Redis Streams using consumer groups."""
    
    def __init__(
        self,
        redis_url: str,
        stream_name: str,
        consumer_group: str,
        consumer_name: str
    ):
        """
        Initialize Redis Stream Consumer.
        
        Args:
            redis_url: Redis connection URL
            stream_name: Name of the stream to consume from
            consumer_group: Consumer group name
            consumer_name: Unique consumer name within the group
        """
        self.redis_client = redis.from_url(redis_url, decode_responses=False)
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        
        logger.info(
            f"RedisStreamConsumer initialized - "
            f"Stream: {stream_name}, Group: {consumer_group}, Consumer: {consumer_name}"
        )
    
    def create_consumer_group(self, start_id: str = "0") -> bool:
        """
        Create consumer group if it doesn't exist.
        
        Args:
            start_id: Starting message ID ('0' for all messages, '$' for new messages only)
        
        Returns:
            True if created or already exists
        """
        try:
            self.redis_client.xgroup_create(
                self.stream_name,
                self.consumer_group,
                id=start_id,
                mkstream=True
            )
            logger.info(f"Created consumer group '{self.consumer_group}' on stream '{self.stream_name}'")
            return True
            
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.info(f"Consumer group '{self.consumer_group}' already exists")
                return True
            else:
                logger.error(f"Error creating consumer group: {e}")
                raise
    
    def consume(
        self,
        handler: Callable,
        block_ms: int = 5000,
        count: int = 10,
        auto_create_group: bool = True
    ):
        """
        Start consuming messages from the stream.
        
        Args:
            handler: Callback function to process each message. 
                    Should accept (message_id, data) as arguments
            block_ms: Milliseconds to block waiting for new messages
            count: Maximum number of messages to read per call
            auto_create_group: Automatically create consumer group if needed
        """
        if auto_create_group:
            self.create_consumer_group(start_id="0")
        
        logger.info(f"Starting consumer loop for {self.stream_name}...")
        
        while True:
            try:
                # Read messages from the stream
                messages = self.redis_client.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_name,
                    streams={self.stream_name: '>'},
                    count=count,
                    block=block_ms
                )
                
                if not messages:
                    continue
                
                # Process messages
                for stream_name, stream_messages in messages:
                    for message_id, data in stream_messages:
                        try:
                            # Decode message ID
                            msg_id = message_id.decode('utf-8') if isinstance(message_id, bytes) else message_id
                            
                            # Call handler
                            handler(msg_id, data)
                            
                            # Acknowledge message
                            self.redis_client.xack(
                                self.stream_name,
                                self.consumer_group,
                                msg_id
                            )
                            logger.debug(f"Processed and ACKed message: {msg_id}")
                            
                        except Exception as e:
                            logger.error(f"Error processing message {message_id}: {e}", exc_info=True)
                            # Message will remain in pending list for retry
                            continue
                
            except KeyboardInterrupt:
                logger.info("Consumer interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in consumer loop: {e}", exc_info=True)
                time.sleep(1)  # Brief pause before retry
    
    def get_pending_messages(self, count: int = 100):
        """
        Get pending messages for this consumer.
        
        Args:
            count: Maximum number of pending messages to retrieve
        
        Returns:
            List of pending messages
        """
        try:
            pending = self.redis_client.xpending_range(
                self.stream_name,
                self.consumer_group,
                min='-',
                max='+',
                count=count,
                consumername=self.consumer_name
            )
            return pending
        except Exception as e:
            logger.error(f"Error getting pending messages: {e}")
            return []
    
    def close(self):
        """Close Redis connection."""
        self.redis_client.close()
        logger.info("RedisStreamConsumer connection closed")

