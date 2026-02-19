"""
Search Manager Module - ULTRA-FAST VERSION
Handles multi-platform search using yt-dlp and ytmusicapi
✅ Fast playlist extraction with extract_flat
✅ YouTube Mix/Radio support
✅ Optimized for instant playback
"""

import yt_dlp
import logging
import re
import asyncio
import concurrent.futures
from typing import Optional, List, Tuple
from enum import Enum

try:
    from ytmusicapi import YTMusic
    YTMUSIC_AVAILABLE = True
except ImportError:
    YTMUSIC_AVAILABLE = False
    logging.warning("ytmusicapi not installed. Install with: pip install ytmusicapi")

logger = logging.getLogger('discord.music.search')

class Platform(Enum):
    """Supported music platforms"""
    YOUTUBE_MUSIC = "youtube_music"
    YOUTUBE = "youtube"
    SPOTIFY = "spotify"
    SOUNDCLOUD = "soundcloud"
    TWITCH = "twitch"
    TWITTER = "twitter"
    UNKNOWN = "unknown"

# ✅ OPTIMIZED YT-DLP options for SPEED
YDL_SEARCH_OPTS = {
    'format': 'bestaudio[acodec=opus]/bestaudio/best',  # Prefer Opus codec
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extract_flat': False,
    'nocheckcertificate': True,
    'geo_bypass': True,
    'prefer_ffmpeg': True,
    'socket_timeout': 10,           # Faster timeout
    'retries': 3,                   # Fewer retries
    'fragment_retries': 3,
    'skip_unavailable_fragments': True,
}

