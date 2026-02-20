"""Memory models for conversations."""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import time


@dataclass
class ConversationTurn:
    """Single turn in a conversation (message + response)."""
    
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    user_id: Optional[int] = None
    tokens: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "tokens": self.tokens,
            "metadata": self.metadata,
        }


@dataclass
class ChannelMemory:
    """Memory for a Discord channel."""
    
    channel_id: int
    messages: List[Dict] = field(default_factory=list)
    total_messages: int = 0
    total_tokens: int = 0
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Size limits
    MAX_MESSAGES: int = 100
    MAX_SIZE_BYTES: int = 100 * 1024  # 100 KB
    
    def add_message(self, role: str, content: str, user_id: Optional[int] = None, tokens: int = 0) -> None:
        """Add message to memory with size enforcement."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "user_id": user_id,
            "tokens": tokens,
            "metadata": {},
        }
        
        self.messages.append(msg)
        self.total_messages += 1
        self.total_tokens += tokens
        self.last_updated = time.time()
        
        # Enforce message limit
        while len(self.messages) > self.MAX_MESSAGES:
            removed = self.messages.pop(0)
            self.total_tokens -= removed.get("tokens", 0)
        
        # Enforce size limit (approximate)
        import json
        while len(json.dumps(self.messages).encode()) > self.MAX_SIZE_BYTES:
            removed = self.messages.pop(0)
            self.total_tokens -= removed.get("tokens", 0)
    
    def get_context_messages(self, limit: int = 10) -> List[Dict]:
        """Get recent messages for context."""
        return self.messages[-limit:] if self.messages else []
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            "channel_id": self.channel_id,
            "messages": self.messages,
            "total_messages": self.total_messages,
            "total_tokens": self.total_tokens,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "metadata": self.metadata,
        }


@dataclass
class GuildMemory:
    """Memory for a Discord guild (server-wide context)."""
    
    guild_id: int
    messages: List[Dict] = field(default_factory=list)
    total_messages: int = 0
    total_tokens: int = 0
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Size limits (larger for guild-wide context)
    MAX_MESSAGES: int = 200
    MAX_SIZE_BYTES: int = 500 * 1024  # 500 KB
    
    def add_message(self, role: str, content: str, user_id: Optional[int] = None, tokens: int = 0) -> None:
        """Add message to memory with size enforcement."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "user_id": user_id,
            "tokens": tokens,
            "metadata": {},
        }
        
        self.messages.append(msg)
        self.total_messages += 1
        self.total_tokens += tokens
        self.last_updated = time.time()
        
        # Enforce message limit
        while len(self.messages) > self.MAX_MESSAGES:
            removed = self.messages.pop(0)
            self.total_tokens -= removed.get("tokens", 0)
        
        # Enforce size limit (approximate)
        import json
        while len(json.dumps(self.messages).encode()) > self.MAX_SIZE_BYTES:
            removed = self.messages.pop(0)
            self.total_tokens -= removed.get("tokens", 0)
    
    def get_context_messages(self, limit: int = 20) -> List[Dict]:
        """Get recent messages for context."""
        return self.messages[-limit:] if self.messages else []
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            "guild_id": self.guild_id,
            "messages": self.messages,
            "total_messages": self.total_messages,
            "total_tokens": self.total_tokens,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "metadata": self.metadata,
        }
