"""
Play Service - Railway Optimized
✅ Simple & fast audio extraction
✅ Timeout protection (Railway stability)
✅ Minimal memory overhead
✅ Parallel extraction in executor
✅ No complex state management
"""

import asyncio
import yt_dlp
import discord
import logging
from typing import Optional, Dict, Tuple
from collections import deque

logger = logging.getLogger('discord.music.play')

# ==================== CONFIGURATION ====================
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'default_search': 'ytsearch',
    'noplaylist': True,                    # ⚡ CRITICAL: Only first video
    'no_check_certificate': True,
    'socket_timeout': 8,
    'socket_interval': 0.1,
    'fragment_retries': 2,
    'extractor_retries': 2,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -bufsize 512k -ar 48000 -ac 2 -b:a 128k'
}

TIMEOUTS = {
    'EXTRACTION': 10.0,                    # Max 10 seconds to extract
    'VOICE_CONNECT': 5.0,                  # Max 5 seconds to connect
}


# ==================== SONG DATA CLASS ====================
class Song:
    """Lightweight song data"""
    def __init__(self, url: str, title: str, duration: int, requester_id: int):
        self.url = url
        self.title = title
        self.duration = duration
        self.requester_id = requester_id
        self.extracted_url: Optional[str] = None
    
    def __repr__(self):
        return f"Song({self.title[:30]}... {self.duration}s)"


