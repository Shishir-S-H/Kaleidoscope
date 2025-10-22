"""
Shared JSON Logger Utility for Kaleidoscope AI Services

Provides structured JSON logging for consistent observability across all microservices.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter that serializes log records into structured JSON.
    
    Includes standard fields (timestamp, level, message, logger name) and any extra
    contextual data passed via the 'extra' parameter.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as a JSON string.
        
        Args:
            record: The LogRecord instance to format
            
        Returns:
            JSON-formatted string representation of the log record
        """
        # Build the base log entry
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add source location info (useful for debugging)
        log_entry["source"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
        }
        
        # Add process/thread info (useful for concurrency debugging)
        log_entry["process"] = {
            "pid": record.process,
            "process_name": record.processName,
            "thread_id": record.thread,
            "thread_name": record.threadName,
        }
        
        # Include exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }
        
        # Add any extra contextual data passed via logger.info(..., extra={...})
        # Filter out standard LogRecord attributes to avoid duplicates
        standard_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName', 'levelname',
            'levelno', 'lineno', 'module', 'msecs', 'message', 'pathname', 'process',
            'processName', 'relativeCreated', 'thread', 'threadName', 'exc_info',
            'exc_text', 'stack_info', 'asctime', 'getMessage', 'extra'
        }
        
        extra_data = {}
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith('_'):
                extra_data[key] = value
        
        if extra_data:
            log_entry["extra"] = extra_data
        
        # Serialize to JSON
        try:
            return json.dumps(log_entry, default=str)
        except Exception as e:
            # Fallback: if JSON serialization fails, return a simple error message
            fallback = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "ERROR",
                "logger": "JSONFormatter",
                "message": f"Failed to serialize log record: {e}",
                "original_message": str(record.msg),
            }
            return json.dumps(fallback)


def get_logger(service_name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Get a configured logger instance with JSON formatting.
    
    Args:
        service_name: Name of the service (e.g., "content-moderation", "search-service")
        level: Logging level (default: logging.INFO)
        
    Returns:
        Configured logging.Logger instance
        
    Example:
        >>> logger = get_logger("content-moderation")
        >>> logger.info("Service started")
        >>> logger.info("Processing image", extra={"media_id": 1001, "url": "..."})
        >>> logger.error("Failed to process", extra={"media_id": 1001, "error": str(e)})
    """
    # Get logger instance
    logger = logging.getLogger(service_name)
    
    # Set logging level
    logger.setLevel(level)
    
    # Prevent duplicate handlers if logger already exists
    if logger.handlers:
        return logger
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Set JSON formatter
    json_formatter = JSONFormatter()
    console_handler.setFormatter(json_formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger (avoid duplicate logs)
    logger.propagate = False
    
    return logger