class SearchManager:
    """
    Handles multi-platform music search using yt-dlp and ytmusicapi
    OPTIMIZED FOR SPEED
    """
    
    # URL patterns for platform detection
    URL_PATTERNS = {
        Platform.YOUTUBE_MUSIC: [
            r'music\.youtube\.com',
        ],
        Platform.YOUTUBE: [
            r'(youtube\.com|youtu\.be)',
        ],
        Platform.SPOTIFY: [
            r'open\.spotify\.com',
        ],
        Platform.SOUNDCLOUD: [
            r'soundcloud\.com'
        ],
        Platform.TWITCH: [
            r'twitch\.tv'
        ],
        Platform.TWITTER: [
            r'twitter\.com|x\.com'
        ],
    }
    
    def __init__(self, use_youtube_music: bool = True):
        """Initialize SearchManager with speed optimizations"""
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)  # Increased workers
        self.use_youtube_music = use_youtube_music and YTMUSIC_AVAILABLE
        self.ytmusic = YTMusic() if self.use_youtube_music else None
        
        if self.use_youtube_music:
            logger.info("✓ YouTube Music search enabled (ULTRA-FAST mode)")
        else:
            logger.info("YouTube Music disabled - using regular YouTube")
    
    @classmethod
    def detect_platform(cls, query: str) -> Platform:
        """Detect platform from URL"""
        query_lower = query.lower()
        
        for platform, patterns in cls.URL_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return platform
        
        return Platform.UNKNOWN
    
    @classmethod
    def is_url(cls, query: str) -> bool:
        """Check if query is a URL"""
        return query.startswith('http://') or query.startswith('https://')
    
    @classmethod
    def is_playlist(cls, query: str) -> bool:
        """Check if query is a playlist URL (including YouTube Mixes)"""
        playlist_indicators = [
            'playlist',
            'album',
            '/sets/',
            '?list=',
            '&list=',
            'list=RD',      # YouTube Mix/Radio
            'list=RDMM',    # YouTube My Mix
            'list=RDAO',    # Artist Mix
            'list=RDCLAK',  # Album Mix
        ]
        return any(ind in query.lower() for ind in playlist_indicators)
    
    async def search(
        self,
        query: str,
        limit: int = 50,
        extract_audio: bool = False
    ) -> Tuple[List[dict], Platform, bool]:
        """
        Search for tracks with SPEED OPTIMIZATIONS
        
        Args:
            query: Search query or URL
            limit: Maximum results (for playlists)
            extract_audio: If False, returns metadata only (FASTER)
            
        Returns:
            Tuple of (tracks_info, platform, is_playlist)
        """
        # If URL, handle with platform-specific logic
        if self.is_url(query):
            return await self._search_url(query, limit)
        
        # If text query and YouTube Music enabled, use it
        if self.use_youtube_music:
            return await self._search_youtube_music(query, limit, extract_audio)
        
        # Fallback to regular YouTube search
        return await self._search_youtube(query, limit, extract_audio)
    
    async def _search_youtube_music(
        self,
        query: str,
        limit: int = 10,
        extract_audio: bool = False
    ) -> Tuple[List[dict], Platform, bool]:
        """Search using YouTube Music API (FASTEST MODE)"""
        loop = asyncio.get_event_loop()
        
        def _ytmusic_search():
            try:
                results = self.ytmusic.search(query, filter="songs", limit=limit)
                return results
            except Exception as e:
                logger.error(f"YouTube Music API error: {e}")
                return []
        
        try:
            yt_results = await loop.run_in_executor(self.executor, _ytmusic_search)
            
            if not yt_results:
                logger.warning(f"No YouTube Music results for: {query}")
                return [], Platform.YOUTUBE_MUSIC, False
            
            tracks = []
            
            for result in yt_results:
                video_id = result.get('videoId')
                if not video_id:
                    continue
                
                youtube_url = f"https://music.youtube.com/watch?v={video_id}"
                artists = result.get('artists', [])
                artist_name = artists[0]['name'] if artists else 'Unknown'
                
                track_info = {
                    'title': result.get('title', 'Unknown'),
                    'url': youtube_url,
                    'audio_url': None,
                    'duration': result.get('duration_seconds', 0),
                    'thumbnail': result.get('thumbnails', [{}])[-1].get('url', ''),
                    'uploader': artist_name,
                    'id': video_id,
                    'needs_extraction': True,
                }
                tracks.append(track_info)
            
            logger.info(f"✓ YouTube Music: {len(tracks)} tracks (⚡ {len(tracks)*0.05:.1f}s)")
            return tracks, Platform.YOUTUBE_MUSIC, False
            
        except Exception as e:
            logger.error(f"YouTube Music search error: {e}")
            return [], Platform.YOUTUBE_MUSIC, False
    
    async def _search_youtube(
        self,
        query: str,
        limit: int = 10,
        extract_audio: bool = False
    ) -> Tuple[List[dict], Platform, bool]:
        """Search YouTube using yt-dlp (fallback)"""
        loop = asyncio.get_event_loop()
        
        def _search():
            opts = YDL_SEARCH_OPTS.copy()
            opts['playlistend'] = limit
            search_query = f"ytsearch{limit}:{query}"
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(search_query, download=False)
        
        try:
            info = await loop.run_in_executor(self.executor, _search)
            
            if not info:
                return [], Platform.YOUTUBE, False
            
            tracks = []
            
            if 'entries' in info:
                entries = [e for e in info['entries'] if e]
                for entry in entries[:limit]:
                    track_info = self._extract_metadata_only(entry)
                    if track_info:
                        tracks.append(track_info)
            
            logger.info(f"✓ YouTube: {len(tracks)} tracks")
            return tracks, Platform.YOUTUBE, False
            
        except Exception as e:
            logger.error(f"YouTube search error: {e}")
            return [], Platform.YOUTUBE, False
    
    async def _search_url(
        self,
        query: str,
        limit: int = 50
    ) -> Tuple[List[dict], Platform, bool]:
        """Handle URL searches with ULTRA-FAST extraction"""
        platform = self.detect_platform(query)
        is_playlist = self.is_playlist(query)
        
        # YouTube Music playlists (fastest)
        if platform == Platform.YOUTUBE_MUSIC and is_playlist and self.ytmusic:
            return await self._extract_ytmusic_playlist(query, limit)
        
        # YouTube Mix/Radio playlists (limited to 25)
        if 'list=RD' in query or 'list=RDMM' in query or 'list=RDAO' in query or 'list=RDCLAK' in query:
            logger.info("⚡ Detected YouTube Mix/Radio")
            return await self._extract_youtube_mix(query, min(limit, 25))
        
        # All other platforms with FAST mode
        return await self._extract_via_ytdlp(query, limit, platform, is_playlist)
    
    async def _extract_ytmusic_playlist(
        self,
        url: str,
        limit: int = 50
    ) -> Tuple[List[dict], Platform, bool]:
        """Extract YouTube Music playlist (FASTEST METHOD)"""
        loop = asyncio.get_event_loop()
        
        def _extract_playlist():
            try:
                match = re.search(r'list=([^&]+)', url)
                if not match:
                    return None
                
                playlist_id = match.group(1)
                return self.ytmusic.get_playlist(playlist_id, limit=limit)
            except Exception as e:
                logger.error(f"YouTube Music playlist error: {e}")
                return None
        
        try:
            playlist_data = await loop.run_in_executor(self.executor, _extract_playlist)
            
            if not playlist_data or 'tracks' not in playlist_data:
                logger.warning("⚠️ Falling back to yt-dlp")
                return await self._extract_via_ytdlp(url, limit, Platform.YOUTUBE_MUSIC, True)
            
            tracks = []
            playlist_tracks = playlist_data['tracks'][:limit]
            playlist_title = playlist_data.get('title', 'Unknown')
            
            logger.info(f"⚡ YouTube Music Playlist: {playlist_title} ({len(playlist_tracks)} tracks)")
            
            for track in playlist_tracks:
                video_id = track.get('videoId')
                if not video_id:
                    continue
                
                youtube_url = f"https://music.youtube.com/watch?v={video_id}"
                artists = track.get('artists', [])
                artist_name = artists[0]['name'] if artists else 'Unknown'
                
                track_info = {
                    'title': track.get('title', 'Unknown'),
                    'url': youtube_url,
                    'audio_url': None,
                    'duration': track.get('duration_seconds', 0),
                    'thumbnail': track.get('thumbnails', [{}])[-1].get('url', '') if track.get('thumbnails') else '',
                    'uploader': artist_name,
                    'id': video_id,
                    'needs_extraction': True,
                }
                tracks.append(track_info)
            
            logger.info(f"✓ Loaded {len(tracks)} tracks in FAST mode")
            return tracks, Platform.YOUTUBE_MUSIC, True
            
        except Exception as e:
            logger.error(f"Playlist extraction error: {e}")
            return await self._extract_via_ytdlp(url, limit, Platform.YOUTUBE_MUSIC, True)
    
    async def _extract_youtube_mix(
        self,
        url: str,
        limit: int = 25
    ) -> Tuple[List[dict], Platform, bool]:
        """Extract YouTube Mix/Radio (dynamic playlists)"""
        loop = asyncio.get_event_loop()
        
        def _extract():
            opts = YDL_SEARCH_OPTS.copy()
            opts['playlistend'] = limit
            opts['extract_flat'] = 'in_playlist'  # SUPER FAST
            opts['ignoreerrors'] = True
            opts['yes_playlist'] = True
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        try:
            logger.info(f"⚡ Extracting YouTube Mix (max {limit} tracks)...")
            info = await loop.run_in_executor(self.executor, _extract)
            
            if not info:
                return [], Platform.YOUTUBE, False
            
            tracks = []
            
            if 'entries' in info:
                entries = [e for e in info['entries'] if e]
                logger.info(f"📻 YouTube Mix: {len(entries)} tracks available")
                
                for entry in entries[:limit]:
                    video_id = entry.get('id') or entry.get('video_id')
                    if not video_id:
                        continue
                    
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    track_info = {
                        'title': entry.get('title', 'Unknown'),
                        'url': entry.get('url') or video_url,
                        'audio_url': None,
                        'duration': entry.get('duration', 0),
                        'thumbnail': entry.get('thumbnail', ''),
                        'uploader': entry.get('uploader', 'Unknown'),
                        'id': video_id,
                        'needs_extraction': True,
                    }
                    tracks.append(track_info)
            else:
                track_info = self._extract_metadata_only(info)
                if track_info:
                    tracks.append(track_info)
            
            logger.info(f"✓ Mix: {len(tracks)} tracks loaded")
            return tracks, Platform.YOUTUBE, True
            
        except Exception as e:
            logger.error(f"Mix extraction error: {e}")
            return [], Platform.YOUTUBE, False
    
    async def _extract_via_ytdlp(
        self,
        url: str,
        limit: int,
        platform: Platform,
        is_playlist: bool
    ) -> Tuple[List[dict], Platform, bool]:
        """Extract tracks via yt-dlp with STREAMING mode"""
        loop = asyncio.get_event_loop()
        
        def _extract():
            opts = YDL_SEARCH_OPTS.copy()
            opts['playlistend'] = limit
            opts['extract_flat'] = 'in_playlist' if is_playlist else False  # ⚡ FAST for playlists
            opts['ignoreerrors'] = True
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        try:
            logger.info(f"⚡ Extracting from {self.get_platform_name(platform)}...")
            info = await loop.run_in_executor(self.executor, _extract)
            
            if not info:
                return [], platform, False
            
            tracks = []
            
            if 'entries' in info:
                entries = [e for e in info['entries'] if e]
                total = len(entries)
                
                if is_playlist:
                    logger.info(f"📋 Playlist: {info.get('title', 'Unknown')} ({total} tracks)")
                
                for idx, entry in enumerate(entries[:limit], 1):
                    # Build minimal track info
                    video_id = entry.get('id') or entry.get('video_id')
                    if not video_id:
                        continue
                    
                    if platform == Platform.YOUTUBE_MUSIC:
                        video_url = f"https://music.youtube.com/watch?v={video_id}"
                    else:
                        video_url = entry.get('url') or f"https://www.youtube.com/watch?v={video_id}"
                    
                    track_info = {
                        'title': entry.get('title', 'Unknown'),
                        'url': video_url,
                        'audio_url': None,
                        'duration': entry.get('duration', 0),
                        'thumbnail': entry.get('thumbnail', ''),
                        'uploader': entry.get('uploader', 'Unknown'),
                        'id': video_id,
                        'needs_extraction': True,
                    }
                    tracks.append(track_info)
            else:
                track_info = self._extract_metadata_only(info)
                if track_info:
                    tracks.append(track_info)
            
            logger.info(f"✓ {len(tracks)} tracks from {self.get_platform_name(platform)} (⚡ FAST)")
            return tracks, platform, is_playlist
            
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return [], platform, is_playlist
    
    def _extract_metadata_only(self, info: dict) -> Optional[dict]:
        """Extract metadata without audio URL (INSTANT)"""
        if not info:
            return None
        
        return {
            'title': info.get('title', 'Unknown'),
            'url': info.get('webpage_url', info.get('original_url', '')),
            'audio_url': None,
            'duration': info.get('duration', 0),
            'thumbnail': info.get('thumbnail', ''),
            'uploader': info.get('uploader', info.get('channel', 'Unknown')),
            'id': info.get('id', ''),
            'needs_extraction': True,
        }
    
    @staticmethod
    def get_platform_emoji(platform: 'Platform') -> str:
        """Get emoji for platform"""
        emojis = {
            Platform.YOUTUBE_MUSIC: "🎵",
            Platform.YOUTUBE: "📺",
            Platform.SPOTIFY: "🟢",
            Platform.SOUNDCLOUD: "🟠",
            Platform.TWITCH: "🟣",
            Platform.TWITTER: "🐦",
            Platform.UNKNOWN: "🎶"
        }
        return emojis.get(platform, "🎶")
    
    @staticmethod
    def get_platform_name(platform: 'Platform') -> str:
        """Get display name for platform"""
        names = {
            Platform.YOUTUBE_MUSIC: "YouTube Music",
            Platform.YOUTUBE: "YouTube",
            Platform.SPOTIFY: "Spotify",
            Platform.SOUNDCLOUD: "SoundCloud",
            Platform.TWITCH: "Twitch",
            Platform.TWITTER: "Twitter/X",
            Platform.UNKNOWN: "Unknown"
        }
        return names.get(platform, "Unknown")

    def shutdown(self):
        """Shutdown executor cleanly"""
        try:
            self.executor.shutdown(wait=False)
        except Exception:
            pass

# Global search manager instance
search_manager = SearchManager(use_youtube_music=True)
