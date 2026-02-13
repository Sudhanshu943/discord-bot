"""
Conversation Context Manager for Chat Module
============================================

Manages conversation history and context for users with optional persistence.
"""

import json
import time
import asyncio
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
import logging

from .exceptions import ContextException

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Represents a single message in the conversation."""
    role: str  # 'user', 'assistant', or 'system'
    content: str
    timestamp: float = field(default_factory=time.time)
    provider: Optional[str] = None  # Which provider generated this response
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "provider": self.provider
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Message':
        """Create from dictionary."""
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", time.time()),
            provider=data.get("provider")
        )
    
    def to_api_format(self) -> Dict[str, str]:
        """Convert to API format for LLM providers."""
        return {"role": self.role, "content": self.content}


@dataclass
class Conversation:
    """Represents a user's conversation history."""
    user_id: int
    messages: List[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    total_messages: int = 0
    preferred_provider: Optional[str] = None
    
    def add_message(self, role: str, content: str, provider: str = None) -> Message:
        """Add a message to the conversation."""
        message = Message(
            role=role,
            content=content,
            provider=provider
        )
        self.messages.append(message)
        self.last_activity = time.time()
        self.total_messages += 1
        return message
    
    def get_api_messages(self, system_prompt: str) -> List[Dict]:
        """Get messages in API format."""
        api_messages = [{"role": "system", "content": system_prompt}]
        api_messages.extend(msg.to_api_format() for msg in self.messages)
        return api_messages
    
    def clear(self) -> None:
        """Clear conversation history."""
        self.messages.clear()
        self.last_activity = time.time()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "user_id": self.user_id,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "total_messages": self.total_messages,
            "preferred_provider": self.preferred_provider
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Conversation':
        """Create from dictionary."""
        conv = cls(
            user_id=data["user_id"],
            messages=[Message.from_dict(m) for m in data.get("messages", [])],
            created_at=data.get("created_at", time.time()),
            last_activity=data.get("last_activity", time.time()),
            total_messages=data.get("total_messages", 0),
            preferred_provider=data.get("preferred_provider")
        )
        return conv


class ConversationManager:
    """
    Manages conversation contexts for all users.
    
    Features:
    - In-memory storage with optional persistence
    - Automatic cleanup of old conversations
    - Thread-safe operations
    - History size limits
    """
    
    DEFAULT_PERSISTENCE_PATH = "data/conversations.json"
    
    def __init__(
        self,
        max_history: int = 20,
        conversation_timeout_hours: int = 24,
        persist: bool = True,
        persistence_path: str = None
    ):
        """
        Initialize the conversation manager.
        
        Args:
            max_history: Maximum messages to keep per conversation
            conversation_timeout_hours: Hours before conversation expires
            persist: Whether to persist conversations to disk
            persistence_path: Path for persistence file
        """
        self.max_history = max_history
        self.conversation_timeout_hours = conversation_timeout_hours
        self.persist = persist
        self.persistence_path = persistence_path or self.DEFAULT_PERSISTENCE_PATH
        
        # In-memory storage
        self._conversations: Dict[int, Conversation] = {}
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Statistics
        self._stats = {
            "total_conversations": 0,
            "total_messages": 0,
            "persistences": 0,
            "cleanups": 0
        }
        
        # Load persisted conversations
        if self.persist:
            self._load_from_disk()
        
        logger.info(
            f"ConversationManager initialized: max_history={max_history}, "
            f"timeout={conversation_timeout_hours}h, persist={persist}"
        )
    
    async def get_conversation(self, user_id: int) -> Conversation:
        """
        Get or create a conversation for a user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Conversation object
        """
        async with self._lock:
            if user_id not in self._conversations:
                self._conversations[user_id] = Conversation(user_id=user_id)
                self._stats["total_conversations"] += 1
                logger.debug(f"Created new conversation for user {user_id}")
            
            return self._conversations[user_id]
    
    async def add_message(
        self,
        user_id: int,
        role: str,
        content: str,
        provider: str = None
    ) -> Message:
        """Add a message to a user's conversation."""
        logger.info(f"📝 Adding {role} message for user {user_id}")  # ADD THIS

        async with self._lock:
            logger.info(f"🔒 Lock acquired for user {user_id}")  # ADD THIS
            conversation = await self.get_conversation(user_id)
            message = conversation.add_message(role, content, provider)

            # Trim history if needed
            if len(conversation.messages) > self.max_history:
                conversation.messages = conversation.messages[-self.max_history:]

            self._stats["total_messages"] += 1

            logger.info(f"💾 Persisting conversation for user {user_id}")  # ADD THIS
            # Persist if enabled
            if self.persist:
                await self._save_to_disk()

            logger.info(f"✅ Message added successfully for user {user_id}")  # ADD THIS
            return message

    
    async def clear_conversation(self, user_id: int) -> bool:
        """
        Clear a user's conversation history.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            True if conversation was cleared, False if not found
        """
        async with self._lock:
            if user_id in self._conversations:
                self._conversations[user_id].clear()
                logger.info(f"Cleared conversation for user {user_id}")
                
                if self.persist:
                    await self._save_to_disk()
                
                return True
            return False
    
    async def delete_conversation(self, user_id: int) -> bool:
        """
        Delete a user's conversation entirely.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            True if conversation was deleted, False if not found
        """
        async with self._lock:
            if user_id in self._conversations:
                del self._conversations[user_id]
                logger.info(f"Deleted conversation for user {user_id}")
                
                if self.persist:
                    await self._save_to_disk()
                
                return True
            return False
    
    async def get_api_messages(self, user_id: int, system_prompt: str) -> List[Dict]:
        """
        Get messages formatted for API calls.
        
        Args:
            user_id: Discord user ID
            system_prompt: System prompt to prepend
            
        Returns:
            List of message dictionaries
        """
        conversation = await self.get_conversation(user_id)
        return conversation.get_api_messages(system_prompt)
    
    async def set_preferred_provider(self, user_id: int, provider: str) -> None:
        """Set a user's preferred provider."""
        conversation = await self.get_conversation(user_id)
        conversation.preferred_provider = provider
        logger.info(f"User {user_id} set preferred provider to {provider}")
    
    async def cleanup_expired(self) -> int:
        """
        Remove expired conversations.
        
        Returns:
            Number of conversations removed
        """
        async with self._lock:
            current_time = time.time()
            timeout_seconds = self.conversation_timeout_hours * 3600
            
            expired_users = [
                user_id for user_id, conv in self._conversations.items()
                if current_time - conv.last_activity > timeout_seconds
            ]
            
            for user_id in expired_users:
                del self._conversations[user_id]
            
            if expired_users:
                self._stats["cleanups"] += 1
                logger.info(f"Cleaned up {len(expired_users)} expired conversations")
                
                if self.persist:
                    await self._save_to_disk()
            
            return len(expired_users)
    
    def get_stats(self) -> Dict:
        """Get conversation statistics."""
        return {
            **self._stats,
            "active_conversations": len(self._conversations),
            "max_history": self.max_history,
            "timeout_hours": self.conversation_timeout_hours
        }
    
    def get_user_stats(self, user_id: int) -> Optional[Dict]:
        """Get statistics for a specific user's conversation."""
        conv = self._conversations.get(user_id)
        if not conv:
            return None
        
        return {
            "message_count": len(conv.messages),
            "total_messages": conv.total_messages,
            "created_at": conv.created_at,
            "last_activity": conv.last_activity,
            "preferred_provider": conv.preferred_provider
        }
    
    def _load_from_disk(self) -> None:
        """Load conversations from disk."""
        try:
            path = Path(self.persistence_path)
            
            if not path.exists():
                logger.debug("No persistence file found, starting fresh")
                return
            
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._conversations = {
                int(user_id): Conversation.from_dict(conv_data)
                for user_id, conv_data in data.get("conversations", {}).items()
            }
            
            self._stats = data.get("stats", self._stats)
            
            logger.info(
                f"Loaded {len(self._conversations)} conversations from disk"
            )
            
        except Exception as e:
            logger.error(f"Failed to load conversations from disk: {e}")
    
    async def _save_to_disk(self) -> None:
        """Save conversations to disk."""
        logger.info("💾 Starting save to disk...")  # ADD THIS
        try:
            path = Path(self.persistence_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "conversations": {
                    str(user_id): conv.to_dict()
                    for user_id, conv in self._conversations.items()
                },
                "stats": self._stats
            }
            
            # Write to temp file first, then rename (atomic operation)
            temp_path = path.with_suffix('.tmp')
            
            logger.info(f"💾 Writing to {temp_path}")  # ADD THIS
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"💾 Renaming to {path}")  # ADD THIS
            temp_path.rename(path)
            self._stats["persistences"] += 1
            
            logger.info("✅ Save to disk complete")  # ADD THIS
            
        except Exception as e:
            logger.error(f"Failed to save conversations to disk: {e}")

    
    async def export_conversation(self, user_id: int) -> Optional[str]:
        """Export a conversation as JSON string."""
        conv = self._conversations.get(user_id)
        if not conv:
            return None
        
        return json.dumps(conv.to_dict(), indent=2)
    
    async def import_conversation(self, user_id: int, data: str) -> bool:
        """Import a conversation from JSON string."""
        try:
            conv_data = json.loads(data)
            conv = Conversation.from_dict(conv_data)
            conv.user_id = user_id  # Ensure correct user ID
            
            async with self._lock:
                self._conversations[user_id] = conv
            
            if self.persist:
                await self._save_to_disk()
            
            logger.info(f"Imported conversation for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to import conversation: {e}")
            return False
