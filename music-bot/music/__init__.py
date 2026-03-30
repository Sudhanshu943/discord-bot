"""
Music Cog Package
A modular music system for Discord bots using yt-dlp. 

No Lavalink required! Supports YouTube, Spotify, SoundCloud, and 1000+ platforms.

Structure:
- cog.py: Main cog with all commands
- ui.py: UI components (embeds, views, buttons)
- exceptions.py: Custom exceptions and error handling
- logic/: Core logic modules
  - player_manager.py: Player connection and state management
  - track_handler.py: Track operations and queue management
  - search_manager.py: Multi-platform search functionality
  - liked_songs.py: User liked songs storage
"""

from .cog import Music
from .logic.liked_songs import init_liked_songs_storage

__all__ = ['Music']


async def setup(bot):
    """
    Setup function to load the music cog
    This is called by the bot's extension loader
    """
    # Initialize liked songs storage
    await init_liked_songs_storage()
    await bot.add_cog(Music(bot))
