"""JSON-based persistent storage for conversation memories."""

import json
import os
import asyncio
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class MemoryStorage:
    """Handles persistent storage of conversation memories using JSON files."""
    
    def __init__(self, storage_dir: str = "data/chat_memory"):
        """
        Initialize storage with a directory path.
        
        Args:
            storage_dir: Directory to store JSON memory files
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.channels_file = self.storage_dir / "channels.json"
        self.guilds_file = self.storage_dir / "guilds.json"
        
        # Create files if they don't exist
        self._ensure_files_exist()
    
    def _ensure_files_exist(self) -> None:
        """Create JSON files if they don't exist."""
        for file_path in [self.channels_file, self.guilds_file]:
            if not file_path.exists():
                with open(file_path, "w") as f:
                    json.dump({}, f)
    
    def _load_all_channel_memories(self) -> Dict[int, Dict]:
        """Load all channel memories from disk."""
        try:
            with open(self.channels_file, "r") as f:
                data = json.load(f)
                # Convert string keys back to int
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            logger.error(f"Failed to load channel memories: {e}")
            return {}
    
    def _load_all_guild_memories(self) -> Dict[int, Dict]:
        """Load all guild memories from disk."""
        try:
            with open(self.guilds_file, "r") as f:
                data = json.load(f)
                # Convert string keys back to int
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            logger.error(f"Failed to load guild memories: {e}")
            return {}
    
    async def load_channel_memory(self, channel_id: int) -> Optional[Dict]:
        """
        Load channel memory from disk.
        
        Args:
            channel_id: Discord channel ID
            
        Returns:
            Channel memory dict or None if not found
        """
        memories = self._load_all_channel_memories()
        return memories.get(channel_id)
    
    async def load_guild_memory(self, guild_id: int) -> Optional[Dict]:
        """
        Load guild memory from disk.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Guild memory dict or None if not found
        """
        memories = self._load_all_guild_memories()
        return memories.get(guild_id)
    
    async def save_channel_memory(self, channel_id: int, memory: Dict) -> None:
        """
        Save channel memory to disk asynchronously.
        
        Args:
            channel_id: Discord channel ID
            memory: Memory dict to save
        """
        try:
            # Run file I/O in thread pool to avoid blocking
            await asyncio.get_event_loop().run_in_executor(
                None, 
                self._sync_save_channel_memory,
                channel_id,
                memory
            )
        except Exception as e:
            logger.error(f"Failed to save channel memory {channel_id}: {e}")
    
    def _sync_save_channel_memory(self, channel_id: int, memory: Dict) -> None:
        """Synchronous version of save for use in executor."""
        try:
            memories = self._load_all_channel_memories()
            memories[channel_id] = memory
            
            with open(self.channels_file, "w") as f:
                # Convert int keys to strings for JSON
                json_data = {str(k): v for k, v in memories.items()}
                json.dump(json_data, f, indent=2)
        except Exception as e:
            logger.error(f"Sync save failed for channel {channel_id}: {e}")
    
    async def save_guild_memory(self, guild_id: int, memory: Dict) -> None:
        """
        Save guild memory to disk asynchronously.
        
        Args:
            guild_id: Discord guild ID
            memory: Memory dict to save
        """
        try:
            # Run file I/O in thread pool to avoid blocking
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._sync_save_guild_memory,
                guild_id,
                memory
            )
        except Exception as e:
            logger.error(f"Failed to save guild memory {guild_id}: {e}")
    
    def _sync_save_guild_memory(self, guild_id: int, memory: Dict) -> None:
        """Synchronous version of save for use in executor."""
        try:
            memories = self._load_all_guild_memories()
            memories[guild_id] = memory
            
            with open(self.guilds_file, "w") as f:
                # Convert int keys to strings for JSON
                json_data = {str(k): v for k, v in memories.items()}
                json.dump(json_data, f, indent=2)
        except Exception as e:
            logger.error(f"Sync save failed for guild {guild_id}: {e}")
    
    async def cleanup_old_memories(self, days: int = 30) -> int:
        """
        Remove memories older than specified days.
        
        Args:
            days: Remove memories older than this many days
            
        Returns:
            Number of memories removed
        """
        try:
            cutoff_timestamp = (datetime.now() - timedelta(days=days)).timestamp()
            removed_count = 0
            
            # Cleanup channel memories
            channel_memories = self._load_all_channel_memories()
            for channel_id, memory in list(channel_memories.items()):
                if memory.get("last_updated", 0) < cutoff_timestamp:
                    del channel_memories[channel_id]
                    removed_count += 1
            
            # Save cleaned up channel memories
            with open(self.channels_file, "w") as f:
                json_data = {str(k): v for k, v in channel_memories.items()}
                json.dump(json_data, f, indent=2)
            
            # Cleanup guild memories
            guild_memories = self._load_all_guild_memories()
            for guild_id, memory in list(guild_memories.items()):
                if memory.get("last_updated", 0) < cutoff_timestamp:
                    del guild_memories[guild_id]
                    removed_count += 1
            
            # Save cleaned up guild memories
            with open(self.guilds_file, "w") as f:
                json_data = {str(k): v for k, v in guild_memories.items()}
                json.dump(json_data, f, indent=2)
            
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old memory records")
            
            return removed_count
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return 0
