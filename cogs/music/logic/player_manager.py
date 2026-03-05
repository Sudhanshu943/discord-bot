"""
Player Manager Module - ULTRA-FAST VERSION
✅ Pre-extraction for instant playback
✅ Background pre-loading for next songs
✅ Optimized FFmpeg for low latency
✅ Opus codec preference
✅ YouTube cookies support
"""

import discord
import yt_dlp
import logging
import asyncio
import concurrent.futures
import re
import requests
import os
from dotenv import load_dotenv
from typing import Optional, Dict, Any
from collections import deque


logger = logging.getLogger('discord.music.player')

# Load environment variables
load_dotenv()

# Cookie file path
COOKIE_FILE = 'cookies.txt'

def download_youtube_cookies():
    """Download cookies.txt directly from URL (no encryption)"""
    cookie_url = os.getenv('YOUTUBE_COOKIE_URL')

    if not cookie_url:
        logger.info("No cookie URL configured in .env")
        return False

    try:
        logger.info("⬇️ Downloading YouTube cookies...")
        response = requests.get(cookie_url, timeout=30)
        response.raise_for_status()

        with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
            f.write(response.text)

        logger.info("✅ YouTube cookies downloaded successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to download cookies: {e}")
        return False

async def init_cookies(self):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, download_youtube_cookies)

# ✅ IMPROVED YT-DLP options - Works with or without Node.js
YDL_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'skip_download': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extractor_retries': 5,
    'fragment_retries': 5,
    'ignoreerrors': False,
}

