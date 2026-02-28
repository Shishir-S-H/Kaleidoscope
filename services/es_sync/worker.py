#!/usr/bin/env python3
"""
Elasticsearch Sync Service
Syncs data from PostgreSQL read models to Elasticsearch indices.
"""

import datetime
import json
import os
import re
import signal
import sys
import threading
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
from shared.utils.health_server import start_health_server, mark_ready

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

shutdown_event = threading.Event()


def _shutdown_handler(signum, frame):
    LOGGER.info("Shutdown signal received (signal %s)", signum)
    shutdown_event.set()


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
        
        # Initialize PostgreSQL connection pool
        self.pg_pool = None
        self._init_postgresql()
    
    def _init_postgresql(self):
        """Initialize PostgreSQL connection pool."""
        try:
            import psycopg2
            import psycopg2.pool
            
            self.pg_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=10,
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                connect_timeout=10,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5,
            )
            self.logger.info("PostgreSQL connection pool initialized", extra={
                "host": DB_HOST,
                "port": DB_PORT,
                "database": DB_NAME,
                "minconn": 2,
                "maxconn": 10,
            })
        except ImportError:
            self.logger.error("psycopg2 package not installed. Run: pip install psycopg2-binary")
            self.pg_pool = None
        except Exception as e:
            self.logger.error(f"Failed to create PostgreSQL connection pool: {e}", extra={
                "host": DB_HOST,
                "port": DB_PORT,
                "database": DB_NAME
            })
            self.pg_pool = None
    
    def _ensure_postgresql_connection(self) -> bool:
        """
        Ensure PostgreSQL connection pool is available, recreating it if needed.
        
        Returns:
            True if pool is available, False otherwise
        """
        if self.pg_pool is None or self.pg_pool.closed:
            self.logger.warning("PostgreSQL pool is unavailable, attempting to recreate...")
            self._init_postgresql()
            return self.pg_pool is not None and not self.pg_pool.closed

        # Validate the pool by borrowing and returning a connection
        conn = None
        try:
            conn = self.pg_pool.getconn()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            return True
        except Exception as e:
            self.logger.warning("PostgreSQL pool health-check failed: %s. Recreating pool...", e)
            try:
                self.pg_pool.closeall()
            except Exception:
                pass
            self._init_postgresql()
            return self.pg_pool is not None and not self.pg_pool.closed
        finally:
            if conn is not None and self.pg_pool is not None:
                try:
                    self.pg_pool.putconn(conn)
                except Exception:
                    pass
    
    def read_from_postgresql(self, table_name: str, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Read data from PostgreSQL read model table.
        Automatically handles connection health checking and reconnection.
        
        Args:
            table_name: Name of the read model table
            document_id: Document ID (primary key value)
            
        Returns:
            Dictionary with row data or None if not found
        """
        import psycopg2
        import psycopg2.extras
        
        if not self._ensure_postgresql_connection():
            self.logger.error("PostgreSQL connection pool not available after reconnection attempt")
            return None

        conn = None
        try:
            conn = self.pg_pool.getconn()

            pk_column = self._get_primary_key_column(table_name)
            
            if table_name == "read_model_face_search" and pk_column == "face_id":
                query = f'SELECT * FROM {table_name} WHERE {pk_column} = %s::text'
            else:
                query = f'SELECT * FROM {table_name} WHERE {pk_column} = %s'
            
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (document_id,))
                row = cursor.fetchone()
                
                if row:
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
                    
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            self.logger.warning(
                "Connection error during read, attempting retry: %s", e,
                extra={"table": table_name, "document_id": document_id, "error_type": type(e).__name__},
            )
            # Put back the broken connection (mark as failed) and retry once
            if conn is not None:
                try:
                    self.pg_pool.putconn(conn, close=True)
                except Exception:
                    pass
                conn = None

            if self._ensure_postgresql_connection():
                retry_conn = None
                try:
                    retry_conn = self.pg_pool.getconn()
                    pk_column = self._get_primary_key_column(table_name)
                    if table_name == "read_model_face_search" and pk_column == "face_id":
                        query = f'SELECT * FROM {table_name} WHERE {pk_column} = %s::text'
                    else:
                        query = f'SELECT * FROM {table_name} WHERE {pk_column} = %s'
                    with retry_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                        cursor.execute(query, (document_id,))
                        row = cursor.fetchone()
                        if row:
                            data = dict(row)
                            self.logger.info("Read data from PostgreSQL (after reconnection)", extra={
                                "table": table_name,
                                "document_id": document_id,
                                "columns": list(data.keys())
                            })
                            return data
                        else:
                            self.logger.warning("Document not found in PostgreSQL (after reconnection)", extra={
                                "table": table_name,
                                "document_id": document_id
                            })
                            return None
                except Exception as retry_error:
                    self.logger.error("Error reading from PostgreSQL after reconnection: %s", retry_error, extra={
                        "table": table_name,
                        "document_id": document_id
                    })
                    return None
                finally:
                    if retry_conn is not None:
                        try:
                            self.pg_pool.putconn(retry_conn)
                        except Exception:
                            pass
            else:
                self.logger.error("Failed to reconnect to PostgreSQL", extra={
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
        finally:
            if conn is not None:
                try:
                    self.pg_pool.putconn(conn)
                except Exception:
                    pass
    
    def _get_primary_key_column(self, table_name: str) -> str:
        """
        Get primary key column name for a table.
        
        Args:
            table_name: Table name
            
        Returns:
            Primary key column name
        """
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
    
    def sync_batch(self, actions: list) -> bool:
        """Sync a batch of documents using the Elasticsearch _bulk API.

        Args:
            actions: List of dicts, each with keys 'index', 'id', 'doc' (for index)
                     or 'index', 'id', 'op' = 'delete' (for delete).

        Returns:
            True if the entire batch succeeded, False otherwise.
        """
        if not self.es_client or not actions:
            return False

        from elasticsearch.helpers import bulk as es_bulk

        bulk_actions = []
        for action in actions:
            if action.get("op") == "delete":
                bulk_actions.append({
                    "_op_type": "delete",
                    "_index": action["index"],
                    "_id": action["id"],
                })
            else:
                bulk_actions.append({
                    "_op_type": "index",
                    "_index": action["index"],
                    "_id": action["id"],
                    "_source": action["doc"],
                })

        try:
            success_count, errors = es_bulk(
                self.es_client, bulk_actions, raise_on_error=False,
            )
            if errors:
                self.logger.warning(
                    "Bulk sync completed with errors",
                    extra={"success": success_count, "errors": len(errors)},
                )
                return False
            self.logger.info("Bulk sync completed", extra={"count": success_count})
            return True
        except Exception as exc:
            self.logger.error("Bulk sync failed: %s — falling back to single-doc mode", exc)
            ok = True
            for action in actions:
                if action.get("op") == "delete":
                    ok = self.delete_document(action["index"], action["id"]) and ok
                else:
                    ok = self.sync_document(action["index"], action["id"], action["doc"]) and ok
            return ok

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
            
            if retry_count < MAX_RETRIES:
                delay = RETRY_DELAY_SECONDS * (2 ** retry_count)
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
            
            if retry_count < MAX_RETRIES:
                delay = RETRY_DELAY_SECONDS * (2 ** retry_count)
                self.logger.info(f"Retrying in {delay} seconds...", extra={
                    "retry_count": retry_count + 1,
                    "max_retries": MAX_RETRIES
                })
                time.sleep(delay)
                return self.delete_document(index_name, document_id, retry_count + 1)
            
            return False

    def close(self):
        """Close the PostgreSQL pool and Elasticsearch client."""
        if self.pg_pool is not None:
            try:
                self.pg_pool.closeall()
                self.logger.info("PostgreSQL connection pool closed")
            except Exception as e:
                self.logger.error("Error closing PostgreSQL pool: %s", e)
        if self.es_client is not None:
            try:
                self.es_client.close()
                self.logger.info("Elasticsearch client closed")
            except Exception as e:
                self.logger.error("Error closing Elasticsearch client: %s", e)


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
    
    for key, value in pg_data.items():
        es_key = _snake_to_camel(key)
        
        if isinstance(value, list):
            es_doc[es_key] = value
        elif key == "bbox" and value is not None:
            if isinstance(value, list):
                es_doc[es_key] = [int(x) for x in value if x is not None]
            elif isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        es_doc[es_key] = [int(x) for x in parsed if x is not None]
                    else:
                        es_doc[es_key] = value
                except (json.JSONDecodeError, TypeError, ValueError):
                    es_doc[es_key] = value
            else:
                es_doc[es_key] = value
        elif key in {"created_at", "updated_at", "last_modified_at", "processed_at"} and value:
            es_doc[es_key] = _normalize_timestamp(value)
        elif isinstance(value, str) and (key.endswith("_embedding") or "embedding" in key.lower()):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    es_doc[es_key] = parsed
                else:
                    es_doc[es_key] = value
            except (json.JSONDecodeError, TypeError):
                es_doc[es_key] = value
        elif isinstance(value, bool):
            es_doc[es_key] = value
        elif isinstance(value, (int, float)):
            es_doc[es_key] = value
        elif value is None:
            es_doc[es_key] = None
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
    
    Elasticsearch expects format: uuuu-MM-dd'T'HH:mm:ss.SSSSSS (without Z suffix)

    Args:
        raw_value: Timestamp (datetime object or string like '2025-11-11 15:24:00.955427+00:00')

    Returns:
        ISO8601 string in format YYYY-MM-DDTHH:mm:ss.SSSSSS (without Z) or original value if parsing fails.
    """
    if not raw_value:
        return raw_value

    if isinstance(raw_value, datetime.datetime):
        if raw_value.tzinfo is None:
            raw_value = raw_value.replace(tzinfo=datetime.timezone.utc)
        utc_dt = raw_value.astimezone(datetime.timezone.utc)
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")

    if isinstance(raw_value, str):
        if raw_value.endswith('Z'):
            raw_value = raw_value[:-1] + '+00:00'
        
        for fmt in ("%Y-%m-%d %H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.datetime.strptime(raw_value, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                utc_dt = dt.astimezone(datetime.timezone.utc)
                return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")
            except ValueError:
                continue

        try:
            dt = datetime.datetime.fromisoformat(raw_value.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            utc_dt = dt.astimezone(datetime.timezone.utc)
            return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")
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
        decoded_data = decode_message(data)
        
        operation = decoded_data.get("operation", "index")
        index_type = decoded_data.get("indexType")
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
        
        mapping = INDEX_MAPPING.get(index_type)
        if not mapping:
            LOGGER.error(f"Unknown index type: {index_type}", extra={"available_types": list(INDEX_MAPPING.keys())})
            return
        
        table_name, es_index_name = mapping
        
        if operation == "delete":
            success = sync_handler.delete_document(es_index_name, document_id)
        else:
            pg_data = sync_handler.read_from_postgresql(table_name, document_id)
            
            if not pg_data:
                LOGGER.error("Failed to read data from PostgreSQL", extra={
                    "table": table_name,
                    "document_id": document_id
                })
                return
            
            es_document = map_postgresql_to_elasticsearch(table_name, pg_data)
            
            for field in ["embedding", "imageEmbedding", "textEmbedding", "faceEmbedding"]:
                if field in es_document:
                    es_document[field] = parse_vector_field(es_document[field])
            
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

    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    consumer = None
    sync_handler = None

    try:
        sync_handler = ElasticsearchSyncHandler(ES_HOST)
        consumer = RedisStreamConsumer(
            REDIS_URL,
            STREAM_INPUT,
            CONSUMER_GROUP,
            CONSUMER_NAME,
            shutdown_event=shutdown_event,
        )
        
        LOGGER.info("Connected to Redis Streams", extra={
            "input_stream": STREAM_INPUT,
            "consumer_group": CONSUMER_GROUP
        })

        BATCH_SIZE = int(os.getenv("ES_SYNC_BATCH_SIZE", "50"))
        BATCH_TIMEOUT = float(os.getenv("ES_SYNC_BATCH_TIMEOUT", "2.0"))
        batch_actions: list = []
        batch_start = time.time()

        start_health_server(
            service_name="es-sync",
            health_fn=lambda: {"status": "healthy", "service": "es-sync"},
        )
        mark_ready()
        
        def _flush_batch():
            nonlocal batch_actions, batch_start
            if not batch_actions:
                return
            LOGGER.info("Flushing batch", extra={"size": len(batch_actions)})
            sync_handler.sync_batch(batch_actions)
            batch_actions = []
            batch_start = time.time()

        def message_handler(message_id: str, data: dict):
            nonlocal batch_start
            decoded_data = decode_message(data)

            operation = decoded_data.get("operation", "index")
            index_type = decoded_data.get("indexType")
            document_id = decoded_data.get("documentId")

            if not index_type or not document_id:
                LOGGER.error("Invalid message format — missing indexType or documentId", extra={"data": decoded_data})
                return

            mapping = INDEX_MAPPING.get(index_type)
            if not mapping:
                LOGGER.error("Unknown index type: %s", index_type, extra={"available_types": list(INDEX_MAPPING.keys())})
                return

            table_name, es_index_name = mapping

            if operation == "delete":
                batch_actions.append({"index": es_index_name, "id": document_id, "op": "delete"})
            else:
                pg_data = sync_handler.read_from_postgresql(table_name, document_id)
                if not pg_data:
                    LOGGER.error("Failed to read data from PostgreSQL", extra={"table": table_name, "document_id": document_id})
                    return

                es_document = map_postgresql_to_elasticsearch(table_name, pg_data)
                for field in ["embedding", "imageEmbedding", "textEmbedding", "faceEmbedding"]:
                    if field in es_document:
                        es_document[field] = parse_vector_field(es_document[field])

                batch_actions.append({"index": es_index_name, "id": document_id, "doc": es_document})

            if len(batch_actions) >= BATCH_SIZE:
                _flush_batch()
            elif time.time() - batch_start >= BATCH_TIMEOUT and batch_actions:
                _flush_batch()

        LOGGER.info("Worker ready — waiting for sync requests (batch_size=%d, batch_timeout=%.1fs)", BATCH_SIZE, BATCH_TIMEOUT)
        
        consumer.consume(message_handler, block_ms=int(BATCH_TIMEOUT * 1000), count=BATCH_SIZE)
        
    except KeyboardInterrupt:
        LOGGER.warning("Interrupted by user")
    except Exception as e:
        LOGGER.exception("Unexpected error in main loop", extra={"error": str(e)})
    finally:
        shutdown_event.set()
        # Flush remaining batch before shutting down
        if batch_actions and sync_handler:
            LOGGER.info("Flushing remaining batch on shutdown", extra={"size": len(batch_actions)})
            try:
                sync_handler.sync_batch(batch_actions)
            except Exception as flush_err:
                LOGGER.error("Failed to flush final batch: %s", flush_err)
        if consumer:
            consumer.close()
        if sync_handler:
            sync_handler.close()
        LOGGER.info("Worker shut down complete")


if __name__ == "__main__":
    main()
