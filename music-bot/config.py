"""
Music Bot Configuration
=======================

Configuration settings for the standalone music bot.
This module imports centralized constants from music/constants.py
"""

import os
from dotenv import load_dotenv

# Import centralized constants from music module
from music import constants

load_dotenv()


class MusicBotConfig:
    """Configuration for the music bot"""
    
    # Bot settings
    COMMAND_PREFIX = constants.COMMAND_PREFIX
    MAX_QUEUE_SIZE = constants.LIMITS['MAX_QUEUE_SIZE']
    DEFAULT_VOLUME = constants.LIMITS['DEFAULT_VOLUME']
    LOG_LEVEL = constants.LOG_LEVEL
    LOG_FILE = constants.LOG_FILE
    
    # Voice settings
    SELF_DEAF = constants.VOICE_SETTINGS['SELF_DEAF']
    SELF_MUTE = constants.VOICE_SETTINGS['SELF_MUTE']
    
    # Playback settings
    FFMPEG_OPTIONS = constants.FFMPEG_OPTS
    
    # YouTube settings
    YDL_OPTIONS = constants.YDL_OPTS
    YDL_EXTRACTOR_ARGS = constants.YDL_EXTRACTOR_ARGS
    
    # Cookie file path
    COOKIE_FILE = constants.COOKIE_FILE
    
    # Proxy configuration for anti-bot detection
    PROXY_URL = constants.PROXY_URL
    USE_PROXY = constants.USE_PROXY
    PROXY_ROTATION_ENABLED = constants.PROXY_ROTATION_ENABLED
    
    # Speed optimization - Use timeouts from constants
    SEARCH_TIMEOUT = constants.TIMEOUTS['SEARCH']
    EXTRACTION_TIMEOUT = constants.TIMEOUTS['AUDIO_EXTRACTION']
    VOICE_CONNECT_TIMEOUT = constants.TIMEOUTS['VOICE_CONNECT']
    
    # Idle timeout (seconds)
    IDLE_TIMEOUT = constants.LIMITS['AUTO_DISCONNECT_IDLE']
    
    @classmethod
    def get_discord_token(cls) -> str:
        """Get Discord bot token from environment"""
        token = os.getenv('DISCORD_TOKEN')
        if not token:
            raise ValueError("DISCORD_TOKEN not found in environment variables")
        return token
    
    @classmethod
    def get_cookie_url(cls) -> str:
        """Get YouTube cookie URL from environment"""
        return os.getenv('YOUTUBE_COOKIE_URL', '')
    
    @classmethod
    def get_proxy_url(cls) -> str:
        """Get proxy URL for anti-bot detection"""
        return cls.PROXY_URL
    
    @classmethod
    def validate(cls):
        """Validate configuration"""
        try:
            cls.get_discord_token()
            if cls.USE_PROXY:
                print(f"✓ Proxy enabled: {cls.PROXY_URL[:20]}...")
            return True
        except ValueError:
            return False
