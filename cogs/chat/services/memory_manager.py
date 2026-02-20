"""Memory management service for conversation context."""

import logging
from typing import Dict, Optional, List, Tuple

from ..models.memory import ChannelMemory, GuildMemory
from ..storage.memory_storage import MemoryStorage

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages conversation memory for channels and guilds."""
    
    def __init__(self, storage: MemoryStorage):
        """
        Initialize memory manager.
        
        Args:
            storage: Storage backend for persistence
        """
        self.storage = storage
        self._channel_cache: Dict[int, ChannelMemory] = {}
        self._guild_cache: Dict[int, GuildMemory] = {}
    
    async def get_or_create_channel_memory(self, channel_id: int) -> ChannelMemory:
        """
        Get or create channel memory.
        
        Args:
            channel_id: Discord channel ID
            
        Returns:
            ChannelMemory object
        """
        # Check cache first
        if channel_id in self._channel_cache:
            return self._channel_cache[channel_id]
        
        # Load from storage
        data = await self.storage.load_channel_memory(channel_id)
        if data:
            memory = self._dict_to_channel_memory(data)
        else:
            memory = ChannelMemory(channel_id=channel_id)
        
        # Cache it
        self._channel_cache[channel_id] = memory
        return memory
    
    async def get_or_create_guild_memory(self, guild_id: int) -> GuildMemory:
        """
        Get or create guild memory.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            GuildMemory object
        """
        # Check cache first
        if guild_id in self._guild_cache:
            return self._guild_cache[guild_id]
        
        # Load from storage
        data = await self.storage.load_guild_memory(guild_id)
        if data:
            memory = self._dict_to_guild_memory(data)
        else:
            memory = GuildMemory(guild_id=guild_id)
        
        # Cache it
        self._guild_cache[guild_id] = memory
        return memory
    
    async def add_to_channel_memory(
        self, 
        channel_id: int, 
        role: str, 
        content: str, 
        user_id: Optional[int] = None, 
        tokens: int = 0
    ) -> None:
        """Add message to channel memory."""
        memory = await self.get_or_create_channel_memory(channel_id)
        memory.add_message(role, content, user_id, tokens)
        
        # Save to storage
        await self.storage.save_channel_memory(channel_id, memory.to_dict())
    
    async def add_to_guild_memory(
        self, 
        guild_id: int, 
        role: str, 
        content: str, 
        user_id: Optional[int] = None, 
        tokens: int = 0
    ) -> None:
        """Add message to guild memory."""
        memory = await self.get_or_create_guild_memory(guild_id)
        memory.add_message(role, content, user_id, tokens)
        
        # Save to storage
        await self.storage.save_guild_memory(guild_id, memory.to_dict())
    
    async def get_channel_context(self, channel_id: int, limit: int = 10) -> str:
        """
        Get formatted context from channel memory.
        
        Args:
            channel_id: Discord channel ID
            limit: Number of messages to include
            
        Returns:
            Formatted context string for LLM
        """
        memory = await self.get_or_create_channel_memory(channel_id)
        messages = memory.get_context_messages(limit)
        
        if not messages:
            return ""
        
        context_lines = []
        for msg in messages:
            role = "User" if msg["role"] == "user" else "AI"
            content = msg["content"]
            context_lines.append(f"{role}: {content}")
        
        return "\n".join(context_lines)
    
    async def get_guild_context(self, guild_id: int, limit: int = 20) -> str:
        """
        Get formatted context from guild memory.
        
        Args:
            guild_id: Discord guild ID
            limit: Number of messages to include
            
        Returns:
            Formatted context string for LLM
        """
        memory = await self.get_or_create_guild_memory(guild_id)
        messages = memory.get_context_messages(limit)
        
        if not messages:
            return ""
        
        context_lines = []
        for msg in messages:
            role = "User" if msg["role"] == "user" else "AI"
            content = msg["content"]
            context_lines.append(f"{role}: {content}")
        
        return "\n".join(context_lines)
    
    async def clear_channel_memory(self, channel_id: int) -> None:
        """Clear all memory for a channel."""
        if channel_id in self._channel_cache:
            del self._channel_cache[channel_id]
        
        # Create empty memory and save it
        empty_memory = ChannelMemory(channel_id=channel_id)
        await self.storage.save_channel_memory(channel_id, empty_memory.to_dict())
    
    async def clear_guild_memory(self, guild_id: int) -> None:
        """Clear all memory for a guild."""
        if guild_id in self._guild_cache:
            del self._guild_cache[guild_id]
        
        # Create empty memory and save it
        empty_memory = GuildMemory(guild_id=guild_id)
        await self.storage.save_guild_memory(guild_id, empty_memory.to_dict())
    
    @staticmethod
    def _dict_to_channel_memory(data: Dict) -> ChannelMemory:
        """Convert dict from storage to ChannelMemory object."""
        memory = ChannelMemory(
            channel_id=data["channel_id"],
            messages=data.get("messages", []),
            total_messages=data.get("total_messages", 0),
            total_tokens=data.get("total_tokens", 0),
            created_at=data.get("created_at", 0),
            last_updated=data.get("last_updated", 0),
            metadata=data.get("metadata", {}),
        )
        return memory
    
    @staticmethod
    def _dict_to_guild_memory(data: Dict) -> GuildMemory:
        """Convert dict from storage to GuildMemory object."""
        memory = GuildMemory(
            guild_id=data["guild_id"],
            messages=data.get("messages", []),
            total_messages=data.get("total_messages", 0),
            total_tokens=data.get("total_tokens", 0),
            created_at=data.get("created_at", 0),
            last_updated=data.get("last_updated", 0),
            metadata=data.get("metadata", {}),
        )
        return memory
