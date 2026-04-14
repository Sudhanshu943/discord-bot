"""
Simple Music Cog - Complete & Self-Contained
✅ Fast audio extraction (yt-dlp)
✅ Non-blocking via executor
✅ Per-guild queuing
✅ Timeout protection (Railway safe)
✅ No complex dependencies
✅ Works out of the box!
"""

import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
import logging
from typing import Optional
from collections import deque
from music.services.search_service import SearchService

logger = logging.getLogger('discord.music')

# ==================== CONFIGURATION ====================
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'default_search': 'ytsearch',
    'noplaylist': True,                    # ⭐ CRITICAL: Only first video
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
    'EXTRACTION': 10.0,                    # Max extraction time
    'VOICE_CONNECT': 5.0,                  # Max connection time
}


# ==================== SIMPLE SONG CLASS ====================
class Song:
    """Lightweight song data"""
    def __init__(self, url: str, title: str, duration: int):
        self.url = url
        self.title = title
        self.duration = duration
    
    def duration_str(self):
        """Format duration as MM:SS"""
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"


# ==================== MAIN MUSIC COG ====================
class Music(commands.Cog):
    """
    Fast, simple music cog for Discord
    Uses yt-dlp for direct YouTube extraction
    Railway optimized with timeout protection
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}  # guild_id -> deque of Song objects
        self.current_playing = {}  # guild_id -> currently playing Song
        self.is_playing = {}  # guild_id -> bool (is playback active)
        self.voice_clients = {}  # guild_id -> voice_client for tracking
        self.search_service = SearchService(bot)  # Advanced search with scoring
        self.synced = False
        logger.info("🎵 Music Cog initialized (Fast & Simple)")
    
    async def cog_unload(self):
        """Cleanup on unload"""
        logger.info("🛑 Music cog unloaded")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Sync slash commands when bot is ready"""
        if not self.synced:
            try:
                await self.bot.tree.sync()
                logger.info("✅ Slash commands synced")
                self.synced = True
            except Exception as e:
                logger.error(f"Failed to sync commands: {e}")
    
    # ==================== HELPER METHODS ====================
    
    def get_queue(self, guild_id: int) -> deque:
        """Get or create queue for guild"""
        if guild_id not in self.queues:
            self.queues[guild_id] = deque(maxlen=50)  # Max 50 songs
        return self.queues[guild_id]
    
    def add_to_queue(self, guild_id: int, song: Song) -> int:
        """Add song to queue, return position"""
        queue = self.get_queue(guild_id)
        queue.append(song)
        return len(queue)
    
    def get_current(self, guild_id: int) -> Optional[Song]:
        """Get currently playing song"""
        return self.current_playing.get(guild_id)
    
    def set_current(self, guild_id: int, song: Optional[Song]) -> None:
        """Set currently playing song"""
        self.current_playing[guild_id] = song
    
    def get_next_queued(self, guild_id: int) -> Optional[Song]:
        """Get next song from queue without removing"""
        queue = self.get_queue(guild_id)
        return queue[0] if queue else None
    
    def pop_next_queued(self, guild_id: int) -> Optional[Song]:
        """Remove and return next song from queue"""
        queue = self.get_queue(guild_id)
        return queue.popleft() if queue else None
    
    def clear_queue(self, guild_id: int) -> None:
        """Clear entire queue"""
        queue = self.get_queue(guild_id)
        queue.clear()
        logger.info(f"Queue cleared for guild {guild_id}")
    
    def get_queue_info(self, guild_id: int) -> dict:
        """Get queue info for display"""
        queue = self.get_queue(guild_id)
        current = self.get_current(guild_id)
        return {
            'current': current,
            'queue_length': len(queue),
            'queue_songs': list(queue),
            'is_playing': self.is_playing.get(guild_id, False)
        }
    
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
                        logger.debug("Found audio-only format")
                        return fmt_url
            
            # Fallback to any audio format
            for fmt in info['formats']:
                if isinstance(fmt, dict):
                    acodec = fmt.get('acodec', '')
                    fmt_url = fmt.get('url', '')
                    if acodec and acodec != 'none' and fmt_url:
                        logger.debug("Found audio format")
                        return fmt_url
        
        # Check requested_formats
        if info.get('requested_formats') and isinstance(info['requested_formats'], list):
            for fmt in info['requested_formats']:
                if isinstance(fmt, dict):
                    fmt_url = fmt.get('url', '')
                    if fmt_url:
                        logger.debug("Found URL in requested_formats")
                        return fmt_url
        
        logger.warning(f"Could not extract audio URL. Info keys: {list(info.keys())}")
        return None
    
    async def extract_info(self, url_or_search: str) -> Optional[dict]:
        """
        Extract song info from YouTube with intelligent search
        - For search queries: uses scoring system to find best quality
        - For direct URLs: extracts directly
        Non-blocking via executor, with timeout protection
        """
        try:
            # Check if it's a direct URL
            is_url = url_or_search.startswith('http') or url_or_search.startswith('www')
            
            if is_url:
                # Direct URL - extract directly
                logger.debug("Direct URL detected - extracting...")
                def _extract_direct():
                    try:
                        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                            info = ydl.extract_info(url_or_search, download=False)
                            if not info:
                                return None
                            video_info = info if info.get('_type') != 'playlist' else info['entries'][0]
                            audio_url = self._get_best_audio_url(video_info)
                            return {
                                'url': audio_url,
                                'title': video_info.get('title', 'Unknown'),
                                'duration': video_info.get('duration', 0),
                            }
                    except Exception as e:
                        logger.error(f"Direct extraction failed: {e}")
                        return None
                
                info = await asyncio.wait_for(
                    self.bot.loop.run_in_executor(None, _extract_direct),
                    timeout=TIMEOUTS['EXTRACTION']
                )
            else:
                # Search query - use smart search with scoring
                logger.debug("Search query detected - using intelligent search...")
                search_result = await self.search_service.smart_search(url_or_search)
                
                if not search_result:
                    logger.warning(f"❌ No search results found for: {url_or_search[:50]}")
                    return None
                
                logger.debug(f"Search result: {search_result['title'][:50]} (score: {search_result.get('score', '?')})")
                
                # Now extract the best result URL with retry logic
                def _extract_search():
                    try:
                        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                            logger.debug(f"Extracting audio from: {search_result['url'][:50]}")
                            info = ydl.extract_info(search_result['url'], download=False)
                            if not info:
                                logger.error(f"No info returned for: {search_result['url']}")
                                return None
                            audio_url = self._get_best_audio_url(info)
                            if not audio_url:
                                logger.error(f"No audio URL found in info")
                                return None
                            return {
                                'url': audio_url,
                                'title': search_result['title'],
                                'duration': search_result['duration'],
                                'channel': search_result.get('channel', 'Unknown'),
                                'score': search_result.get('score', 0),
                            }
                    except Exception as e:
                        logger.error(f"Search extraction failed: {e}")
                        return None
                
                info = await asyncio.wait_for(
                    self.bot.loop.run_in_executor(None, _extract_search),
                    timeout=TIMEOUTS['EXTRACTION']
                )
            
            if not info or not info.get('url'):
                logger.warning(f"❌ No audio URL found for: {url_or_search[:50]}")
                return None
            
            logger.info(f"✅ Extracted: {info['title'][:50]} | {info['duration']}s")
            return info
        except asyncio.TimeoutError:
            logger.warning(f"❌ Extraction timeout (>{TIMEOUTS['EXTRACTION']:.0f}s) for: {url_or_search[:50]}")
            return None
        except Exception as e:
            logger.error(f"❌ Extraction error: {e}")
            return None
    
    # ==================== PLAY COMMAND ====================
    
    @commands.command(name='play', help='Play music from YouTube')
    async def play(self, ctx, *, url_or_search: str):
        """
        Play a song from YouTube URL or search query
        Usage:
            !play https://www.youtube.com/watch?v=...
            !play Adele Someone Like You
        """
        
        # Check if user is in voice channel
        if not ctx.author.voice or not ctx.author.voice.channel:
            embed = discord.Embed(
                title="❌ Error",
                description="You must be in a voice channel to use this command!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        channel = ctx.author.voice.channel
        
        # Show loading message only if not already connected
        already_connected = ctx.voice_client is not None and ctx.voice_client.is_connected()
        if not already_connected:
            loading_msg = await ctx.send(
                embed=discord.Embed(
                    title="🔄 Loading...",
                    description=f"Connecting to {channel.mention} and extracting audio...",
                    color=discord.Color.blue()
                )
            )
        else:
            loading_msg = await ctx.send(
                embed=discord.Embed(
                    title="🔄 Extracting audio...",
                    description=f"From {channel.mention}",
                    color=discord.Color.blue()
                )
            )
        
        try:
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
                embed = discord.Embed(
                    title="❌ Connection Timeout",
                    description=f"Failed to connect to voice channel (>{TIMEOUTS['VOICE_CONNECT']:.0f}s)",
                    color=discord.Color.red()
                )
                await loading_msg.edit(embed=embed)
                logger.error("Voice connection timeout")
                return
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Connection Error",
                    description=f"Failed to connect: {str(e)[:100]}",
                    color=discord.Color.red()
                )
                await loading_msg.edit(embed=embed)
                logger.error(f"Connection error: {e}")
                return
            
            # ==================== STEP 2: EXTRACT AUDIO ====================
            logger.info(f"Extracting: {url_or_search[:50]}")
            info = await self.extract_info(url_or_search)
            
            if not info:
                embed = discord.Embed(
                    title="❌ Extraction Failed",
                    description=f"Could not extract audio. Check your internet or try another video.",
                    color=discord.Color.red()
                )
                await loading_msg.edit(embed=embed)
                return
            
            # ==================== STEP 3: PLAY ====================
            try:
                url = info['url']
                title = info['title']
                duration = info['duration']
                
                # Verify URL is valid
                if not url or not isinstance(url, str):
                    raise ValueError("Invalid audio URL")
                
                duration_str = f"{duration // 60}:{duration % 60:02d}"
                
                # Create song object
                song = Song(url=url, title=title, duration=duration)
                
                # Check if already playing
                if voice_client.is_playing() or self.is_playing.get(ctx.guild.id, False):
                    # Queue this song
                    position = self.add_to_queue(ctx.guild.id, song)
                    embed = discord.Embed(
                        title="📝 Queued",
                        description=f"{title}\nPosition: #{position}",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Duration", value=duration_str, inline=False)
                    await loading_msg.edit(embed=embed)
                    logger.info(f"Queued: {title} (position {position})")
                    return
                
                # Create audio source
                audio_source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
                
                # Track playback state
                self.set_current(ctx.guild.id, song)
                self.is_playing[ctx.guild.id] = True
                self.voice_clients[ctx.guild.id] = voice_client
                
                def after_play(error):
                    if error:
                        logger.error(f"Playback error: {error}")
                    else:
                        logger.info(f"✅ Finished: {title[:50]}")
                    
                    # Play next song from queue
                    asyncio.run_coroutine_threadsafe(
                        self.play_next_from_queue(ctx.guild.id, voice_client),
                        self.bot.loop
                    )
                
                # Play!
                voice_client.play(audio_source, after=after_play)
                
                logger.info(f"▶️ Playing: {title} ({duration_str})")
                
                # Update status
                embed = discord.Embed(
                    title="🎵 Now Playing",
                    description=title[:256],
                    color=discord.Color.green()
                )
                embed.add_field(name="Duration", value=duration_str, inline=False)
                embed.add_field(name="Channel", value=f"<#{channel.id}>", inline=False)
                await loading_msg.edit(embed=embed)
                
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Playback Error",
                    description=f"Failed to start playback: {str(e)[:100]}",
                    color=discord.Color.red()
                )
                await loading_msg.edit(embed=embed)
                logger.error(f"Playback error: {e}")
                return
        
        except Exception as e:
            logger.error(f"Unexpected error in play command: {e}")
            embed = discord.Embed(
                title="❌ Unexpected Error",
                description=str(e)[:256],
                color=discord.Color.red()
            )
            try:
                await loading_msg.edit(embed=embed)
            except:
                await ctx.send(embed=embed)
    
    @app_commands.command(name="play", description="Play music from YouTube")
    @app_commands.describe(query="YouTube URL or search query")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        """Play music (slash command)"""
        # CRITICAL: Defer immediately before ANY other operations (3 second timeout)
        try:
            await interaction.response.defer()
        except Exception as e:
            logger.error(f"Failed to defer interaction: {e}")
            return
        
        # Check if user is in voice channel
        if not interaction.user.voice or not interaction.user.voice.channel:
            embed = discord.Embed(
                title="❌ Error",
                description="You must be in a voice channel to use this command!",
                color=discord.Color.red()
            )
            try:
                await interaction.followup.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to send followup: {e}")
            return
        
        channel = interaction.user.voice.channel
        
        # Show loading message only if not already connected
        already_connected = interaction.guild.voice_client is not None and interaction.guild.voice_client.is_connected()
        if not already_connected:
            loading_response = await interaction.followup.send(
                embed=discord.Embed(
                    title="🔄 Loading...",
                    description=f"Connecting to {channel.mention} and extracting audio...",
                    color=discord.Color.blue()
                )
            )
        else:
            loading_response = await interaction.followup.send(
                embed=discord.Embed(
                    title="🔄 Extracting audio...",
                    description=f"From {channel.mention}",
                    color=discord.Color.blue()
                )
            )
        
        try:
            # ==================== STEP 1: CONNECT ====================
            try:
                if interaction.guild.voice_client is None:
                    logger.info(f"Connecting to: {channel}")
                    voice_client = await asyncio.wait_for(
                        channel.connect(),
                        timeout=TIMEOUTS['VOICE_CONNECT']
                    )
                else:
                    voice_client = interaction.guild.voice_client
                    if voice_client.channel != channel:
                        await asyncio.wait_for(
                            voice_client.move_to(channel),
                            timeout=TIMEOUTS['VOICE_CONNECT']
                        )
            except asyncio.TimeoutError:
                embed = discord.Embed(
                    title="❌ Connection Timeout",
                    description=f"Failed to connect to voice channel (>{TIMEOUTS['VOICE_CONNECT']:.0f}s)",
                    color=discord.Color.red()
                )
                try:
                    await interaction.followup.send(embed=embed)
                except:
                    pass  # Interaction expired
                logger.error("Voice connection timeout")
                return
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Connection Error",
                    description=f"Failed to connect: {str(e)[:100]}",
                    color=discord.Color.red()
                )
                try:
                    await interaction.followup.send(embed=embed)
                except:
                    pass  # Interaction expired
                logger.error(f"Connection error: {e}")
                return
            
            # ==================== STEP 2: EXTRACT AUDIO ====================
            logger.info(f"Extracting: {query[:50]}")
            info = await self.extract_info(query)
            
            if not info:
                embed = discord.Embed(
                    title="❌ Extraction Failed",
                    description=f"Could not extract audio. Check your internet or try another video.",
                    color=discord.Color.red()
                )
                try:
                    await interaction.followup.send(embed=embed)
                except:
                    pass  # Interaction expired
                return
            
            # ==================== STEP 3: PLAY ====================
            try:
                url = info['url']
                title = info['title']
                duration = info['duration']
                
                # Verify URL is valid
                if not url or not isinstance(url, str):
                    raise ValueError("Invalid audio URL")
                
                duration_str = f"{duration // 60}:{duration % 60:02d}"
                
                # Create song object
                song = Song(url=url, title=title, duration=duration)
                
                # Check if already playing
                if voice_client.is_playing() or self.is_playing.get(interaction.guild.id, False):
                    # Queue this song
                    position = self.add_to_queue(interaction.guild.id, song)
                    embed = discord.Embed(
                        title="📝 Queued",
                        description=f"{title}\nPosition: #{position}",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Duration", value=duration_str, inline=False)
                    try:
                        await interaction.followup.send(embed=embed)
                    except:
                        pass  # Interaction expired
                    logger.info(f"Queued: {title} (position {position})")
                    return
                
                # Create audio source
                audio_source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
                
                # Track playback state
                self.set_current(interaction.guild.id, song)
                self.is_playing[interaction.guild.id] = True
                self.voice_clients[interaction.guild.id] = voice_client
                
                def after_play(error):
                    if error:
                        logger.error(f"Playback error: {error}")
                    else:
                        logger.info(f"✅ Finished: {title[:50]}")
                    
                    # Play next song from queue
                    asyncio.run_coroutine_threadsafe(
                        self.play_next_from_queue(interaction.guild.id, voice_client),
                        self.bot.loop
                    )
                
                # Play!
                voice_client.play(audio_source, after=after_play)
                
                logger.info(f"▶️ Playing: {title} ({duration_str})")
                
                # Update status
                embed = discord.Embed(
                    title="🎵 Now Playing",
                    description=title[:256],
                    color=discord.Color.green()
                )
                embed.add_field(name="Duration", value=duration_str, inline=False)
                embed.add_field(name="Channel", value=f"<#{channel.id}>", inline=False)
                try:
                    await interaction.followup.send(embed=embed)
                except:
                    pass  # Interaction expired
                
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Playback Error",
                    description=f"Failed to start playback: {str(e)[:100]}",
                    color=discord.Color.red()
                )
                try:
                    await interaction.followup.send(embed=embed)
                except:
                    pass  # Interaction expired
                logger.error(f"Playback error: {e}")
                return
        
        except Exception as e:
            logger.error(f"Unexpected error in play slash command: {e}")
            embed = discord.Embed(
                title="❌ Unexpected Error",
                description=str(e)[:256],
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
    
    # ==================== PAUSE COMMAND ====================
    
    @commands.command(name='pause', help='Pause music')
    async def pause(self, ctx):
        """Pause playback"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            embed = discord.Embed(
                description="⏸️ Music paused",
                color=discord.Color.orange()
            )
            logger.info("Music paused")
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="Nothing is playing",
                color=discord.Color.red()
            )
        await ctx.send(embed=embed)
    
    @app_commands.command(name="pause", description="Pause music")
    async def pause_slash(self, interaction: discord.Interaction):
        """Pause playback (slash command)"""
        await interaction.response.defer()
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            embed = discord.Embed(
                description="⏸️ Music paused",
                color=discord.Color.orange()
            )
            logger.info("Music paused")
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="Nothing is playing",
                color=discord.Color.red()
            )
        await interaction.followup.send(embed=embed)
    
    # ==================== RESUME COMMAND ====================
    
    @commands.command(name='resume', help='Resume music')
    async def resume(self, ctx):
        """Resume playback"""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            embed = discord.Embed(
                description="▶️ Music resumed",
                color=discord.Color.green()
            )
            logger.info("Music resumed")
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="Nothing is paused",
                color=discord.Color.red()
            )
        await ctx.send(embed=embed)
    
    @app_commands.command(name="resume", description="Resume music")
    async def resume_slash(self, interaction: discord.Interaction):
        """Resume playback (slash command)"""
        await interaction.response.defer()
        if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            embed = discord.Embed(
                description="▶️ Music resumed",
                color=discord.Color.green()
            )
            logger.info("Music resumed")
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="Nothing is paused",
                color=discord.Color.red()
            )
        await interaction.followup.send(embed=embed)
    
    # ==================== STOP COMMAND ====================
    
    @commands.command(name='stop', help='Stop music and disconnect')
    async def stop(self, ctx):
        """Stop playback and disconnect"""
        if ctx.voice_client:
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
            await ctx.voice_client.disconnect()
            
            # Clear all playback state
            guild_id = ctx.guild.id
            self.clear_queue(guild_id)
            self.is_playing[guild_id] = False
            self.set_current(guild_id, None)
            if guild_id in self.voice_clients:
                del self.voice_clients[guild_id]
            
            embed = discord.Embed(
                description="⏹️ Stopped and disconnected",
                color=discord.Color.orange()
            )
            logger.info(f"Stopped playback in {ctx.guild.name}")
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="Bot is not connected to a voice channel",
                color=discord.Color.red()
            )
        await ctx.send(embed=embed)
    
    @app_commands.command(name="stop", description="Stop music and disconnect")
    async def stop_slash(self, interaction: discord.Interaction):
        """Stop playback and disconnect (slash command)"""
        await interaction.response.defer()
        if interaction.guild.voice_client:
            if interaction.guild.voice_client.is_playing():
                interaction.guild.voice_client.stop()
            await interaction.guild.voice_client.disconnect()
            
            # Clear all playback state
            guild_id = interaction.guild.id
            self.clear_queue(guild_id)
            self.is_playing[guild_id] = False
            self.set_current(guild_id, None)
            if guild_id in self.voice_clients:
                del self.voice_clients[guild_id]
            
            embed = discord.Embed(
                description="⏹️ Stopped and disconnected",
                color=discord.Color.orange()
            )
            logger.info(f"Stopped playback in {interaction.guild.name}")
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="Bot is not connected to a voice channel",
                color=discord.Color.red()
            )
        await interaction.followup.send(embed=embed)
    
    # ==================== VOLUME COMMAND ====================
    
    @commands.command(name='volume', help='Set volume (0-100)')
    async def volume(self, ctx, vol: int):
        """Set volume level"""
        if ctx.voice_client and ctx.voice_client.source:
            if 0 <= vol <= 100:
                ctx.voice_client.source.volume = vol / 100
                embed = discord.Embed(
                    description=f"🔊 Volume set to {vol}%",
                    color=discord.Color.blue()
                )
                logger.info(f"Volume set to {vol}%")
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description="Volume must be between 0 and 100",
                    color=discord.Color.red()
                )
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="Bot is not playing music",
                color=discord.Color.red()
            )
        await ctx.send(embed=embed)
    
    @app_commands.command(name="volume", description="Set volume (0-100)")
    @app_commands.describe(level="Volume level (0-100)")
    async def volume_slash(self, interaction: discord.Interaction, level: int):
        """Set volume level (slash command)"""
        await interaction.response.defer()
        if interaction.guild.voice_client and interaction.guild.voice_client.source:
            if 0 <= level <= 100:
                interaction.guild.voice_client.source.volume = level / 100
                embed = discord.Embed(
                    description=f"🔊 Volume set to {level}%",
                    color=discord.Color.blue()
                )
                logger.info(f"Volume set to {level}%")
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description="Volume must be between 0 and 100",
                    color=discord.Color.red()
                )
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="Bot is not playing music",
                color=discord.Color.red()
            )
        await interaction.followup.send(embed=embed)
    
    # ==================== QUEUE MANAGEMENT ====================
    
    async def play_next_from_queue(
        self,
        guild_id: int,
        voice_client: discord.VoiceClient
    ) -> None:
        """Play next song from queue"""
        try:
            # Check if voice client is still valid
            if not voice_client or not voice_client.is_connected():
                logger.warning(f"Voice client disconnected for guild {guild_id}")
                self.is_playing[guild_id] = False
                return
            
            # Get next song from queue
            next_song = self.pop_next_queued(guild_id)
            
            if not next_song:
                logger.info(f"Queue empty for guild {guild_id}, stopping playback")
                self.is_playing[guild_id] = False
                self.set_current(guild_id, None)
                return
            
            logger.info(f"Playing next queued song: {next_song.title}")
            
            # Create audio source for next song
            audio_source = discord.FFmpegPCMAudio(
                next_song.url,
                **FFMPEG_OPTIONS
            )
            
            # Set current
            self.set_current(guild_id, next_song)
            
            def after_next_play(error):
                if error:
                    logger.error(f"Next playback error: {error}")
                else:
                    logger.info(f"✅ Finished: {next_song.title[:50]}")
                
                # Play the one after next
                asyncio.run_coroutine_threadsafe(
                    self.play_next_from_queue(guild_id, voice_client),
                    self.bot.loop
                )
            
            # Play next song
            voice_client.play(audio_source, after=after_next_play)
            logger.info(f"▶️ Now playing: {next_song.title}")
            
        except Exception as e:
            logger.error(f"Error playing next song: {e}")
            self.is_playing[guild_id] = False
    
    # ==================== QUEUE COMMANDS ====================
    
    @commands.command(name='queue', help='Show queue')
    async def show_queue(self, ctx):
        """Display current queue"""
        info = self.get_queue_info(ctx.guild.id)
        
        embed = discord.Embed(
            title="📋 Queue",
            color=discord.Color.blue()
        )
        
        if info['current']:
            embed.add_field(
                name="🎵 Now Playing",
                value=f"{info['current'].title}\n({info['current'].duration_str()})",
                inline=False
            )
        else:
            embed.add_field(
                name="🎵 Now Playing",
                value="Nothing",
                inline=False
            )
        
        if info['queue_songs']:
            queue_text = "\n".join(
                f"{i+1}. {song.title} ({song.duration_str()})"
                for i, song in enumerate(info['queue_songs'][:10])
            )
            if len(info['queue_songs']) > 10:
                queue_text += f"\n... and {len(info['queue_songs']) - 10} more"
            embed.add_field(
                name=f"📝 Queue ({info['queue_length']} songs)",
                value=queue_text,
                inline=False
            )
        else:
            embed.add_field(
                name="📝 Queue",
                value="Empty",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='skip', help='Skip current song')
    async def skip(self, ctx):
        """Skip to next song"""
        voice_client = ctx.voice_client
        
        if not voice_client or not voice_client.is_playing():
            await ctx.send("❌ Not playing anything")
            return
        
        # Stop current playback (will trigger next song via after_play callback)
        voice_client.stop()
        current = self.get_current(ctx.guild.id)
        
        next_song = self.get_next_queued(ctx.guild.id)
        if next_song:
            await ctx.send(f"⏭️ Skipped! Next: {next_song.title}")
        else:
            await ctx.send(f"⏭️ Skipped!")
    
    @commands.command(name='clearqueue', help='Clear queue')
    async def clear_queue_cmd(self, ctx):
        """Clear entire queue"""
        self.clear_queue(ctx.guild.id)
        await ctx.send("🗑️ Queue cleared!")
    
    # ==================== STATUS COMMAND ====================
    
    @commands.command(name='status', help='Show bot status')
    async def status(self, ctx):
        """Show current status"""
        if ctx.voice_client:
            if ctx.voice_client.is_playing():
                status_text = "▶️ Playing"
            elif ctx.voice_client.is_paused():
                status_text = "⏸️ Paused"
            else:
                status_text = "🎧 Connected (idle)"
            channel = ctx.voice_client.channel.mention
        else:
            status_text = "🔌 Not connected"
            channel = "N/A"
        
        embed = discord.Embed(
            title="🎵 Music Bot Status",
            color=discord.Color.blue()
        )
        embed.add_field(name="Status", value=status_text, inline=False)
        embed.add_field(name="Voice Channel", value=channel, inline=False)
        embed.add_field(
            name="Prefix Commands (!)",
            value=(
                "🎵 `!play <url/query>` - Play music\n"
                "⏸️ `!pause` - Pause playback\n"
                "▶️ `!resume` - Resume playback\n"
                "⏹️ `!stop` - Stop and disconnect\n"
                "⏭️ `!skip` - Skip current song\n"
                "📋 `!queue` - Show queue\n"
                "🗑️ `!clearqueue` - Clear queue\n"
                "🔊 `!volume <0-100>` - Set volume\n"
                "📊 `!status` - Show this status"
            ),
            inline=False
        )
        embed.add_field(
            name="Slash Commands (/)",
            value=(
                "🎵 `/play` - Play music\n"
                "⏸️ `/pause` - Pause playback\n"
                "▶️ `/resume` - Resume playback\n"
                "⏹️ `/stop` - Stop and disconnect\n"
                "🔊 `/volume` - Set volume\n"
                "📊 `/status` - Show this status"
            ),
            inline=False
        )
        await ctx.send(embed=embed)
    
    @app_commands.command(name="status", description="Show bot status")
    async def status_slash(self, interaction: discord.Interaction):
        """Show current status (slash command)"""
        await interaction.response.defer()
        if interaction.guild.voice_client:
            if interaction.guild.voice_client.is_playing():
                status_text = "▶️ Playing"
            elif interaction.guild.voice_client.is_paused():
                status_text = "⏸️ Paused"
            else:
                status_text = "🎧 Connected (idle)"
            channel = interaction.guild.voice_client.channel.mention
        else:
            status_text = "🔌 Not connected"
            channel = "N/A"
        
        embed = discord.Embed(
            title="🎵 Music Bot Status",
            color=discord.Color.blue()
        )
        embed.add_field(name="Status", value=status_text, inline=False)
        embed.add_field(name="Voice Channel", value=channel, inline=False)
        embed.add_field(
            name="Prefix Commands (!)",
            value=(
                "🎵 `!play <url/query>` - Play music\n"
                "⏸️ `!pause` - Pause playback\n"
                "▶️ `!resume` - Resume playback\n"
                "⏹️ `!stop` - Stop and disconnect\n"
                "🔊 `!volume <0-100>` - Set volume\n"
                "📊 `!status` - Show this status"
            ),
            inline=False
        )
        embed.add_field(
            name="Slash Commands (/)",
            value=(
                "🎵 `/play` - Play music\n"
                "⏸️ `/pause` - Pause playback\n"
                "▶️ `/resume` - Resume playback\n"
                "⏹️ `/stop` - Stop and disconnect\n"
                "🔊 `/volume` - Set volume\n"
                "📊 `/status` - Show this status"
            ),
            inline=False
        )
        await interaction.followup.send(embed=embed)


# ==================== COG SETUP ====================

async def setup(bot):
    """Load the music cog"""
    await bot.add_cog(Music(bot))
    logger.info("✅ Simple Music Cog loaded successfully!")
