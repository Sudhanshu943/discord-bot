"""
Optimized Music Cog - Fast Playback (3-5 seconds)
✅ Chunk-based playlist loading
✅ Background preloading
✅ Fast playback startup
✅ Per-guild queue management
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
from typing import Optional

from music.models.queue_manager import QueueManager, Song
from music.services.stream_preloader import StreamPreloader, BackgroundLoader
from music.services.fast_player import FastPlayer

logger = logging.getLogger('discord.music.optimized')

# ==================== YDL OPTIONS - PLAYLIST SUPPORT ====================
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'default_search': 'ytsearch',
    'noplaylist': False,  # ✅ ENABLE PLAYLISTS
    'playlist_items': '1-999',  # Support large playlists
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
    'EXTRACTION': 10.0,
    'VOICE_CONNECT': 5.0,
    'PLAYLIST_LOAD': 20.0,
}


# ==================== OPTIMIZED MUSIC COG ====================
class MusicOptimized(commands.Cog):
    """
    Optimized music cog with:
    - Fast playback (3-5 seconds)
    - Chunk-based playlist loading
    - Background preloading
    - Per-guild queue management
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.synced = False
        
        # Initialize managers
        self.queue_manager = QueueManager(
            chunk_size=5,
            max_queue_size=200,
            ydl_opts=YDL_OPTIONS
        )
        
        self.preloader = StreamPreloader(
            ydl_opts=YDL_OPTIONS,
            extration_timeout=10.0
        )
        
        self.background_loader = BackgroundLoader(
            queue_manager=self.queue_manager,
            preloader=self.preloader,
            check_interval=3.0
        )
        
        self.player = FastPlayer(
            bot=bot,
            queue_manager=self.queue_manager,
            preloader=self.preloader,
            ydl_opts=YDL_OPTIONS
        )
        
        logger.info("🎵 Optimized Music Cog initialized (Fast playback mode)")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Sync slash commands"""
        if not self.synced:
            try:
                await self.bot.tree.sync()
                logger.info("✅ Slash commands synced")
                self.synced = True
            except Exception as e:
                logger.error(f"Failed to sync: {e}")
    
    # ==================== PLAY COMMANDS ====================
    
    @commands.command(name='play', help='Play music (fast: 3-5 seconds)')
    async def play(self, ctx, *, url_or_search: str):
        """
        Play music from URL or search query
        Usage: !play <URL or song name>
        
        Features:
        - Playback starts in 3-5 seconds
        - Auto-loads playlists in chunks
        - Preloads next song while current plays
        """
        # Defer response
        await ctx.defer()
        
        try:
            # Check voice channel
            if not ctx.author.voice or not ctx.author.voice.channel:
                await ctx.send("❌ Join a voice channel first")
                return
            
            channel = ctx.author.voice.channel
            
            # Get player
            player = self.player.get_player(ctx.guild.id)
            
            # Status
            status_embed = discord.Embed(
                title="🔄 Preparing...",
                description="Loading audio stream...",
                color=discord.Color.blue()
            )
            status_msg = await ctx.send(embed=status_embed)
            
            # Is playlist?
            is_playlist = any(x in url_or_search.lower() for x in [
                'playlist', 'list=', 'album',
                'mix', 'channel/'
            ]) or (url_or_search.startswith('http') is False)
            
            if is_playlist:
                # Load playlist with chunking
                logger.info(f"Loading playlist: {url_or_search[:50]}")
                
                success, count = await self.queue_manager.load_playlist_chunk(
                    ctx.guild.id,
                    url_or_search,
                    self.bot.loop
                )
                
                if not success or count == 0:
                    await status_msg.edit(embed=discord.Embed(
                        title="❌ Load Failed",
                        description="Could not load playlist",
                        color=discord.Color.red()
                    ))
                    return
                
                logger.info(f"Loaded {count} songs from playlist")
                
                # Get first song
                first_song = self.queue_manager.get_queue(ctx.guild.id).queue[0]
                await status_msg.edit(embed=discord.Embed(
                    title="🎵 Loaded Playlist",
                    description=f"Loaded {count} songs\nStarting: {first_song.title}",
                    color=discord.Color.green()
                ))
            else:
                # Single song
                await status_msg.edit(embed=discord.Embed(
                    title="🔍 Searching...",
                    description=f"Searching for: {url_or_search[:50]}",
                    color=discord.Color.blue()
                ))
            
            # Fast play
            success, play_msg = await player.play_song_fast(ctx, url_or_search)
            
            if success:
                # Update status
                embed = discord.Embed(
                    title="✅ Now Playing",
                    description=play_msg,
                    color=discord.Color.green()
                )
                await status_msg.edit(embed=embed)
                
                # Start background loading
                await self.background_loader.start_background_loading(
                    ctx.guild.id,
                    self.bot.loop
                )
                
                logger.info(f"Started playback with background loading")
            else:
                await status_msg.edit(embed=discord.Embed(
                    title="❌ Playback Failed",
                    description=play_msg,
                    color=discord.Color.red()
                ))
        
        except Exception as e:
            logger.error(f"Play command error: {e}")
            await ctx.send(f"❌ Error: {str(e)[:100]}")
    
    @app_commands.command(
        name='play_slash',
        description='Play music (slash command - fast 3-5s startup)'
    )
    async def play_slash(
        self,
        interaction: discord.Interaction,
        query: str
    ):
        """Slash command version of play"""
        await interaction.response.defer()
        
        try:
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.followup.send("❌ Join a voice channel first")
                return
            
            channel = interaction.user.voice.channel
            guild_id = interaction.guild.id
            
            # Get player
            player = self.player.get_player(guild_id)
            
            # Status
            status_embed = discord.Embed(
                title="🔄 Preparing...",
                description="Loading audio stream...",
                color=discord.Color.blue()
            )
            status_msg = await interaction.followup.send(embed=status_embed)
            
            # Fast play
            success, play_msg = await player.play_song_fast(interaction, query)
            
            if success:
                embed = discord.Embed(
                    title="✅ Now Playing",
                    description=play_msg,
                    color=discord.Color.green()
                )
                await status_msg.edit(embed=embed)
                
                # Background loading
                await self.background_loader.start_background_loading(
                    guild_id,
                    self.bot.loop
                )
            else:
                await status_msg.edit(embed=discord.Embed(
                    title="❌ Failed",
                    description=play_msg,
                    color=discord.Color.red()
                ))
        
        except Exception as e:
            logger.error(f"Play slash error: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)[:100]}")
    
    # ==================== QUEUE COMMANDS ====================
    
    @commands.command(name='queue', help='Show queue')
    async def show_queue(self, ctx):
        """Display current queue"""
        info = self.queue_manager.get_queue_info(ctx.guild.id)
        
        embed = discord.Embed(
            title="📋 Queue",
            color=discord.Color.blue()
        )
        
        current = info['current']
        if current:
            embed.add_field(
                name="🎵 Now Playing",
                value=current,
                inline=False
            )
        
        embed.add_field(
            name="📝 Queue",
            value=f"{info['queue_len']} songs queued",
            inline=True
        )
        
        embed.add_field(
            name="⏳ Lazy Queue",
            value=f"{info['lazy_queue_len']} songs (loading...)",
            inline=True
        )
        
        embed.add_field(
            name="📊 Total",
            value=f"{info['total_remaining']} remaining",
            inline=True
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='skip', help='Skip to next song')
    async def skip(self, ctx):
        """Skip current song"""
        next_song = self.queue_manager.skip(ctx.guild.id)
        
        if next_song:
            await ctx.send(f"⏭️ Skipped! Next: {next_song.title}")
        else:
            await ctx.send("❌ No more songs")
    
    @commands.command(name='stop', help='Stop playback')
    async def stop(self, ctx):
        """Stop playback and clear queue"""
        player = self.player.get_player(ctx.guild.id)
        
        # Stop background loading
        await self.background_loader.stop_background_loading(ctx.guild.id)
        
        # Disconnect
        await player.disconnect()
        self.queue_manager.clear_queue(ctx.guild.id)
        
        await ctx.send("⏹️ Stopped playback")
    
    @commands.command(name='pause', help='Pause playback')
    async def pause(self, ctx):
        """Pause current playback"""
        player = self.player.get_player(ctx.guild.id)
        
        if await player.pause():
            await ctx.send("⏸️ Paused")
        else:
            await ctx.send("❌ Not playing")
    
    @commands.command(name='resume', help='Resume playback')
    async def resume(self, ctx):
        """Resume paused playback"""
        player = self.player.get_player(ctx.guild.id)
        
        if await player.resume():
            await ctx.send("▶️ Resumed")
        else:
            await ctx.send("❌ Not paused")
    
    async def cog_unload(self):
        """Cleanup on unload"""
        # Cancel all background loaders
        for guild_id in list(self.background_loader.loader_tasks.keys()):
            await self.background_loader.stop_background_loading(guild_id)
        
        # Disconnect all players
        for guild_id in list(self.player.players.keys()):
            await self.player.disconnect_player(guild_id)
        
        logger.info("🛑 Optimized Music Cog unloaded")


# ==================== SETUP ====================
async def setup(bot):
    """Load cog"""
    await bot.add_cog(MusicOptimized(bot))
    logger.info("✅ Optimized Music Cog loaded")
