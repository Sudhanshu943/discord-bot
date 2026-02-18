"""
Player Manager Module - ULTRA-FAST VERSION
✅ Pre-extraction for instant playback
✅ Background pre-loading for next songs
✅ Optimized FFmpeg for low latency
✅ Opus codec preference
"""

import discord
import yt_dlp
import logging
import asyncio
import concurrent.futures
from typing import Optional, Dict, Any
from collections import deque
from datetime import datetime


logger = logging.getLogger('discord.music.player')

# ✅ OPTIMIZED YT-DLP options for SPEED + Opus preference
YDL_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'cookiefile': './cookies.txt',
    'js_runtimes': {
        'node': {}
    }
}

# ✅ OPTIMIZED FFmpeg options for LOW LATENCY
FFMPEG_OPTS = {
    'before_options': (
        '-reconnect 1 '
        '-reconnect_streamed 1 '
        '-reconnect_delay_max 5 '
        '-analyzeduration 0 '           # Skip analysis
        '-probesize 32 '                # Minimal probe
        '-fflags nobuffer'              # No buffering
    ),
    'options': (
        '-vn '                          # No video
        '-bufsize 512k '                # Small buffer
        '-ar 48000 '                    # 48kHz sample rate
        '-ac 2 '                        # Stereo
        '-b:a 128k'                     # 128kbps bitrate
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

class MusicPlayer:
    """
    Manages music playback with SPEED OPTIMIZATIONS
    ✅ Pre-extraction
    ✅ Background pre-loading
    ✅ Low latency FFmpeg
    """
    
    def __init__(self, guild: discord.Guild, bot):
        self.guild = guild
        self.bot = bot
        self.voice_client: discord.VoiceClient = None
        self.queue: deque = deque()
        self.current: Song = None
        self.volume: float = 0.5
        self.loop: bool = False
        self._is_playing: bool = False
        self.text_channel: discord.TextChannel = None
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)  # Increased workers
        self.controller_message: discord.Message = None
        self._preload_task: Optional[asyncio.Task] = None  # Track pre-loading task
    
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
    
    async def connect(self, channel: discord.VoiceChannel) -> bool:
        """Connect to a voice channel"""
        try:
            if self.voice_client:
                await self.voice_client.move_to(channel)
            else:
                self.voice_client = await channel.connect()
            logger.info(f"✓ Connected to {channel.name}")
            return True
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from voice"""
        # Cancel pre-loading task
        if self._preload_task and not self._preload_task.done():
            self._preload_task.cancel()
        
        if self.voice_client:
            await self.voice_client.disconnect()
            self.voice_client = None
        self.queue.clear()
        self.current = None
        self._is_playing = False
        logger.info(f"Disconnected from {self.guild.name}")
    
    async def extract_audio_url(self, url: str, fast: bool = False) -> Optional[str]:
        """
        Extract audio URL with SPEED optimization
        Args:
            fast: If True, prefer speed over quality
        """
        loop = asyncio.get_event_loop()
        
        def _extract():
            opts = YDL_OPTS.copy()
            if fast:
                opts['format'] = 'worstaudio/worst'  # Fastest extraction
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        try:
            info = await loop.run_in_executor(self.executor, _extract)
            
            if not info:
                return None
            
            return self._get_audio_url(info)
            
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
        next_song = list(self.queue)[0]
        
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
    
    async def play_song(self, song: Song):
        """Play a song with INSTANT start"""
        if not self.voice_client:
            logger.error("No voice client")
            return

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
        self._is_playing = True

        try:
            logger.info(f"▶ Playing: {song.title[:50]}")
            source = discord.FFmpegPCMAudio(song.source, **FFMPEG_OPTS)
            source = discord.PCMVolumeTransformer(source, volume=self.volume)

            self.voice_client.play(source, after=lambda e: self._after_play(e))

            # Delete old controller
            if self.controller_message:
                try:
                    await self.controller_message.delete()
                except:
                    pass
                self.controller_message = None

            # Send new controller
            if self.text_channel:
                try:
                    try:
                        from .ui import MusicEmbeds, MusicControlsView
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

        asyncio.run_coroutine_threadsafe(self.play_next(), self.bot.loop)

    async def play_next(self):
        """Play the next song (pre-loaded = INSTANT)"""
        if self.loop and self.current:
            self.queue.appendleft(self.current)

        finished_song = self.current

        if not self.queue:
            self._is_playing = False
            self.current = None

            if self.controller_message:
                try:
                    await self.controller_message.delete()
                except:
                    pass
                self.controller_message = None

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
        if self.controller_message:
            try:
                await self.controller_message.delete()
            except:
                pass
            self.controller_message = None

        # ✅ Play next song (likely already pre-loaded = INSTANT)
        if self.queue:
            song = self.queue.popleft()
            await self.play_song(song)
    
    async def add_to_queue(self, song: Song) -> int:
        """Add song to queue (returns 0 if playing immediately)"""
        if not self.is_playing and not self.is_paused:
            await self.play_song(song)
            return 0
        else:
            self.queue.append(song)
            return len(self.queue)
    
    async def pause(self):
        """Pause playback"""
        if self.voice_client:
            self.voice_client.pause()
    
    async def resume(self):
        """Resume playback"""
        if self.voice_client:
            self.voice_client.resume()
    
    async def skip(self) -> Optional[Song]:
        """Skip current song"""
        if self.voice_client:
            self.voice_client.stop()
        return self.current
    
    async def stop(self):
        """Stop playback and clear queue"""
        self.queue.clear()
        if self.voice_client:
            self.voice_client.stop()
        self.current = None
        self._is_playing = False
    
    def set_volume(self, volume: int):
        """Set volume (0-100)"""
        self.volume = volume / 100
        if self.voice_client and self.voice_client.source:
            self.voice_client.source.volume = self.volume
    
    def get_queue_list(self, limit: int = 10) -> list:
        """Get queue as list"""
        return list(self.queue)[:limit]
    
    def clear_queue(self):
        """Clear the queue"""
        self.queue.clear()
    
    def shuffle_queue(self):
        """Shuffle the queue"""
        import random
        items = list(self.queue)
        random.shuffle(items)
        self.queue = deque(items)
    
    def remove_from_queue(self, position: int) -> Optional[Song]:
        """Remove song at position (1-based)"""
        if position < 1 or position > len(self.queue):
            return None
        
        items = list(self.queue)
        removed = items.pop(position - 1)
        self.queue = deque(items)
        return removed

class PlayerManager:
    """Manages MusicPlayer instances for all guilds"""
    
    def __init__(self, bot):
        self.bot = bot
        self.players: Dict[int, MusicPlayer] = {}
    
    def get_player(self, guild: discord.Guild) -> MusicPlayer:
        """Get or create a player for a guild"""
        if guild.id not in self.players:
            self.players[guild.id] = MusicPlayer(guild, self.bot)
        return self.players[guild.id]
    
    async def connect_to_voice(self, channel: discord.VoiceChannel) -> MusicPlayer:
        """Connect to a voice channel"""
        player = self.get_player(channel.guild)
        await player.connect(channel)
        return player
    
    async def disconnect(self, guild: discord.Guild):
        """Disconnect from a guild"""
        try:
            if guild.id in self.players:
                await self.players[guild.id].disconnect()
                del self.players[guild.id]
                logger.info(f"Disconnected from {guild.name} (ID: {guild.id})")
        except KeyError:
            logger.debug(f"No active player to disconnect for guild {guild.id}")
        except Exception as e:
            logger.error(f"Error disconnecting from {guild.name}: {e}")
    
    def remove_player(self, guild_id: int):
        """Remove player for a guild"""
        if guild_id in self.players:
            del self.players[guild_id]
