"""
Liked Songs Storage Module
Handles persistent storage of user liked songs using JSON file storage.
"""

import json
import logging
import os
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger('discord.music.liked')

# Storage file path
LIKED_SONGS_FILE = 'data/liked_songs.json'


class LikedSongsStorage:
    """
    Manages persistent storage of user liked songs.
    Uses JSON file storage for simplicity and reliability.
    """
    
    def __init__(self):
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = asyncio.Lock()
        self._ensure_data_dir()
    
    def _ensure_data_dir(self):
        """Ensure the data directory exists"""
        data_dir = os.path.dirname(LIKED_SONGS_FILE)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
            logger.info(f"Created data directory: {data_dir}")
    
    async def load(self):
        """Load liked songs from file"""
        try:
            if os.path.exists(LIKED_SONGS_FILE):
                with open(LIKED_SONGS_FILE, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
                logger.info(f"Loaded liked songs for {len(self._data)} users")
            else:
                self._data = {}
                logger.info("No liked songs file found, starting fresh")
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted liked songs file: {e}")
            self._data = {}
        except Exception as e:
            logger.error(f"Error loading liked songs: {e}")
            self._data = {}
    
    async def save(self):
        """Save liked songs to file"""
        try:
            with open(LIKED_SONGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved liked songs for {len(self._data)} users")
        except Exception as e:
            logger.error(f"Error saving liked songs: {e}")
            raise
    
    def _get_user_key(self, user_id: int) -> str:
        """Get the storage key for a user"""
        return str(user_id)
    
    async def add_song(self, user_id: int, song: Dict[str, Any]) -> bool:
        """
        Add a song to user's liked songs.
        
        Args:
            user_id: The Discord user ID
            song: Song data dictionary with title, url, duration, thumbnail
            
        Returns:
            True if added, False if already exists
        """
        async with self._lock:
            user_key = self._get_user_key(user_id)
            
            if user_key not in self._data:
                self._data[user_key] = []
            
            # Check for duplicates by URL
            existing_songs = self._data[user_key]
            if any(s.get('url') == song.get('url') for s in existing_songs):
                logger.debug(f"Song already liked by user {user_id}: {song.get('title')}")
                return False
            
            # Add metadata
            song_copy = song.copy()
            song_copy['liked_at'] = datetime.utcnow().isoformat()
            song_copy['liked_by'] = user_id
            
            self._data[user_key].append(song_copy)
            await self.save()
            
            logger.info(f"Added '{song.get('title')}' to liked songs for user {user_id}")
            return True
    
    async def remove_song(self, user_id: int, url: str) -> bool:
        """
        Remove a song from user's liked songs by URL.
        
        Args:
            user_id: The Discord user ID
            url: The song URL to remove
            
        Returns:
            True if removed, False if not found
        """
        async with self._lock:
            user_key = self._get_user_key(user_id)
            
            if user_key not in self._data:
                return False
            
            original_count = len(self._data[user_key])
            self._data[user_key] = [
                s for s in self._data[user_key] 
                if s.get('url') != url
            ]
            
            if len(self._data[user_key]) < original_count:
                await self.save()
                logger.info(f"Removed song from liked songs for user {user_id}: {url}")
                return True
            
            return False
    
    async def get_liked_songs(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all liked songs for a user.
        
        Args:
            user_id: The Discord user ID
            
        Returns:
            List of liked song dictionaries
        """
        user_key = self._get_user_key(user_id)
        return self._data.get(user_key, [])
    
    async def is_liked(self, user_id: int, url: str) -> bool:
        """
        Check if a song is liked by a user.
        
        Args:
            user_id: The Discord user ID
            url: The song URL to check
            
        Returns:
            True if the song is in user's liked list
        """
        user_key = self._get_user_key(user_id)
        if user_key not in self._data:
            return False
        return any(s.get('url') == url for s in self._data[user_key])
    
    async def get_liked_count(self, user_id: int) -> int:
        """Get the count of liked songs for a user"""
        user_key = self._get_user_key(user_id)
        return len(self._data.get(user_key, []))
    
    async def clear_all(self, user_id: int) -> int:
        """
        Clear all liked songs for a user.
        
        Args:
            user_id: The Discord user ID
            
        Returns:
            Number of songs removed
        """
        async with self._lock:
            user_key = self._get_user_key(user_id)
            
            if user_key not in self._data:
                return 0
            
            count = len(self._data[user_key])
            del self._data[user_key]
            await self.save()
            
            logger.info(f"Cleared {count} liked songs for user {user_id}")
            return count


# Global storage instance
_liked_songs_storage: Optional[LikedSongsStorage] = None


async def init_liked_songs_storage() -> LikedSongsStorage:
    """Initialize the global liked songs storage"""
    global _liked_songs_storage
    _liked_songs_storage = LikedSongsStorage()
    await _liked_songs_storage.load()
    return _liked_songs_storage


def get_liked_songs_storage() -> LikedSongsStorage:
    """Get the global liked songs storage instance"""
    if _liked_songs_storage is None:
        raise RuntimeError("Liked songs storage not initialized. Call init_liked_songs_storage() first.")
    return _liked_songs_storage
