"""Music Bot Constants"""

# Bot settings
COMMAND_PREFIX = '!'
LOG_LEVEL = 'INFO'
LOG_FILE = 'music-bot.log'

# Limits
LIMITS = {
    'MAX_QUEUE_SIZE': 50,
    'DEFAULT_VOLUME': 50,
    'AUTO_DISCONNECT_IDLE': 300,  # 5 minutes
}

# Voice settings
VOICE_SETTINGS = {
    'SELF_DEAF': True,
    'SELF_MUTE': False,
}

# FFmpeg options for audio playback
FFMPEG_OPTS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -bufsize 512k -ar 48000 -ac 2 -b:a 128k'
}

# YouTube-DL options
YDL_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'noplaylist': True,
    'skip_download': True,
    'default_search': 'ytsearch',
}

YDL_EXTRACTOR_ARGS = {
    'youtube': {
        'player_client': ['android', 'web'],
    }
}

# Cookie file
COOKIE_FILE = 'cookies.txt'

# Proxy settings
PROXY_URL = None
USE_PROXY = False
PROXY_ROTATION_ENABLED = False

# Timeouts (in seconds)
TIMEOUTS = {
    'SEARCH': 10,
    'AUDIO_EXTRACTION': 10,
    'VOICE_CONNECT': 5,
}
