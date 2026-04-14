"""
Fast Player - Optimized for 3-5 second playback start
✅ Stream-based playback (no buffering)
✅ Parallel extraction & connection
✅ Immediate playback of first song
✅ Background loading of next songs
"""

import asyncio
import logging
from typing import Optional, Callable, Tuple, Dict, Any
import discord
import yt_dlp

logger = logging.getLogger('discord.music.player')

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -bufsize 512k -ar 48000 -ac 2 -b:a 128k'
}


class FastPlayer:
    """
    Optimized player for fast playback
    - Starts playing within 3-5 seconds
    - Parallel operations (connect + extract simultaneously)
    - Stream-based audio (no full buffer)
    """
    
    def __init__(
        self,
        bot,
        queue_manager,
        preloader,
        ydl_opts: Optional[Dict[str, Any]] = None
    ):
        self.bot = bot
        self.queue_manager = queue_manager
        self.preloader = preloader
        self.ydl_opts = ydl_opts or {}
        
        # Guild players
        self.players: Dict[int, 'GuildPlayer'] = {}
    
    def get_player(self, guild_id: int) -> 'GuildPlayer':
        """Get or create player for guild"""
        if guild_id not in self.players:
            self.players[guild_id] = GuildPlayer(
                guild_id,
                self.bot,
                self.queue_manager,
                self.preloader,
                self.ydl_opts
            )
        return self.players[guild_id]
    
    async def disconnect_player(self, guild_id: int) -> None:
        """Disconnect and cleanup player"""
        if guild_id in self.players:
            player = self.players[guild_id]
            await player.disconnect()
            del self.players[guild_id]


