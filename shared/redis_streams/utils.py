"""Utility functions for Redis Streams."""

import json
from typing import Dict, Any


def encode_message(data: Dict[str, Any]) -> Dict[str, str]:
    """
    Encode a message dictionary for Redis Streams.
    Converts complex types (lists, dicts) to JSON strings.
    
    Args:
        data: Dictionary of data to encode
    
    Returns:
        Dictionary with all values as strings
    """
    encoded = {}
    for key, value in data.items():
        if isinstance(value, (list, dict)):
            encoded[key] = json.dumps(value)
        elif isinstance(value, bool):
            encoded[key] = "true" if value else "false"
        elif value is None:
            encoded[key] = ""
        else:
            encoded[key] = str(value)
    return encoded


def decode_message(data: Dict[bytes, bytes]) -> Dict[str, Any]:
    """
    Decode a message from Redis Streams.
    Attempts to parse JSON strings back to objects.
    
    Args:
        data: Dictionary with bytes keys and values from Redis
    
    Returns:
        Dictionary with decoded values
    """
    decoded = {}
    for key, value in data.items():
        # Decode bytes to string
        key_str = key.decode('utf-8') if isinstance(key, bytes) else key
        value_str = value.decode('utf-8') if isinstance(value, bytes) else value
        
        # Try to parse as JSON
        try:
            decoded[key_str] = json.loads(value_str)
        except (json.JSONDecodeError, ValueError):
            # Not JSON, keep as string
            decoded[key_str] = value_str
    
    return decoded