# ==================== PLAY SERVICE ====================
class PlayService:
    """
    Fast, simple audio playback service for Railway
    - Direct yt-dlp extraction with timeouts
    - Per-guild queue (memory-efficient)
    - Parallel extraction in thread pool
    - Minimal state tracking
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.queues: Dict[int, deque] = {}  # guild_id -> queue
        self.now_playing: Dict[int, Song] = {}  # guild_id -> current song
        self.extracting: Dict[int, bool] = {}  # guild_id -> is extracting
        logger.info("🎵 Play Service initialized (Railway optimized)")
    
    def _get_best_audio_url(self, info: dict) -> Optional[str]:
        """Extract best audio URL from yt-dlp extraction info"""
        
        # Handle playlist/search results - extract first entry
        if info.get('_type') == 'playlist' and info.get('entries'):
            logger.debug("Detected playlist/search result, extracting first entry...")
            first_entry = info['entries'][0]
            if first_entry:
                return self._get_best_audio_url(first_entry)  # Recursive call on first video
        
        # Direct URL (bestaudio/best format)
        if info.get('url') and isinstance(info['url'], str):
            url = str(info['url']).strip()
            if url and url.startswith('http'):
                logger.debug("Using direct audio URL from info")
                return url
        
        # Check formats array
        if info.get('formats') and isinstance(info['formats'], list):
            for fmt in info['formats']:
                if isinstance(fmt, dict):
                    acodec = fmt.get('acodec', '')
                    vcodec = fmt.get('vcodec', '')
                    fmt_url = fmt.get('url', '')
                    
                    # Prefer audio-only
                    if acodec and acodec != 'none' and (not vcodec or vcodec == 'none') and fmt_url:
                        return fmt_url
            
            # Fallback to any audio format
            for fmt in info['formats']:
                if isinstance(fmt, dict):
                    acodec = fmt.get('acodec', '')
                    fmt_url = fmt.get('url', '')
                    if acodec and acodec != 'none' and fmt_url:
                        return fmt_url
        
        # Check requested_formats
        if info.get('requested_formats') and isinstance(info['requested_formats'], list):
            for fmt in info['requested_formats']:
                if isinstance(fmt, dict):
                    fmt_url = fmt.get('url', '')
                    if fmt_url:
                        return fmt_url
        
        logger.warning(f"Could not extract audio URL from info. Keys: {list(info.keys())}")
        return None
    
    def get_queue(self, guild_id: int) -> deque:
        """Get or create queue for guild"""
        if guild_id not in self.queues:
            self.queues[guild_id] = deque(maxlen=50)  # Max 50 songs, memory-friendly
        return self.queues[guild_id]
    
    async def extract_audio_url(self, url_or_search: str) -> Optional[str]:
        """
        Extract direct audio URL from YouTube (non-blocking)
        Runs in thread pool executor for Railway stability
        Returns audio URL or None on timeout/error
        """
        try:
            def _extract():
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    info = ydl.extract_info(url_or_search, download=False)
                    
                    # Handle playlist/search results - use first entry
                    if info.get('_type') == 'playlist' and info.get('entries'):
                        video_info = info['entries'][0]
                    else:
                        video_info = info
                    
                    audio_url = self._get_best_audio_url(video_info)
                    return audio_url
            
            # Run in executor with timeout
            audio_url = await asyncio.wait_for(
                self.bot.loop.run_in_executor(None, _extract),
                timeout=TIMEOUTS['EXTRACTION']
            )
            return audio_url
        except asyncio.TimeoutError:
            logger.warning(f"Extraction timeout for: {url_or_search[:50]}")
            return None
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return None
    
    async def search_and_get_info(self, url_or_search: str) -> Optional[Song]:
        """
        Search/extract info and return Song object
        Returns None on error/timeout
        """
        try:
            def _search():
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    info = ydl.extract_info(url_or_search, download=False)
                    
                    # Handle playlist/search results - use first entry
                    if info.get('_type') == 'playlist' and info.get('entries'):
                        logger.debug(f"Got {len(info['entries'])} search results, using first")
                        video_info = info['entries'][0]
                    else:
                        video_info = info
                    
                    audio_url = self._get_best_audio_url(video_info)
                    return {
                        'url': audio_url,
                        'title': video_info.get('title', 'Unknown'),
                        'duration': video_info.get('duration', 0),
                    }
            
            result = await asyncio.wait_for(
                self.bot.loop.run_in_executor(None, _search),
                timeout=TIMEOUTS['EXTRACTION']
            )
            
            if not result['url']:
                logger.warning(f"No audio URL found for: {url_or_search[:50]}")
                return None
            
            song = Song(
                url=result['url'],
                title=result['title'],
                duration=result['duration'],
                requester_id=0  # Set by caller
            )
            logger.info(f"✅ Found: {song.title} ({song.duration}s)")
            return song
        except asyncio.TimeoutError:
            logger.warning(f"Search timeout: {url_or_search[:50]}")
            return None
        except Exception as e:
            logger.error(f"Search error: {e}")
            return None
    
    async def play_song(
        self,
        ctx,
        url_or_search: str,
        status_msg=None
    ) -> Tuple[bool, str]:
        """
        Play a song immediately
        Returns: (success: bool, message: str)
        """
        # Check voice channel
        if not ctx.author.voice or not ctx.author.voice.channel:
            return False, "❌ You must be in a voice channel"
        
        channel = ctx.author.voice.channel
        
        # Update status
        if status_msg:
            loading_embed = discord.Embed(
                title="🔄 Loading...",
                description=f"Extracting audio from YouTube...",
                color=discord.Color.blue()
            )
            try:
                await status_msg.edit(embed=loading_embed)
            except:
                pass
        
        # ==================== STEP 1: CONNECT ====================
        try:
            if ctx.voice_client is None:
                logger.info(f"Connecting to: {channel}")
                voice_client = await asyncio.wait_for(
                    channel.connect(),
                    timeout=TIMEOUTS['VOICE_CONNECT']
                )
            else:
                voice_client = ctx.voice_client
                if voice_client.channel != channel:
                    await asyncio.wait_for(
                        voice_client.move_to(channel),
                        timeout=TIMEOUTS['VOICE_CONNECT']
                    )
        except asyncio.TimeoutError:
            logger.error("Voice connection timeout")
            return False, "❌ Voice connection timeout (5s)"
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False, f"❌ Connection error: {str(e)[:50]}"
        
        # ==================== STEP 2: EXTRACT AUDIO ====================
        try:
            def extract():
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    info = ydl.extract_info(url_or_search, download=False)
                    
                    # Handle playlist/search results - use first entry
                    if info.get('_type') == 'playlist' and info.get('entries'):
                        logger.debug(f"Got {len(info['entries'])} search results, using first")
                        video_info = info['entries'][0]
                    else:
                        video_info = info
                    
                    # Properly extract audio URL
                    audio_url = self._get_best_audio_url(video_info)
                    return {
                        'url': audio_url,
                        'title': video_info.get('title', 'Unknown'),
                        'duration': video_info.get('duration', 0),
                    }
            
            logger.info(f"Extracting: {url_or_search[:50]}")
            info = await asyncio.wait_for(
                self.bot.loop.run_in_executor(None, extract),
                timeout=TIMEOUTS['EXTRACTION']
            )
            
            if not info['url']:
                logger.error("Failed to extract audio URL")
                return False, "❌ No audio found for this video"
        except asyncio.TimeoutError:
            logger.error("Extraction timeout")
            return False, "❌ YouTube timeout (10s) - Try another video"
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return False, f"❌ Extraction error: {str(e)[:50]}"
        
        # ==================== STEP 3: PLAY ====================
        try:
            url = info['url']
            title = info['title']
            duration = info['duration']
            
            # Format duration
            minutes = duration // 60
            seconds = duration % 60
            duration_str = f"{minutes}:{seconds:02d}"
            
            # Create audio source
            audio_source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
            
            def after_play(error):
                if error:
                    logger.error(f"Playback error: {error}")
                else:
                    logger.info(f"✅ Finished: {title}")
            
            # Play it!
            voice_client.play(audio_source, after=after_play)
            
            logger.info(f"▶️ Playing: {title} ({duration_str})")
            
            if status_msg:
                embed = discord.Embed(
                    title="🎵 Now Playing",
                    description=title[:256],
                    color=discord.Color.green()
                )
                embed.add_field(name="Duration", value=duration_str, inline=False)
                embed.add_field(name="Channel", value=channel.mention, inline=False)
                try:
                    await status_msg.edit(embed=embed)
                except:
                    pass
            
            return True, f"▶️ Playing: {title}"
        
        except Exception as e:
            logger.error(f"Playback error: {e}")
            return False, f"❌ Playback error: {str(e)[:50]}"
    
    async def queue_song(
        self,
        guild_id: int,
        url_or_search: str,
        requester_id: int
    ) -> str:
        """
        Add song to queue
        Returns status message
        """
        song = await self.search_and_get_info(url_or_search)
        if not song:
            return "❌ Could not find song"
        
        song.requester_id = requester_id
        queue = self.get_queue(guild_id)
        queue.append(song)
        
        length = len(queue)
        return f"✅ Queued: {song.title} (Position: {length})"
    
    def get_now_playing(self, guild_id: int) -> Optional[Song]:
        """Get currently playing song"""
        return self.now_playing.get(guild_id)
    
    def get_queue_list(self, guild_id: int) -> str:
        """Get formatted queue list"""
        queue = self.get_queue(guild_id)
        if not queue:
            return "📭 Queue is empty"
        
        lines = ["**📋 Queue:**"]
        for i, song in enumerate(queue, 1):
            lines.append(f"{i}. {song.title[:50]}... ({song.duration}s)")
        
        return "\n".join(lines[:10])  # Show first 10
    
    def stop_playback(self, guild_id: int, voice_client: discord.VoiceClient):
        """Stop playback and clear queue"""
        if voice_client and voice_client.is_playing():
            voice_client.stop()
        self.clear_queue(guild_id)
        logger.info(f"Stopped playback in guild {guild_id}")


# ==================== SINGLETON INSTANCE ====================
_play_service = None

def get_play_service(bot) -> PlayService:
    """Get or create play service singleton"""
    global _play_service
    if _play_service is None:
        _play_service = PlayService(bot)
    return _play_service
