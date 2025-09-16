"""
JSON Serialization Utilities - Handles numpy types and complex objects
Prevents FastAPI JSON serialization errors with numpy types
"""
import json
import numpy as np
from datetime import datetime, date
from typing import Any, Dict, List
import logging

logger = logging.getLogger(__name__)

class NumpyJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles numpy types and other complex objects"""

    def default(self, obj):
        # Handle numpy types
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            # Handle SQLAlchemy models and other objects with __dict__
            return {key: value for key, value in obj.__dict__.items()
                   if not key.startswith('_')}

        # Let the base class handle everything else
        return super().default(obj)

def sanitize_for_json(data: Any) -> Any:
    """
    Recursively sanitize data to be JSON serializable
    Converts numpy types, datetime objects, and SQLAlchemy models
    """
    if data is None:
        return None

    # Handle numpy types
    if isinstance(data, np.bool_):
        return bool(data)
    elif isinstance(data, np.integer):
        return int(data)
    elif isinstance(data, np.floating):
        return float(data)
    elif isinstance(data, np.ndarray):
        return data.tolist()

    # Handle datetime objects
    elif isinstance(data, (datetime, date)):
        return data.isoformat()

    # Handle dictionaries
    elif isinstance(data, dict):
        return {key: sanitize_for_json(value) for key, value in data.items()}

    # Handle lists and tuples
    elif isinstance(data, (list, tuple)):
        return [sanitize_for_json(item) for item in data]

    # Handle SQLAlchemy models (objects with __dict__)
    elif hasattr(data, '__dict__') and not isinstance(data, (str, int, float, bool)):
        try:
            return {key: sanitize_for_json(value)
                   for key, value in data.__dict__.items()
                   if not key.startswith('_')}
        except Exception as e:
            logger.warning(f"Could not serialize object {type(data)}: {e}")
            return str(data)

    # Return as-is for basic types
    return data

def safe_json_response(data: Any) -> Dict[str, Any]:
    """
    Create a safe JSON response dictionary with sanitized data
    Used by FastAPI endpoints to prevent serialization errors
    """
    try:
        sanitized = sanitize_for_json(data)

        # Test serialization to catch any remaining issues
        json.dumps(sanitized, cls=NumpyJSONEncoder)

        return sanitized

    except Exception as e:
        logger.error(f"JSON serialization failed: {e}")

        # Return safe fallback
        return {
            'error': 'serialization_failed',
            'message': str(e),
            'data_type': str(type(data).__name__),
            'safe_data': str(data)[:500] if data else None
        }

def validate_json_serializable(data: Any) -> bool:
    """
    Check if data is JSON serializable without raising exceptions
    """
    try:
        json.dumps(sanitize_for_json(data), cls=NumpyJSONEncoder)
        return True
    except Exception:
        return False