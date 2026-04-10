"""
Simplified Search Manager - OPTIMIZED FOR SPEED & ANTI-BOT DETECTION
✅ Faster search (4-5 seconds)
✅ Proxy support for anti-bot detection
✅ Simplified code structure
✅ Better error handling
✅ Full terminal logging
"""

import yt_dlp
import logging
import re
import asyncio
import concurrent.futures
import os
import random
from typing import Optional, List, Tuple
from enum import Enum
from config import MusicBotConfig

logger = logging.getLogger('discord.music.search')

class Platform(Enum):
    """Supported music platforms"""
    YOUTUBE_MUSIC = "youtube_music"
    YOUTUBE = "youtube"
    SPOTIFY = "spotify"
    SOUNDCLOUD = "soundcloud"
    UNKNOWN = "unknown"


# ==================== PROXY MANAGEMENT ====================
class ProxyManager:
    """Manages proxy rotation for anti-bot detection"""
    
    def __init__(self):
        self.proxy_url = MusicBotConfig.get_proxy_url()
        self.rotation_enabled = MusicBotConfig.PROXY_ROTATION_ENABLED
        self.proxy_list = self._load_proxy_list()
        self.current_proxy_idx = 0
        
        if self.proxy_url:
            logger.info(f"✓ Proxy configured: {self.proxy_url[:30]}...")
            if self.rotation_enabled:
                logger.info(f"✓ Proxy rotation enabled with {len(self.proxy_list)} proxies")
    
    def _load_proxy_list(self) -> List[str]:
        """Load proxy list from environment or config file"""
        proxies = []
        
        # Try to load from .env PROXY_LIST
        proxy_env = os.getenv('PROXY_LIST', '')
        if proxy_env:
            proxies = [p.strip() for p in proxy_env.split(';') if p.strip()]
        
        # Add main proxy if configured
        if self.proxy_url and self.proxy_url not in proxies:
            proxies.insert(0, self.proxy_url)
        
        return proxies if proxies else [self.proxy_url] if self.proxy_url else []
    
    def get_proxy(self) -> Optional[str]:
        """Get proxy URL (with rotation if enabled)"""
        if not self.proxy_list:
            return None
        
        if self.rotation_enabled:
            proxy = self.proxy_list[self.current_proxy_idx]
            self.current_proxy_idx = (self.current_proxy_idx + 1) % len(self.proxy_list)
            return proxy
        
        return self.proxy_url if self.proxy_url else None


# ==================== USER AGENT ROTATION ====================
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

def get_random_user_agent() -> str:
    """Get random user agent for anti-detection"""
    return random.choice(USER_AGENTS)


# ==================== YDL OPTIONS WITH ANTI-BOT MEASURES ====================
def get_ydl_opts(proxy: Optional[str] = None, use_fast_mode: bool = True) -> dict:
    """Get yt-dlp options with anti-bot detection and speed optimization"""
    opts = {
        'format': 'bestaudio[acodec=opus]/bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
        'source_address': '0.0.0.0',
        'nocheckcertificate': True,
        'geo_bypass': True,
        'prefer_ffmpeg': True,
        
        # ⚡ SPEED OPTIMIZATION
        'socket_timeout': 5 if use_fast_mode else 10,
        'retries': 1 if use_fast_mode else 3,
        'fragment_retries': 1 if use_fast_mode else 3,
        'skip_unavailable_fragments': True,
        
        # 🤖 ANTI-BOT DETECTION
        'user_agent': get_random_user_agent(),
        'referer': 'https://www.youtube.com/',
        'sleep_interval': 0.5,
        'max_sleep_interval': 2,
        'sleep_interval_requests': 1,
        'ratelimit': 1000000,
        'throttledratelimit': 100000,
        'geo_bypass_country': 'US',
        
        # COOKIES
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') and os.path.getsize('cookies.txt') > 0 else None,
    }
    
    # Add proxy if available
    if proxy:
        opts['proxy'] = proxy
        logger.info(f"🔄 Using proxy: {proxy[:30]}...")
    
    # Fast extraction mode
    if use_fast_mode:
        opts['extract_flat'] = 'in_playlist'
    
    # YouTube extractor args
    opts['extractor_args'] = {
        'youtube': {
            'player_client': ['web'],
            'max_comments': [0],
        }
    }
    
    return opts


