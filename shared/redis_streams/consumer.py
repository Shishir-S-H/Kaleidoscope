"""Redis Stream Consumer for consuming messages from Redis Streams."""

import logging
import threading
import time
from typing import Callable, Optional
import redis

logger = logging.getLogger(__name__)

PENDING_IDLE_MS = 300_000  # 5 minutes
PENDING_CHECK_INTERVAL = 60  # seconds
DEFAULT_MAX_CLAIM_FAILURES = 3


class RedisStreamConsumer:
    """Consumes messages from Redis Streams using consumer groups."""
    
    def __init__(
        self,
        redis_url: str,
        stream_name: str,
        consumer_group: str,
        consumer_name: str,
        shutdown_event: Optional[threading.Event] = None,
        dlq_publisher: Optional[Callable] = None,
        max_claim_failures: int = DEFAULT_MAX_CLAIM_FAILURES,
    ):
        """
        Initialize Redis Stream Consumer.
        
        Args:
            redis_url: Redis connection URL
            stream_name: Name of the stream to consume from
            consumer_group: Consumer group name
            consumer_name: Unique consumer name within the group
            shutdown_event: Optional threading.Event to signal graceful shutdown
            dlq_publisher: Optional callback(message_id, data) to publish poison
                           messages to a dead-letter queue after max_claim_failures
            max_claim_failures: Number of failed claim attempts before sending to DLQ
        """
        self.redis_client = redis.from_url(redis_url, decode_responses=False)
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self.shutdown_event = shutdown_event
        self.dlq_publisher = dlq_publisher
        self.max_claim_failures = max_claim_failures
        self._last_pending_check: float = 0.0
        
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
    
    def claim_pending_messages(self, handler: Callable, count: int = 50) -> int:
        """
        Scan for messages idle longer than PENDING_IDLE_MS, claim them via XCLAIM,
        and reprocess through *handler*.  After *max_claim_failures* delivery
        attempts the message is forwarded to the DLQ (if a publisher was provided)
        and ACKed so it stops blocking the group.

        Args:
            handler: Same message handler used by consume()
            count: Max pending entries to inspect per call

        Returns:
            Number of messages successfully reprocessed
        """
        reprocessed = 0
        try:
            pending = self.redis_client.xpending_range(
                self.stream_name,
                self.consumer_group,
                min="-",
                max="+",
                count=count,
            )
            if not pending:
                return 0

            for entry in pending:
                msg_id = entry.get("message_id", b"")
                if isinstance(msg_id, bytes):
                    msg_id = msg_id.decode("utf-8")

                idle = entry.get("time_since_delivered", 0)
                times_delivered = entry.get("times_delivered", 1)

                if idle < PENDING_IDLE_MS:
                    continue

                if times_delivered >= self.max_claim_failures and self.dlq_publisher:
                    try:
                        raw = self.redis_client.xrange(
                            self.stream_name, min=msg_id, max=msg_id, count=1
                        )
                        data = raw[0][1] if raw else {}
                        self.dlq_publisher(msg_id, data)
                        logger.warning(
                            "Message exceeded max claim attempts, sent to DLQ",
                            extra={
                                "message_id": msg_id,
                                "times_delivered": times_delivered,
                            },
                        )
                    except Exception as dlq_err:
                        logger.error(
                            "Failed to publish to DLQ: %s", dlq_err,
                            extra={"message_id": msg_id},
                        )
                    # ACK so the message leaves the pending list regardless
                    self.redis_client.xack(
                        self.stream_name, self.consumer_group, msg_id
                    )
                    continue

                # Attempt to claim and reprocess
                try:
                    claimed = self.redis_client.xclaim(
                        self.stream_name,
                        self.consumer_group,
                        self.consumer_name,
                        min_idle_time=PENDING_IDLE_MS,
                        message_ids=[msg_id],
                    )
                    for claimed_id, claimed_data in claimed:
                        cid = (
                            claimed_id.decode("utf-8")
                            if isinstance(claimed_id, bytes)
                            else claimed_id
                        )
                        handler(cid, claimed_data)
                        self.redis_client.xack(
                            self.stream_name, self.consumer_group, cid
                        )
                        reprocessed += 1
                        logger.info("Reprocessed claimed message: %s", cid)
                except Exception as claim_err:
                    logger.error(
                        "Error claiming/reprocessing message %s: %s",
                        msg_id,
                        claim_err,
                        exc_info=True,
                    )

        except Exception as e:
            logger.error("Error in claim_pending_messages: %s", e, exc_info=True)

        return reprocessed
    
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

        # Claim stale pending messages on startup
        self.claim_pending_messages(handler)
        self._last_pending_check = time.time()
        
        while True:
            if self.shutdown_event and self.shutdown_event.is_set():
                logger.info("Shutdown event detected, exiting consumer loop")
                break

            # Periodically re-check pending messages
            now = time.time()
            if now - self._last_pending_check >= PENDING_CHECK_INTERVAL:
                self.claim_pending_messages(handler)
                self._last_pending_check = now

            try:
                messages = self.redis_client.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_name,
                    streams={self.stream_name: '>'},
                    count=count,
                    block=block_ms
                )
                
                if not messages:
                    continue
                
                for stream_name, stream_messages in messages:
                    for message_id, data in stream_messages:
                        try:
                            msg_id = message_id.decode('utf-8') if isinstance(message_id, bytes) else message_id
                            
                            handler(msg_id, data)
                            
                            self.redis_client.xack(
                                self.stream_name,
                                self.consumer_group,
                                msg_id
                            )
                            logger.debug(f"Processed and ACKed message: {msg_id}")
                            
                        except Exception as e:
                            logger.error(f"Error processing message {message_id}: {e}", exc_info=True)
                            continue
                
            except KeyboardInterrupt:
                logger.info("Consumer interrupted by user")
                break
            except redis.exceptions.ResponseError as e:
                error_str = str(e)
                if "NOGROUP" in error_str and auto_create_group:
                    logger.warning(f"Consumer group '{self.consumer_group}' not found for stream '{self.stream_name}'. Attempting to create...")
                    try:
                        self.create_consumer_group(start_id="0")
                        logger.info(f"Successfully created consumer group '{self.consumer_group}' for stream '{self.stream_name}'")
                    except Exception as create_error:
                        logger.error(f"Failed to create consumer group: {create_error}", exc_info=True)
                        time.sleep(2)
                else:
                    logger.error(f"Redis error in consumer loop: {e}", exc_info=True)
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Error in consumer loop: {e}", exc_info=True)
                time.sleep(1)
    
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
