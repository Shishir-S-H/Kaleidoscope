"""Base worker class extracting common boilerplate from all AI service workers."""

import logging
import os
import signal
import threading
import time
from typing import Callable, Optional

from shared.redis_streams import RedisStreamConsumer, RedisStreamPublisher
from shared.utils.health_server import start_health_server, mark_ready
from shared.utils.health import check_health
from shared.utils.metrics import get_metrics
from shared.utils.http_client import close_http_session

logger = logging.getLogger(__name__)


class BaseWorker:
    """Base class for all stream-processing workers.
    
    Subclasses implement process_message(decoded_data) and override
    class-level attributes for configuration.
    """
    
    SERVICE_NAME: str = "unknown"
    STREAM_INPUT: str = ""
    STREAM_OUTPUT: str = ""
    CONSUMER_GROUP: str = ""
    CONSUMER_NAME: str = ""
    STREAM_DLQ: str = "ai-processing-dlq"
    
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.shutdown_event = threading.Event()
        self.consumer: Optional[RedisStreamConsumer] = None
        self.publisher: Optional[RedisStreamPublisher] = None
        self.logger = logging.getLogger(self.SERVICE_NAME)
        
        signal.signal(signal.SIGTERM, self._shutdown_handler)
        signal.signal(signal.SIGINT, self._shutdown_handler)
    
    def _shutdown_handler(self, signum, frame):
        self.logger.info("Shutdown signal received (signal %s)", signum)
        self.shutdown_event.set()
    
    def process_message(self, message_id: str, decoded_data: dict):
        """Override in subclasses to handle a decoded message."""
        raise NotImplementedError
    
    def run(self):
        """Start the worker: init connections, health server, consume loop."""
        self.logger.info("%s worker starting", self.SERVICE_NAME)
        
        try:
            self.publisher = RedisStreamPublisher(self.redis_url)
            self.consumer = RedisStreamConsumer(
                self.redis_url,
                self.STREAM_INPUT,
                self.CONSUMER_GROUP,
                self.CONSUMER_NAME,
            )
            
            start_health_server(
                service_name=self.SERVICE_NAME,
                health_fn=lambda: check_health(get_metrics(), self.SERVICE_NAME),
                metrics_fn=get_metrics,
            )
            
            mark_ready()
            self.logger.info("%s worker ready — waiting for messages", self.SERVICE_NAME)
            
            self.consumer.consume(self._message_handler, block_ms=5000, count=1)
            
        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
        except Exception:
            self.logger.exception("Unexpected error in main loop")
        finally:
            self.shutdown_event.set()
            if self.consumer:
                self.consumer.close()
            if self.publisher:
                self.publisher.close()
            close_http_session()
            self.logger.info("%s worker shut down complete", self.SERVICE_NAME)
    
    def _message_handler(self, message_id: str, data: dict):
        from shared.redis_streams.utils import decode_message
        decoded_data = decode_message(data)
        self.process_message(message_id, decoded_data)
