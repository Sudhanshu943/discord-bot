"""
Music Bot Configuration
=======================

Configuration settings for the standalone music bot.
Support for proxy configuration for anti-bot detection.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class MusicBotConfig:
    """Configuration for the music bot"""
    
    # Bot settings
    COMMAND_PREFIX = '!'
    MAX_QUEUE_SIZE = 100
    DEFAULT_VOLUME = 0.5
    
    # Voice settings
    SELF_DEAF = True
    SELF_MUTE = False
    
    # Playback settings
    FFMPEG_OPTIONS = {
        'before_options': (
            '-reconnect 1 '
            '-reconnect_streamed 1 '
            '-reconnect_delay_max 5 '
        ),
        'options': (
            '-vn '                          # No video
            '-bufsize 512k '                # Small buffer
            '-ar 48000 '                   # 48kHz sample rate
            '-ac 2 '                        # Stereo
            '-b:a 128k'                    # 128kbps bitrate
        )
    }
    
    # YouTube settings with optimized speed
    YDL_OPTIONS = {
        'format': 'bestaudio/best',
        'quiet': True,
        'skip_download': True,
        'default_search': 'ytsearch',
        'source_address': '0.0.0.0',
        'extractor_retries': 2,
        'fragment_retries': 2,
        'ignoreerrors': False,
        'socket_timeout': 5,
    }
    
    # YouTube extractor args
    YDL_EXTRACTOR_ARGS = {
        'youtube': {
            'player_client': ['web'],
            'max_comments': [0],
        }
    }
    
    # Cookie file path
    COOKIE_FILE = 'cookies.txt'
    
    # Proxy configuration for anti-bot detection
    PROXY_URL = os.getenv('PROXY_URL', '')  # e.g., 'http://user:pass@proxy.com:8080'
    USE_PROXY = bool(PROXY_URL)
    PROXY_ROTATION_ENABLED = os.getenv('PROXY_ROTATION', 'false').lower() == 'true'
    
    # Speed optimization
    SEARCH_TIMEOUT = 5  # 5 seconds max for search
    EXTRACTION_TIMEOUT = 4  # 4 seconds max for extraction
    
    # Idle timeout (seconds)
    IDLE_TIMEOUT = 60
    
    # Logging
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'music-bot.log'
    
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