# Add cookies to YDL_OPTS if file exists
if os.path.exists(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 0:
    YDL_OPTS['cookiefile'] = COOKIE_FILE
    logger.info("✅ YouTube cookies enabled")

# Extractor's specific args for YouTube
YDL_EXTRACTOR_ARGS = {
    'youtube': {
        'player_client': ['default'],  # Try simpler clients first
        'player_skip': ['configs', 'js', 'hls'],
    }
}



# ✅ OPTIMIZED FFmpeg options for LOW LATENCY
FFMPEG_OPTS = {
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

class Song:
    """Represents a song/track"""
    def __init__(self, source: str, title: str, url: str, duration: int = 0,
                 thumbnail: str = None, requester: discord.Member = None):
        self.source = source
        self.title = title
        self.url = url
        self.duration = duration
        self.thumbnail = thumbnail
        self.requester = requester
    
    @property
    def duration_str(self) -> str:
        if self.duration <= 0:
            return "?:??"
        duration = int(self.duration)
        mins, secs = divmod(duration, 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours}:{mins:02d}:{secs:02d}"
        return f"{mins}:{secs:02d}"


class PlayerManager:
    """Manages multiple music players for different guilds"""
    def __init__(self, bot):
        self.bot = bot
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.players = {}
        
    def get_player(self, guild):
        if guild.id not in self.players:
            self.players[guild.id] = MusicPlayer(guild, self)
        return self.players[guild.id]
        
    def remove_player(self, guild_id):
        if guild_id in self.players:
            del self.players[guild_id]
            
    async def disconnect(self, guild):
        player = self.get_player(guild)
        await player.disconnect()
        self.remove_player(guild.id)


class MusicPlayer:
    """
    Manages music playback with SPEED OPTIMIZATIONS
    ✅ Pre-extraction
    ✅ Background pre-loading
    ✅ Low latency FFmpeg
    """
    
    def __init__(self, guild: discord.Guild, player_manager):
        self.guild = guild
        self.player_manager = player_manager
        self.bot = player_manager.bot
        self.voice_client: discord.VoiceClient = None
        self.queue: deque = deque()
        self.current: Song = None
        self.volume: float = 0.5
        self.loop: bool = False
        self.text_channel: discord.TextChannel = None
        self.executor = player_manager.executor
        self.controller_message: discord.Message = None
        self._preload_task: Optional[asyncio.Task] = None  
        self._idle_task: Optional[asyncio.Task] = None
        self._voice_lock = asyncio.Lock()  # Per-guild lock for voice operations
        self._is_connecting: bool = False  # Track connection state to prevent reconnect loops
        self._connection_failures: int = 0  # Track connection failures
        self._last_failure_time: float = 0  # Track last failure time
        self._reconnect_delay: float = 1.0  # Initial reconnect delay

    
    @property
    def is_playing(self) -> bool:
        return self.voice_client and self.voice_client.is_playing()
    
    @property
    def is_paused(self) -> bool:
        return self.voice_client and self.voice_client.is_paused()
    
    @property
    def queue_count(self) -> int:
        return len(self.queue)
    
    @property
    def queue_empty(self) -> bool:
        return len(self.queue) == 0
    
    def get_queue_list(self, limit: int = 10) -> list:
        """Get list of queued songs up to the specified limit"""
        return list(self.queue)[:limit]
    
    async def connect(self, channel: discord.VoiceChannel) -> bool:
        async with self._voice_lock:
            # Prevent concurrent connection attempts
            if self._is_connecting:
                logger.warning(f"Already connecting to {channel.name}, skipping...")
                return False
            
            # If already connected properly
            if self.voice_client and self.voice_client.is_connected():
                if self.voice_client.channel.id == channel.id:
                    return True
                await self.voice_client.move_to(channel)
                return True

            # Cleanup stale client
            if self.voice_client:
                try:
                    await self.voice_client.disconnect(force=True)
                except:
                    pass
                self.voice_client = None
                await asyncio.sleep(0.5)

            self._is_connecting = True
            self._connection_failures = 0
            
            try:
                # Use reconnect=True to handle network issues
                self.voice_client = await channel.connect(
                    self_deaf=True,
                    self_mute=False,
                    reconnect=True
                )
                logger.info(f"Connected to {channel.name}")
                return True

            except Exception as e:
                logger.error(f"Voice connect failed: {e}")
                self.voice_client = None
                return False
            finally:
                self._is_connecting = False
    
    async def disconnect(self):
        """External disconnect - acquires lock first"""
        async with self._voice_lock:
            await self._do_disconnect()
    
    async def _do_disconnect(self):
        """Internal disconnect - called when lock is already held"""
        # Cancel preload task
        if self._preload_task and not self._preload_task.done():
            self._preload_task.cancel()
            try:
                await self._preload_task
            except:
                pass

        # Cancel idle task
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
            try:
                await self._idle_task
            except:
                pass

        # Clean up voice client properly
        if self.voice_client:
            try:
                # Stop any playing audio first
                if self.voice_client.is_playing():
                    self.voice_client.stop()

                # Disconnect and clean up
                await self.voice_client.disconnect()
            except Exception as e:
                logger.warning(f"Error during voice disconnect: {e}")
            finally:
                self.voice_client = None

        self.queue.clear()
        self.current = None
        self._is_connecting = False  # Reset connection state on disconnect
        self._connection_failures = 0  # Reset failure counter on disconnect

        logger.info(f"Disconnected from {self.guild.name}")

    
    async def extract_audio_url(self, url: str, fast: bool = False) -> Optional[str]:
        """
        Extract audio URL with fallback support:
        1. First try YouTube Music URL
        2. If extraction fails, try regular YouTube URL
        Args:
            fast: If True, prefer speed over quality
        """
        loop = asyncio.get_event_loop()
        
        # Check if this is a YouTube Music URL
        youtube_music_pattern = r'music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]+)'
        match = re.search(youtube_music_pattern, url)
        
        if match:
            # This is a YouTube Music URL - try both YouTube Music and regular YouTube
            video_id = match.group(1)
            youtube_music_url = url
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
            
            logger.info(f"Trying YouTube Music first: {youtube_music_url}")
            
            # First try YouTube Music
            audio_url = await self._try_extract(loop, youtube_music_url, fast)
            
            if not audio_url:
                # Fallback to regular YouTube
                logger.warning(f"YouTube Music extraction failed, trying regular YouTube: {youtube_url}")
                audio_url = await self._try_extract(loop, youtube_url, fast)
            
            return audio_url
        else:
            # Regular YouTube URL - just try once
            return await self._try_extract(loop, url, fast)
    
    async def _try_extract(self, loop, url: str, fast: bool = False) -> Optional[str]:
        """Helper method to extract audio URL with error handling"""
        def _extract():
            opts = YDL_OPTS.copy()
            opts['extractor_args'] = YDL_EXTRACTOR_ARGS
            if fast:
                opts['format'] = 'bestaudio/best'  # Faster format for quick search
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        try:
            info = await loop.run_in_executor(self.executor, _extract)
            
            if not info:
                return None
            
            return self._get_audio_url(info)
            
        except yt_dlp.utils.DownloadError as e:
            logger.warning(f"Download error for {url}: {e}")
            return None
        except yt_dlp.utils.ExtractorError as e:
            logger.warning(f"Extractor error for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Extraction error for {url}: {e}")
            return None
    
    def _get_audio_url(self, info: dict) -> Optional[str]:
        """Extract best audio URL from yt-dlp info"""
        audio_url = None
        
        # Method 1: Direct URL
        if info.get('url'):
            audio_url = info.get('url')
        
        # Method 2: Check formats array (prefer Opus)
        elif 'formats' in info:
            formats = info.get('formats', [])
            
            # ✅ Prefer Opus codec (best for Discord)
            opus_formats = [
                f for f in formats 
                if f.get('acodec') == 'opus'
                and f.get('url')
            ]
            
            if opus_formats:
                best_opus = max(opus_formats, key=lambda x: x.get('abr', 0) or 0)
                audio_url = best_opus.get('url')
            else:
                # Fallback to audio-only formats
                audio_formats = [
                    f for f in formats 
                    if f.get('acodec') != 'none' 
                    and f.get('vcodec') == 'none' 
                    and f.get('url')
                ]
                
                if audio_formats:
                    best_audio = max(audio_formats, key=lambda x: x.get('abr', 0) or 0)
                    audio_url = best_audio.get('url')
                else:
                    # Last resort: any format with audio
                    for fmt in formats:
                        if fmt.get('acodec') != 'none' and fmt.get('url'):
                            audio_url = fmt.get('url')
                            break
        
        # Method 3: requested_formats
        elif 'requested_formats' in info:
            for fmt in info['requested_formats']:
                if fmt.get('acodec') != 'none' and fmt.get('url'):
                    audio_url = fmt.get('url')
                    break
        
        return audio_url
    
    async def _preload_next_song(self):
        """✅ PRE-LOAD next song in background for INSTANT playback"""
        if self.queue_empty:
            return
        
        # Get next song (without removing from queue)
        try:
            next_song = self.queue[0]
        except IndexError:
            return

        # Only extract if pending
        if next_song.source == "pending" and next_song.url:
            logger.info(f"🔄 Pre-loading: {next_song.title[:40]}...")
            
            try:
                audio_url = await self.extract_audio_url(next_song.url)
                if audio_url:
                    next_song.source = audio_url
                    logger.info(f"✅ Pre-loaded: {next_song.title[:40]}")
                else:
                    logger.warning(f"⚠️ Pre-load failed: {next_song.title[:40]}")
            except Exception as e:
                logger.error(f"Pre-load error: {e}")


    async def _idle_disconnect(self):
        try:
            await asyncio.sleep(60)
            
            async with self._voice_lock:
                # Double-check: only disconnect if still idle AND connected
                if not self.is_playing and not self.queue:
                    if self.voice_client and self.voice_client.is_connected():
                        logger.info(f"Idle timeout reached in {self.guild.name}, disconnecting.")
                        await self._do_disconnect()

        except asyncio.CancelledError:
            pass



    
    
    async def play_song(self, song: Song):
        """Play a song with INSTANT start"""

        if not self.voice_client:
            logger.error("No voice client")
            return
        
        # STRICT: Verify voice is actually connected before playing
        if not self.voice_client.is_connected():
            logger.error("Voice client exists but not connected, cannot play")
            return
        
        # Cancel idle timer if playing again
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()


        # ✅ LAZY EXTRACTION with feedback
        if not song.source or song.source == "pending":
            # Show extracting indicator
            extracting_msg = None
            if self.text_channel:
                try:
                    embed = discord.Embed(
                        description=f"⏳ Preparing: **{song.title[:50]}...**",
                        color=0x3498db
                    )
                    extracting_msg = await self.text_channel.send(embed=embed)
                except:
                    pass
            
            logger.info(f"⏳ Extracting: {song.title[:50]}")
            
            if song.url:
                audio_url = await self.extract_audio_url(song.url)
                
                # Delete extracting message
                if extracting_msg:
                    try:
                        await extracting_msg.delete()
                    except:
                        pass
                
                if audio_url:
                    song.source = audio_url
                    logger.info(f"✓ Extracted: {song.title[:50]}")
                else:
                    logger.error(f"❌ Extraction failed: {song.title}")
                    if self.text_channel:
                        embed = discord.Embed(
                            description=f"❌ Failed to extract: **{song.title[:50]}**",
                            color=0xe74c3c
                        )
                        await self.text_channel.send(embed=embed, delete_after=10)
                    await self.play_next()
                    return
            else:
                await self.play_next()
                return

        if not song or not song.source:
            await self.play_next()
            return

        self.current = song
        

        try:
            logger.info(f"▶ Playing: {song.title[:50]}")
            source = discord.FFmpegPCMAudio(song.source, **FFMPEG_OPTS)
            source = discord.PCMVolumeTransformer(source, volume=self.volume)

            self.voice_client.play(source, after=lambda e: self._after_play(e))

            # Delete old controller
            await self.delete_controller()

            # Send new controller
            if self.text_channel:
                try:
                    try:
                        from ui import MusicEmbeds, MusicControlsView
                    except ImportError:
                        from cogs.music.ui import MusicEmbeds, MusicControlsView

                    embed = MusicEmbeds.now_playing(song, requester=song.requester)
                    view = MusicControlsView(self, timeout=300, auto_delete=False)
                    message = await self.text_channel.send(embed=embed, view=view)
                    view.message = message
                    self.controller_message = message
                except Exception as e:
                    logger.error(f"Controller error: {e}")
            
            # ✅ START PRE-LOADING NEXT SONG (background)
            # Cancel previous preload task if running
            if self._preload_task and not self._preload_task.done():
                self._preload_task.cancel()
            try:
                await self._preload_task
            except:
                pass

            # Start new preload task
            if not self.queue_empty:
                self._preload_task = asyncio.create_task(self._preload_next_song())


        except Exception as e:
            logger.error(f"Playback error: {e}")
            if self.text_channel:
                await self.text_channel.send(f"❌ Error: **{song.title[:50]}**")
            await self.play_next()

    def _after_play(self, error):
        """Called after a song finishes"""
        if error:
            logger.error(f"Player error: {error}")

        if not self.bot.is_closed():
            asyncio.run_coroutine_threadsafe(self.play_next(), self.bot.loop)

    async def play_next(self):
        """Play the next song (pre-loaded = INSTANT)"""
        if self.loop and self.current:
            self.queue.appendleft(self.current)

        finished_song = self.current

        if not self.queue:
            
            self.current = None

            # 🔥 Start idle disconnect timer
            if self._idle_task and not self._idle_task.done():
                self._idle_task.cancel()

            self._idle_task = asyncio.create_task(self._idle_disconnect())

            await self.delete_controller()


            if self.text_channel and finished_song:
                try:
                    embed = discord.Embed(
                        description=f"### ✅ Finished\n**{finished_song.title}**\n\n*Queue empty. Use `/play` to add more!*",
                        color=0x00D9A3
                    )
                    await self.text_channel.send(embed=embed, delete_after=15)
                except:
                    pass

            return

        # Delete old controller
        await self.delete_controller()

        # Get next song (pre-loaded = INSTANT)
        next_song = self.queue.popleft()
        
        # Play next song
        await self.play_song(next_song)
    
    async def delete_controller(self):
        """Delete the controller message if it exists"""
        if self.controller_message:
            try:
                await self.controller_message.delete()
            except:
                pass
            self.controller_message = None
    
    async def pause(self):
        """Pause playback"""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            return True
        return False
    
    async def resume(self):
        """Resume playback"""
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            return True
        return False
    
    def set_volume(self, volume: int):
        """
        Set the volume for playback.
        
        Args:
            volume: Volume level as percentage (0-100)
        """
        # Convert to float (0.0 - 1.0)
        self.volume = max(0.0, min(1.0, volume / 100.0))
        
        # Update volume for currently playing source if available
        if self.voice_client and self.voice_client.source:
            if hasattr(self.voice_client.source, 'volume'):
                self.voice_client.source.volume = self.volume
    
    def shuffle_queue(self):
        """Shuffle the queue randomly"""
        if len(self.queue) > 1:
            # Convert deque to list, shuffle, then convert back
            queue_list = list(self.queue)
            import random
            random.shuffle(queue_list)
            self.queue = deque(queue_list)
    
    def clear_queue(self):
        """Clear all songs from the queue"""
        self.queue.clear()
    
    async def skip(self):
        async with self._voice_lock:
            """Skip current song"""
            if self.voice_client and self.voice_client.is_playing():
                self.voice_client.stop()
                return True
            return False
    
    async def stop(self):
        async with self._voice_lock:
            """Stop playback and clear queue"""
            if self.voice_client:
                self.voice_client.stop()

                # Cancel preload task
                if self._preload_task and not self._preload_task.done():
                    self._preload_task.cancel()
                    try:
                        await self._preload_task
                    except:
                        pass
                    
                # Cancel idle task
                if self._idle_task and not self._idle_task.done():
                    self._idle_task.cancel()
                    try:
                        await self._idle_task
                    except:
                        pass
                    
                self.queue.clear()
                self.current = None

                await self.disconnect()
                return True
            return False
    
    async def add_to_queue(self, song: Song):
        """Add song to queue and auto-play if idle"""
        
        if not self.is_playing and not self.is_paused and not self.current:
            # Play immediately if nothing is playing
            await self.play_song(song)
            return 0
        else:
            self.queue.append(song)
            return len(self.queue)
    
    async def check_empty_channel(self):
        async with self._voice_lock:
            # Check if voice channel is empty and disconnect if needed
            if self.voice_client and self.voice_client.channel:
                members = self.voice_client.channel.members
                bot_member = self.bot.user
                other_members = [m for m in members if m != bot_member]
                
                if not other_members:
                    logger.info(f"No members left in {self.guild.name}, disconnecting.")
                    # Use _do_disconnect to avoid deadlock (lock already held)
                    await self._do_disconnect()
