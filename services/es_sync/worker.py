#!/usr/bin/env python3
"""
Elasticsearch Sync Service
Syncs data from PostgreSQL read models to Elasticsearch indices.
"""

import datetime
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

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

# PostgreSQL configuration
# Try to parse from SPRING_DATASOURCE_URL first, then fall back to individual variables
SPRING_DATASOURCE_URL = os.getenv("SPRING_DATASOURCE_URL", "")
if SPRING_DATASOURCE_URL:
    # Parse JDBC URL: jdbc:postgresql://host:port/database?params
    match = re.match(r'jdbc:postgresql://([^:/]+)(?::(\d+))?/([^?]+)', SPRING_DATASOURCE_URL)
    if match:
        DB_HOST = match.group(1)
        DB_PORT = int(match.group(2)) if match.group(2) else 5432
        DB_NAME = match.group(3)
        DB_USER = os.getenv("DB_USERNAME") or os.getenv("DB_USER", "postgres")
        DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    else:
        # Fall back to individual variables
        DB_HOST = os.getenv("DB_HOST", "localhost")
        DB_PORT = int(os.getenv("DB_PORT", "5432"))
        DB_NAME = os.getenv("DB_NAME", "kaleidoscope")
        DB_USER = os.getenv("DB_USERNAME") or os.getenv("DB_USER", "postgres")
        DB_PASSWORD = os.getenv("DB_PASSWORD", "")
else:
    # Use individual variables
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME", "kaleidoscope")
    DB_USER = os.getenv("DB_USERNAME") or os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Index mapping: indexType -> (table_name, es_index_name)