# ==================== SEARCH MANAGER ====================
class SearchManager:
    """Simplified music search manager with anti-bot detection"""
    
    # URL patterns for platform detection
    URL_PATTERNS = {
        Platform.YOUTUBE_MUSIC: [r'music\.youtube\.com'],
        Platform.YOUTUBE: [r'(youtube\.com|youtu\.be)'],
        Platform.SPOTIFY: [r'open\.spotify\.com'],
        Platform.SOUNDCLOUD: [r'soundcloud\.com'],
    }
    
    def __init__(self):
        """Initialize search manager"""
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.proxy_manager = ProxyManager()
        logger.info("⚡ Search Manager initialized (OPTIMIZED MODE)")
    
    @classmethod
    def detect_platform(cls, query: str) -> Platform:
        """Detect platform from URL"""
        query_lower = query.lower()
        for platform, patterns in cls.URL_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return platform
        return Platform.YOUTUBE
    
    @classmethod
    def is_url(cls, query: str) -> bool:
        """Check if query is a URL"""
        return query.startswith(('http://', 'https://'))
    
    @classmethod
    def is_playlist(cls, query: str) -> bool:
        """Check if query is a playlist"""
        playlist_indicators = ['playlist', 'album', '/sets/', '?list=', '&list=', 'list=RD', 'list=RDMM']
        return any(ind in query.lower() for ind in playlist_indicators)
    
    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> Tuple[List[dict], Platform, bool]:
        """
        FAST search with 4-5 sec timeout
        
        Args:
            query: Search query or URL
            limit: Max results
            
        Returns:
            (tracks, platform, is_playlist)
        """
        logger.info(f"🔍 Searching: {query[:60]}")
        
        try:
            # Handle URLs
            if self.is_url(query):
                return await self._search_url(query, limit)
            
            # Handle text search
            return await self._search_text(query, limit)
        
        except asyncio.TimeoutError:
            logger.error(f"❌ Search timeout for: {query}")
            return [], Platform.YOUTUBE, False
        except Exception as e:
            logger.error(f"❌ Search error: {e}")
            return [], Platform.YOUTUBE, False
    
    async def _search_text(
        self,
        query: str,
        limit: int
    ) -> Tuple[List[dict], Platform, bool]:
        """Search for text query"""
        loop = asyncio.get_event_loop()
        
        def _search():
            proxy = self.proxy_manager.get_proxy()
            opts = get_ydl_opts(proxy, use_fast_mode=True)
            opts['playlistend'] = limit
            search_query = f"ytsearch{limit}:{query}"
            
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    logger.info(f"📺 Searching YouTube for: {query}")
                    return ydl.extract_info(search_query, download=False)
            except Exception as e:
                logger.error(f"Search extraction failed: {e}")
                return None
        
        try:
            info = await asyncio.wait_for(
                loop.run_in_executor(self.executor, _search),
                timeout=MusicBotConfig.SEARCH_TIMEOUT
            )
            
            if not info or 'entries' not in info:
                logger.warning("No results found")
                return [], Platform.YOUTUBE, False
            
            tracks = []
            for entry in info['entries'][:limit]:
                if entry and entry.get('id'):
                    track = {
                        'title': entry.get('title', 'Unknown'),
                        'url': entry.get('webpage_url') or f"https://www.youtube.com/watch?v={entry.get('id')}",
                        'duration': entry.get('duration', 0),
                        'thumbnail': entry.get('thumbnail', ''),
                        'uploader': entry.get('uploader', 'Unknown'),
                        'id': entry.get('id'),
                    }
                    tracks.append(track)
            
            logger.info(f"✓ Found {len(tracks)} results")
            return tracks, Platform.YOUTUBE, False
        
        except asyncio.TimeoutError:
            logger.error(f"Search timed out after {MusicBotConfig.SEARCH_TIMEOUT}s")
            return [], Platform.YOUTUBE, False
        except Exception as e:
            logger.error(f"Search error: {e}")
            return [], Platform.YOUTUBE, False
    
    async def _search_url(
        self,
        url: str,
        limit: int
    ) -> Tuple[List[dict], Platform, bool]:
        """Search for URL"""
        platform = self.detect_platform(url)
        is_playlist = self.is_playlist(url)
        
        loop = asyncio.get_event_loop()
        
        def _extract():
            proxy = self.proxy_manager.get_proxy()
            opts = get_ydl_opts(proxy, use_fast_mode=True)
            opts['playlistend'] = min(limit, 25) if is_playlist else 1
            
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    if is_playlist:
                        logger.info(f"📋 Extracting playlist (max {limit} tracks)...")
                    else:
                        logger.info(f"🎵 Extracting track...")
                    return ydl.extract_info(url, download=False)
            except Exception as e:
                logger.error(f"Extraction failed: {e}")
                return None
        
        try:
            info = await asyncio.wait_for(
                loop.run_in_executor(self.executor, _extract),
                timeout=MusicBotConfig.EXTRACTION_TIMEOUT
            )
            
            if not info:
                return [], platform, is_playlist
            
            tracks = []
            
            # Handle playlist
            if 'entries' in info:
                entries = [e for e in info['entries'] if e]
                for entry in entries[:limit]:
                    if entry.get('id'):
                        track = {
                            'title': entry.get('title', 'Unknown'),
                            'url': entry.get('webpage_url') or f"https://www.youtube.com/watch?v={entry.get('id')}",
                            'duration': entry.get('duration', 0),
                            'thumbnail': entry.get('thumbnail', ''),
                            'uploader': entry.get('uploader', 'Unknown'),
                            'id': entry.get('id'),
                        }
                        tracks.append(track)
                logger.info(f"✓ Extracted {len(tracks)} tracks from playlist")
            else:
                # Single track
                if info.get('id'):
                    track = {
                        'title': info.get('title', 'Unknown'),
                        'url': info.get('webpage_url') or f"https://www.youtube.com/watch?v={info.get('id')}",
                        'duration': info.get('duration', 0),
                        'thumbnail': info.get('thumbnail', ''),
                        'uploader': info.get('uploader', 'Unknown'),
                        'id': info.get('id'),
                    }
                    tracks.append(track)
                    logger.info(f"✓ Extracted track")
            
            return tracks, platform, is_playlist
        
        except asyncio.TimeoutError:
            logger.error(f"Extraction timed out after {MusicBotConfig.EXTRACTION_TIMEOUT}s")
            return [], platform, is_playlist
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return [], platform, is_playlist
    
    async def get_suggestions(self, query: str, limit: int = 5) -> List[str]:
        """Get search suggestions for autocomplete"""
        if len(query) < 2:
            return []
        
        loop = asyncio.get_event_loop()
        
        def _get_suggestions():
            try:
                proxy = self.proxy_manager.get_proxy()
                opts = get_ydl_opts(proxy, use_fast_mode=True)
                opts['playlistend'] = limit
                search_query = f"ytsearch{limit}:{query}"
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(search_query, download=False)
                    
                    if not info or 'entries' not in info:
                        return []
                    
                    suggestions = []
                    for entry in info['entries'][:limit]:
                        if entry and entry.get('title'):
                            suggestions.append(entry['title'])
                    
                    return suggestions
            except Exception as e:
                logger.warning(f"Could not get suggestions: {e}")
                return []
        
        try:
            suggestions = await asyncio.wait_for(
                loop.run_in_executor(self.executor, _get_suggestions),
                timeout=2.0
            )
            return suggestions
        except asyncio.TimeoutError:
            logger.warning("Suggestions timed out")
            return []
        except Exception as e:
            logger.warning(f"Suggestions error: {e}")
            return []
    
    @staticmethod
    def get_platform_emoji(platform: Platform) -> str:
        """Get emoji for platform"""
        emojis = {
            Platform.YOUTUBE_MUSIC: "🎵",
            Platform.YOUTUBE: "📺",
            Platform.SPOTIFY: "🟢",
            Platform.SOUNDCLOUD: "🟠",
            Platform.UNKNOWN: "🎶"
        }
        return emojis.get(platform, "🎶")
    
    @staticmethod
    def get_platform_name(platform: Platform) -> str:
        """Get display name for platform"""
        names = {
            Platform.YOUTUBE_MUSIC: "YouTube Music",
            Platform.YOUTUBE: "YouTube",
            Platform.SPOTIFY: "Spotify",
            Platform.SOUNDCLOUD: "SoundCloud",
            Platform.UNKNOWN: "Unknown"
        }
        return names.get(platform, "Unknown")
    
    def shutdown(self):
        """Shutdown executor"""
        try:
            self.executor.shutdown(wait=False)
        except Exception:
            pass
