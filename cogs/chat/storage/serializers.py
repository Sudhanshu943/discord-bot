"""Serialization utilities for memory objects."""

from typing import Dict, Any
from datetime import datetime


def serialize_memory(memory_dict: Dict) -> Dict:
    """
    Serialize memory object for JSON storage.
    
    Converts datetime objects to ISO format strings.
    
    Args:
        memory_dict: Memory dictionary to serialize
        
    Returns:
        Serialized dictionary safe for JSON
    """
    serialized = memory_dict.copy()
    
    if "created_at" in serialized and isinstance(serialized["created_at"], datetime):
        serialized["created_at"] = serialized["created_at"].isoformat()
    
    if "last_updated" in serialized and isinstance(serialized["last_updated"], datetime):
        serialized["last_updated"] = serialized["last_updated"].isoformat()
    
    return serialized


def deserialize_memory(memory_dict: Dict) -> Dict:
    """
    Deserialize memory object from JSON storage.
    
    Converts ISO format timestamp strings back to datetime objects.
    
    Args:
        memory_dict: Deserialized dictionary from JSON
        
    Returns:
        Memory dictionary with proper types
    """
    deserialized = memory_dict.copy()
    
    if "created_at" in deserialized and isinstance(deserialized["created_at"], str):
        try:
            deserialized["created_at"] = datetime.fromisoformat(deserialized["created_at"])
        except (ValueError, TypeError):
            pass
    
    if "last_updated" in deserialized and isinstance(deserialized["last_updated"], str):
        try:
            deserialized["last_updated"] = datetime.fromisoformat(deserialized["last_updated"])
        except (ValueError, TypeError):
            pass
    
    return deserialized