INDEX_MAPPING = {
    "media_search": ("read_model_media_search", "media_search"),
    "post_search": ("read_model_post_search", "post_search"),
    "user_search": ("read_model_user_search", "user_search"),
    "face_search": ("read_model_face_search", "face_search"),
    "recommendations_knn": ("read_model_recommendations_knn", "recommendations_knn"),
    "feed_personalized": ("read_model_feed_personalized", "feed_personalized"),
    "known_faces_index": ("read_model_known_faces", "known_faces_index")
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
        
        # Initialize PostgreSQL connection
        self.pg_conn = None
        self._init_postgresql()
    
    def _init_postgresql(self):
        """Initialize PostgreSQL connection."""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            self.pg_conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            self.logger.info("Connected to PostgreSQL", extra={
                "host": DB_HOST,
                "port": DB_PORT,
                "database": DB_NAME
            })
        except ImportError:
            self.logger.error("psycopg2 package not installed. Run: pip install psycopg2-binary")
            self.pg_conn = None
        except Exception as e:
            self.logger.error(f"Failed to connect to PostgreSQL: {e}", extra={
                "host": DB_HOST,
                "port": DB_PORT,
                "database": DB_NAME
            })
            self.pg_conn = None
    
    def read_from_postgresql(self, table_name: str, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Read data from PostgreSQL read model table.
        
        Args:
            table_name: Name of the read model table
            document_id: Document ID (primary key value)
            
        Returns:
            Dictionary with row data or None if not found
        """
        if not self.pg_conn:
            self.logger.error("PostgreSQL connection not available")
            return None
        
        try:
            import psycopg2.extras
            
            # Determine primary key column name based on table
            pk_column = self._get_primary_key_column(table_name)
            
            with self.pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                query = f'SELECT * FROM {table_name} WHERE {pk_column} = %s'
                cursor.execute(query, (document_id,))
                row = cursor.fetchone()
                
                if row:
                    # Convert RealDictRow to regular dict
                    data = dict(row)
                    self.logger.info("Read data from PostgreSQL", extra={
                        "table": table_name,
                        "document_id": document_id,
                        "columns": list(data.keys())
                    })
                    return data
                else:
                    self.logger.warning("Document not found in PostgreSQL", extra={
                        "table": table_name,
                        "document_id": document_id
                    })
                    return None
                    
        except Exception as e:
            self.logger.exception("Error reading from PostgreSQL", extra={
                "table": table_name,
                "document_id": document_id,
                "error": str(e)
            })
            return None
    
    def _get_primary_key_column(self, table_name: str) -> str:
        """
        Get primary key column name for a table.
        
        Args:
            table_name: Table name
            
        Returns:
            Primary key column name
        """
        # Map table names to their primary key columns
        pk_mapping = {
            "read_model_media_search": "media_id",
            "read_model_post_search": "post_id",
            "read_model_user_search": "user_id",
            "read_model_face_search": "face_id",
            "read_model_recommendations_knn": "user_id",
            "read_model_feed_personalized": "user_id",
            "read_model_known_faces": "face_id"
        }
        return pk_mapping.get(table_name, "id")
    
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


def map_postgresql_to_elasticsearch(table_name: str, pg_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map PostgreSQL read model data to Elasticsearch document format.
    
    Args:
        table_name: PostgreSQL table name
        pg_data: Data from PostgreSQL
        
    Returns:
        Elasticsearch document format
    """
    es_doc = {}
    
    # Common mappings for all tables
    for key, value in pg_data.items():
        # Convert snake_case to camelCase for ES
        es_key = _snake_to_camel(key)
        
        # Handle array fields (PostgreSQL arrays)
        if isinstance(value, list):
            es_doc[es_key] = value
        # Handle timestamp fields - convert to ISO8601 (Elasticsearch expects RFC 3339)
        elif key in {"created_at", "updated_at", "last_modified_at", "processed_at"} and value:
            es_doc[es_key] = _normalize_timestamp(value)
        # Handle JSON string fields
        elif isinstance(value, str) and (key.endswith("_embedding") or "embedding" in key.lower()):
            # Try to parse as JSON array
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    es_doc[es_key] = parsed
                else:
                    es_doc[es_key] = value
            except (json.JSONDecodeError, TypeError):
                es_doc[es_key] = value
        # Handle boolean fields
        elif isinstance(value, bool):
            es_doc[es_key] = value
        # Handle numeric fields
        elif isinstance(value, (int, float)):
            es_doc[es_key] = value
        # Handle None/null
        elif value is None:
            es_doc[es_key] = None
        # Default: keep as string
        else:
            es_doc[es_key] = str(value) if value is not None else None
    
    return es_doc


def _snake_to_camel(snake_str: str) -> str:
    """Convert snake_case to camelCase."""
    components = snake_str.split('_')
    return components[0] + ''.join(x.capitalize() for x in components[1:])


def _normalize_timestamp(raw_value: Any) -> Optional[str]:
    """
    Normalize timestamp values returned from PostgreSQL to ISO8601 (UTC) format.
    Handles both datetime objects and timestamp strings.

    Args:
        raw_value: Timestamp (datetime object or string like '2025-11-11 15:24:00.955427+00:00')

    Returns:
        ISO8601 string or original value if parsing fails.
    """
    if not raw_value:
        return raw_value

    # If it's already a datetime object (from psycopg2), convert directly
    if isinstance(raw_value, datetime.datetime):
        if raw_value.tzinfo is None:
            raw_value = raw_value.replace(tzinfo=datetime.timezone.utc)
        return raw_value.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

    # If it's a string, parse it
    if isinstance(raw_value, str):
        # Attempt to parse common Postgres timestamp formats
        for fmt in ("%Y-%m-%d %H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.datetime.strptime(raw_value, fmt)
                # Ensure timezone aware; assume UTC if missing tz info
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                return dt.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
            except ValueError:
                continue

        # Fallback to fromisoformat (handles 'YYYY-MM-DDTHH:MM:SS' variants)
        try:
            dt = datetime.datetime.fromisoformat(raw_value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            pass

    LOGGER.warning("Failed to normalize timestamp, returning raw value", extra={"value": raw_value, "type": type(raw_value).__name__})
    return str(raw_value) if raw_value is not None else None


def handle_message(message_id: str, data: dict, sync_handler: ElasticsearchSyncHandler):
    """
    Handle ES sync message - reads from PostgreSQL read model tables.
    
    Args:
        message_id: Redis Stream message ID
        data: Message data
        sync_handler: ElasticsearchSyncHandler instance
    """
    try:
        # Decode message data
        decoded_data = decode_message(data)
        
        operation = decoded_data.get("operation", "index")  # index or delete
        index_type = decoded_data.get("indexType")  # Which read model (e.g., "media_search")
        document_id = decoded_data.get("documentId")
        
        LOGGER.info("Received sync message", extra={
            "message_id": message_id,
            "operation": operation,
            "index_type": index_type,
            "document_id": document_id
        })
        
        if not index_type or not document_id:
            LOGGER.error("Invalid message format - missing indexType or documentId", extra={"data": decoded_data})
            return
        
        # Get table name and ES index name
        mapping = INDEX_MAPPING.get(index_type)
        if not mapping:
            LOGGER.error(f"Unknown index type: {index_type}", extra={"available_types": list(INDEX_MAPPING.keys())})
            return
        
        table_name, es_index_name = mapping
        
        # Handle operation
        if operation == "delete":
            success = sync_handler.delete_document(es_index_name, document_id)
        else:
            # Read data from PostgreSQL read model table
            pg_data = sync_handler.read_from_postgresql(table_name, document_id)
            
            if not pg_data:
                LOGGER.error("Failed to read data from PostgreSQL", extra={
                    "table": table_name,
                    "document_id": document_id
                })
                return
            
            # Map PostgreSQL data to Elasticsearch format
            es_document = map_postgresql_to_elasticsearch(table_name, pg_data)
            
            # Parse vector fields if present
            for field in ["embedding", "imageEmbedding", "textEmbedding", "faceEmbedding"]:
                if field in es_document:
                    es_document[field] = parse_vector_field(es_document[field])
            
            # Sync to Elasticsearch
            success = sync_handler.sync_document(es_index_name, document_id, es_document)
        
        if success:
            LOGGER.info("Sync completed successfully", extra={
                "index": es_index_name,
                "document_id": document_id,
                "operation": operation,
                "table": table_name
            })
        else:
            LOGGER.error("Sync failed", extra={
                "index": es_index_name,
                "document_id": document_id,
                "operation": operation,
                "table": table_name
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

