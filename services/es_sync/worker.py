#!/usr/bin/env python3
"""
Elasticsearch Sync Service
Syncs data from PostgreSQL read models to Elasticsearch indices.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import time

# Add parent directories to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables
load_dotenv()

# Import logger and Redis Streams
from shared.utils.logger import get_logger
from shared.redis_streams import RedisStreamPublisher, RedisStreamConsumer
from shared.redis_streams.utils import decode_message

# Initialize logger
LOGGER = get_logger("es-sync")

# Redis Streams configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STREAM_INPUT = "es-sync-queue"
CONSUMER_GROUP = "es-sync-group"
CONSUMER_NAME = "es-sync-worker-1"

# Elasticsearch configuration
ES_HOST = os.getenv("ES_HOST", "http://elasticsearch:9200")

# Index mapping
INDEX_MAPPING = {
    "media_search": "media_search",
    "post_search": "post_search",
    "user_search": "user_search",
    "face_search": "face_search",
    "recommendations_knn": "recommendations_knn",
    "feed_personalized": "feed_personalized",
    "known_faces_index": "known_faces_index"
}

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


class ElasticsearchSyncHandler:
    """Handles syncing data to Elasticsearch."""
    
    def __init__(self, es_host: str):
        self.es_host = es_host
        self.logger = LOGGER
        
        # Import elasticsearch client
        try:
            from elasticsearch import Elasticsearch
            self.es_client = Elasticsearch([es_host])
            self.logger.info("Connected to Elasticsearch", extra={"host": es_host})
        except ImportError:
            self.logger.error("elasticsearch package not installed. Run: pip install elasticsearch")
            self.es_client = None
        except Exception as e:
            self.logger.error(f"Failed to connect to Elasticsearch: {e}")
            self.es_client = None
    
    def sync_document(self, index_name: str, document_id: str, document: Dict[str, Any], 
                     retry_count: int = 0) -> bool:
        """
        Sync a document to Elasticsearch with retry logic.
        
        Args:
            index_name: Elasticsearch index name
            document_id: Document ID
            document: Document data
            retry_count: Current retry attempt
            
        Returns:
            True if successful, False otherwise
        """
        if not self.es_client:
            self.logger.error("Elasticsearch client not available")
            return False
        
        try:
            # Index the document
            response = self.es_client.index(
                index=index_name,
                id=document_id,
                document=document
            )
            
            self.logger.info("Document synced successfully", extra={
                "index": index_name,
                "document_id": document_id,
                "result": response.get("result")
            })
            return True
            
        except Exception as e:
            self.logger.error(f"Error syncing document: {e}", extra={
                "index": index_name,
                "document_id": document_id,
                "retry_count": retry_count
            })
            
            # Retry logic
            if retry_count < MAX_RETRIES:
                delay = RETRY_DELAY_SECONDS * (2 ** retry_count)  # Exponential backoff
                self.logger.info(f"Retrying in {delay} seconds...", extra={
                    "retry_count": retry_count + 1,
                    "max_retries": MAX_RETRIES
                })
                time.sleep(delay)
                return self.sync_document(index_name, document_id, document, retry_count + 1)
            
            return False
    
    def delete_document(self, index_name: str, document_id: str, retry_count: int = 0) -> bool:
        """
        Delete a document from Elasticsearch with retry logic.
        
        Args:
            index_name: Elasticsearch index name
            document_id: Document ID
            retry_count: Current retry attempt
            
        Returns:
            True if successful, False otherwise
        """
        if not self.es_client:
            self.logger.error("Elasticsearch client not available")
            return False
        
        try:
            response = self.es_client.delete(
                index=index_name,
                id=document_id
            )
            
            self.logger.info("Document deleted successfully", extra={
                "index": index_name,
                "document_id": document_id,
                "result": response.get("result")
            })
            return True
            
        except Exception as e:
            # Document not found is not an error
            if "not_found" in str(e).lower():
                self.logger.info("Document not found (already deleted)", extra={
                    "index": index_name,
                    "document_id": document_id
                })
                return True
            
            self.logger.error(f"Error deleting document: {e}", extra={
                "index": index_name,
                "document_id": document_id,
                "retry_count": retry_count
            })
            
            # Retry logic
            if retry_count < MAX_RETRIES:
                delay = RETRY_DELAY_SECONDS * (2 ** retry_count)
                self.logger.info(f"Retrying in {delay} seconds...", extra={
                    "retry_count": retry_count + 1,
                    "max_retries": MAX_RETRIES
                })
                time.sleep(delay)
                return self.delete_document(index_name, document_id, retry_count + 1)
            
            return False


def parse_vector_field(value: Any) -> Optional[list]:
    """
    Parse a vector field from string or list.
    
    Args:
        value: Vector value (string or list)
        
    Returns:
        Parsed vector as list or None
    """
    if not value:
        return None
    
    if isinstance(value, list):
        return value
    
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    
    return None


def handle_message(message_id: str, data: dict, sync_handler: ElasticsearchSyncHandler):
    """
    Handle ES sync message.
    
    Args:
        message_id: Redis Stream message ID
        data: Message data
        sync_handler: ElasticsearchSyncHandler instance
    """
    try:
        # Decode message data
        decoded_data = decode_message(data)
        
        operation = decoded_data.get("operation", "index")  # index or delete
        index_type = decoded_data.get("indexType")  # Which read model
        document_id = decoded_data.get("documentId")
        document_data_str = decoded_data.get("documentData", "{}")
        
        LOGGER.info("Received sync message", extra={
            "message_id": message_id,
            "operation": operation,
            "index_type": index_type,
            "document_id": document_id
        })
        
        if not index_type or not document_id:
            LOGGER.error("Invalid message format", extra={"data": decoded_data})
            return
        
        # Get ES index name
        index_name = INDEX_MAPPING.get(index_type)
        if not index_name:
            LOGGER.error(f"Unknown index type: {index_type}")
            return
        
        # Handle operation
        if operation == "delete":
            success = sync_handler.delete_document(index_name, document_id)
        else:
            # Parse document data
            document_data = json.loads(document_data_str) if isinstance(document_data_str, str) else document_data_str
            
            # Parse vector fields if present
            if "embedding" in document_data:
                document_data["embedding"] = parse_vector_field(document_data["embedding"])
            if "imageEmbedding" in document_data:
                document_data["imageEmbedding"] = parse_vector_field(document_data["imageEmbedding"])
            if "textEmbedding" in document_data:
                document_data["textEmbedding"] = parse_vector_field(document_data["textEmbedding"])
            if "faceEmbedding" in document_data:
                document_data["faceEmbedding"] = parse_vector_field(document_data["faceEmbedding"])
            
            success = sync_handler.sync_document(index_name, document_id, document_data)
        
        if success:
            LOGGER.info("Sync completed successfully", extra={
                "index": index_name,
                "document_id": document_id,
                "operation": operation
            })
        else:
            LOGGER.error("Sync failed", extra={
                "index": index_name,
                "document_id": document_id,
                "operation": operation
            })
        
    except Exception as e:
        LOGGER.exception("Error processing sync message", extra={
            "error": str(e),
            "message_id": message_id
        })


def main():
    """Main worker function."""
    LOGGER.info("Elasticsearch Sync Worker starting (Redis Streams)")
    LOGGER.info("Connecting to Elasticsearch", extra={"host": ES_HOST})
    LOGGER.info("Connecting to Redis Streams", extra={"redis_url": REDIS_URL})
    
    try:
        # Initialize components
        sync_handler = ElasticsearchSyncHandler(ES_HOST)
        consumer = RedisStreamConsumer(
            REDIS_URL,
            STREAM_INPUT,
            CONSUMER_GROUP,
            CONSUMER_NAME
        )
        
        LOGGER.info("Connected to Redis Streams", extra={
            "input_stream": STREAM_INPUT,
            "consumer_group": CONSUMER_GROUP
        })
        
        # Define handler with dependencies bound
        def message_handler(message_id: str, data: dict):
            handle_message(message_id, data, sync_handler)
        
        LOGGER.info("Worker ready - waiting for sync requests")
        
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