class GuildPlayer:
    """Player for a single guild"""
    
    def __init__(
        self,
        guild_id: int,
        bot,
        queue_manager,
        preloader,
        ydl_opts: Dict[str, Any]
    ):
        self.guild_id = guild_id
        self.bot = bot
        self.queue_manager = queue_manager
        self.preloader = preloader
        self.ydl_opts = ydl_opts
        
        self.voice_client: Optional[discord.VoiceClient] = None
        self.is_playing = False
        self.current_song = None
    
    async def connect(self, channel: discord.VoiceChannel) -> Tuple[bool, str]:
        """
        Connect to voice channel (fast)
        Returns: (success, message)
        """
        try:
            if self.voice_client and self.voice_client.is_connected():
                if self.voice_client.channel.id == channel.id:
                    return True, "Already connected"
                await self.voice_client.move_to(channel)
                return True, f"Moved to {channel.name}"
            
            logger.info(f"Connecting to {channel.name}...")
            self.voice_client = await asyncio.wait_for(
                channel.connect(self_deaf=True, self_mute=False),
                timeout=5.0
            )
            logger.info(f"✓ Connected to {channel.name}")
            return True, f"Connected to {channel.name}"
            
        except asyncio.TimeoutError:
            logger.error("Connection timeout")
            return False, "❌ Connection timeout (>5s)"
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False, f"❌ Connection failed: {str(e)[:50]}"
    
    async def play_song_fast(
        self,
        ctx,
        url_or_search: str
    ) -> Tuple[bool, str]:
        """
        Play song with <5 second startup
        Strategy:
        1. Connect to voice (async)
        2. Extract audio URL in parallel (async)
        3. Play immediately when both ready
        Returns: (success, message)
        """
        # Step 0: Validate
        if not ctx.author.voice or not ctx.author.voice.channel:
            return False, "❌ You must be in a voice channel"
        
        channel = ctx.author.voice.channel
        queue = self.queue_manager.get_queue(self.guild_id)
        queue.is_playing = True
        
        try:
            # ========== PARALLEL OPERATIONS ==========
            # 1. Connect to voice (can take 2-3 sec)
            # 2. Extract audio URL (can take 2-3 sec)
            # Both happen simultaneously!
            
            logger.info(f"▶️ Starting fast playback: {url_or_search[:50]}")
            start_time = asyncio.get_event_loop().time()
            
            # Step 1: Connect (non-blocking)
            connect_task = asyncio.create_task(self.connect(channel))
            
            # Step 2: Extract audio (non-blocking)
            extract_task = asyncio.create_task(
                self._fast_extract(url_or_search)
            )
            
            # Wait for both, but optimize for speed
            results = await asyncio.gather(
                connect_task,
                extract_task,
                return_exceptions=True
            )
            
            # Check connection
            if isinstance(results[0], tuple):
                connected, conn_msg = results[0]
                if not connected:
                    return False, conn_msg
            else:
                return False, f"Connection error: {results[0]}"
            
            # Check extraction
            if isinstance(results[1], Exception):
                return False, f"Extraction error: {results[1]}"
            
            song_info, audio_url = results[1]
            if not audio_url:
                return False, "❌ Failed to extract audio URL"
            
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.info(f"Ready to play in {elapsed:.1f}s")
            
            # Step 3: Play immediately
            success, msg = await self._play_audio(
                audio_url,
                song_info
            )
            
            if success:
                total_time = asyncio.get_event_loop().time() - start_time
                logger.info(f"🎵 Playback started in {total_time:.1f}s")
            
            return success, msg
            
        except Exception as e:
            logger.error(f"Play error: {e}")
            return False, f"❌ Playback error: {str(e)[:50]}"
    
    async def _fast_extract(
        self,
        url_or_search: str
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Fast extraction optimized for speed
        Returns: (song_info, audio_url)
        """
        try:
            # Extract in executor (non-blocking)
            def extract():
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    info = ydl.extract_info(url_or_search, download=False)
                    
                    # Handle search results
                    if info.get('_type') == 'playlist' and info.get('entries'):
                        info = info['entries'][0]
                    
                    return info
            
            logger.debug(f"Extracting: {url_or_search[:50]}")
            info = await asyncio.wait_for(
                self.bot.loop.run_in_executor(None, extract),
                timeout=10.0
            )
            
            # Extract audio URL
            audio_url = self._get_best_audio_url(info)
            
            song_info = {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'url': info.get('webpage_url') or info.get('url'),
                'id': info.get('id')
            }
            
            return song_info, audio_url
            
        except asyncio.TimeoutError:
            logger.error("Extraction timeout")
            raise TimeoutError("YouTube timeout - try another video")
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            raise
    
    async def _play_audio(
        self,
        audio_url: str,
        song_info: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Start playing audio stream
        Returns: (success, message)
        """
        try:
            if not self.voice_client or not self.voice_client.is_connected():
                return False, "❌ Not connected to voice"
            
            # Create audio source
            audio_source = discord.FFmpegPCMAudio(
                audio_url,
                **FFMPEG_OPTIONS
            )
            
            def after_playback(error):
                if error:
                    logger.error(f"Playback error: {error}")
                else:
                    logger.info(f"✅ Finished: {song_info['title']}")
                # Trigger next song play
                asyncio.run_coroutine_threadsafe(
                    self.play_next(),
                    self.bot.loop
                )
            
            # Play!
            self.voice_client.play(audio_source, after=after_playback)
            self.is_playing = True
            self.current_song = song_info
            
            duration_str = f"{song_info['duration']//60}:{song_info['duration']%60:02d}"
            msg = f"🎵 Playing: {song_info['title']} ({duration_str})"
            logger.info(msg)
            
            return True, msg
            
        except Exception as e:
            logger.error(f"Playback setup error: {e}")
            return False, f"❌ Playback error: {str(e)[:50]}"
    
    def _get_best_audio_url(self, info: Dict[str, Any]) -> Optional[str]:
        """Extract best audio URL"""
        if info.get('url') and isinstance(info['url'], str):
            url = str(info['url']).strip()
            if url.startswith('http'):
                return url
        
        if info.get('formats'):
            for fmt in info['formats']:
                if (fmt.get('acodec') and fmt.get('acodec') != 'none' and
                    (not fmt.get('vcodec') or fmt.get('vcodec') == 'none') and
                    fmt.get('url')):
                    return fmt['url']
            
            for fmt in info['formats']:
                if fmt.get('acodec') and fmt.get('acodec') != 'none' and fmt.get('url'):
                    return fmt['url']
        
        return None
    
    async def play_next(self) -> None:
        """Play next song in queue"""
        queue = self.queue_manager.get_queue(self.guild_id)
        
        # Skip to next
        next_song = self.queue_manager.skip(self.guild_id)
        if not next_song:
            self.is_playing = False
            logger.info("Queue empty, stopping playback")
            return
        
        # Extract if needed
        if not next_song.is_extracted and next_song.url:
            logger.debug(f"Extracting next song: {next_song.title}")
            audio_url = await self.preloader.preload_song(
                next_song.url,
                self.bot.loop
            )
            if audio_url:
                next_song.audio_url = audio_url
                next_song.is_extracted = True
        
        # Play
        if next_song.audio_url:
            await self._play_audio(
                next_song.audio_url,
                {'title': next_song.title, 'duration': next_song.duration}
            )
    
    async def disconnect(self) -> None:
        """Disconnect from voice"""
        if self.voice_client:
            try:
                if self.voice_client.is_playing():
                    self.voice_client.stop()
                await self.voice_client.disconnect()
            except Exception as e:
                logger.debug(f"Disconnect error: {e}")
            finally:
                self.voice_client = None
                self.is_playing = False
        
        logger.info(f"Disconnected from guild {self.guild_id}")
    
    async def pause(self) -> bool:
        """Pause playback"""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            return True
        return False
    
    async def resume(self) -> bool:
        """Resume playback"""
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            return True
        return False
