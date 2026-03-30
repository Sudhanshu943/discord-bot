"""
Music Logic Module
Contains core music functionality: PlayerManager and SearchManager
"""

from .player_manager import PlayerManager, MusicPlayer, Song
from .search_manager import SearchManager, Platform

__all__ = [
    'PlayerManager',
    'MusicPlayer',
    'Song',
    'SearchManager',
    'Platform'
]
