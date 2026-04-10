"""
Music Cog - ULTRA-FAST VERSION
✅ Pre-extraction for instant playback
✅ Streaming playlist loading
✅ YouTube Mix support
✅ Background pre-loading
✅ Low latency optimizations
"""

import discord
from discord import player
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional, List
import json
import os

from .logic.player_manager import PlayerManager, Song
from .logic.search_manager_v2 import SearchManager, Platform
from .ui import MusicEmbeds, MusicControlsView, VolumeModal

logger = logging.getLogger('discord.music')

class Music(commands.Cog):
    """
    Music Cog - ULTRA-FAST MODE
    No Lavalink Required! Uses yt-dlp + YouTube Music
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.player_manager = PlayerManager(bot)
        self.search_manager = SearchManager(use_youtube_music=True)
        logger.info("⚡ Music cog initialized (ULTRA-FAST mode)")
    
    async def cog_unload(self):
        
        for guild in self.bot.guilds:
            await self.player_manager.disconnect(guild)

        try:
            self.search_manager.shutdown()
        except Exception:
            pass

        logger.info("Music cog unloaded")

    
    # ==================== HELPER METHODS ====================
    
    async def _send_response(self, ctx, content=None, embed=None, view=None, ephemeral=False):
        """Send response handling both text and slash commands"""
        try:
            # Handle Message objects (when called from chat integration)
            if isinstance(ctx, discord.Message):
                kwargs = {}
                if content:
                    kwargs['content'] = content
                if embed:
                    kwargs['embed'] = embed
                return await ctx.reply(**kwargs, mention_author=False)
            
            kwargs = {}
            if content:
                kwargs['content'] = content
            if embed:
                kwargs['embed'] = embed
            if view:
                kwargs['view'] = view
            if ephemeral:
                kwargs['ephemeral'] = ephemeral
            
            # Check if interaction is expired
            interaction_expired = False
            if hasattr(ctx, 'interaction') and ctx.interaction:
                interaction_expired = getattr(ctx.interaction, '_expired', False)
            
            # If interaction expired, use channel send instead
            if interaction_expired:
                kwargs.pop('view', None)
                kwargs.pop('ephemeral', None)
                if hasattr(ctx, 'channel') and ctx.channel:
                    return await ctx.channel.send(**kwargs)
                return None
            
            if hasattr(ctx, 'interaction') and ctx.interaction:
                if ctx.interaction.response.is_done():
                    return await ctx.interaction.followup.send(**kwargs)
                else:
                    return await ctx.interaction.response.send_message(**kwargs)
            else:
                return await ctx.send(**kwargs)
        except discord.errors.NotFound:
            # Fallback to channel send if interaction not found
            if hasattr(ctx, 'channel') and ctx.channel:
                kwargs.pop('view', None)
                kwargs.pop('ephemeral', None)
                return await ctx.channel.send(**kwargs)
        except Exception as e:
            logger.error(f"Error sending response: {e}")
            return None
    
    async def _defer_if_slash(self, ctx):
        """Defer response for slash commands"""
        if hasattr(ctx, 'interaction') and ctx.interaction and not ctx.interaction.response.is_done():
            try:
                await ctx.interaction.response.defer()
            except discord.errors.NotFound:
                # Interaction expired or network issue - mark as expired
                logger.warning("Interaction defer failed - interaction may have expired")
                ctx.interaction._expired = True  # Mark as expired for later handling
            except Exception as e:
                logger.error(f"Error deferring interaction: {e}")
                ctx.interaction._expired = True
    
    async def _handle_single_track(self, ctx, track_info: dict, player, pre_extract: bool = True):
        """
        Handle single track playback with PRE-EXTRACTION
        Args:
            pre_extract: If True and not playing, extract audio now for instant playback
        """
        # ✅ PRE-EXTRACTION: Extract audio NOW if not playing (saves 2-3s on playback)
        if pre_extract and not player.is_playing and track_info.get('url'):
            # Show "Adding to queue..." with extraction
            queue_embed = discord.Embed(
                description=f"📥 **{track_info['title'][:50]}...**",
                color=0x3498db
            )
            queue_msg = await self._send_response(ctx, embed=queue_embed)
            
            # Extract audio NOW (parallel to user feedback)
            logger.info(f"⚡ Pre-extracting for instant playback")
            audio_url = await player.extract_audio_url(track_info['url'])
            
            # Delete queue message
            if queue_msg:
                try:
                    await queue_msg.delete()
                except:
                    pass
            
            # Use extracted URL or fallback to pending
            source = audio_url if audio_url else "pending"
        else:
            source = "pending"
        
        song = Song(
            source=source,
            title=track_info['title'],
            url=track_info['url'],
            duration=track_info['duration'],
            thumbnail=track_info['thumbnail'],
            requester=ctx.author
        )

        position = await player.add_to_queue(song)

        if position == 0:
            if player.controller_message:
                try:
                    await player.controller_message.delete()
                except:
                    pass
            
            embed = MusicEmbeds.now_playing(song, requester=ctx.author)
            view = MusicControlsView(player, timeout=300, auto_delete=False)
            message = await self._send_response(ctx, embed=embed, view=view)
            if message:
                view.message = message
                player.controller_message = message
        else:
            embed = MusicEmbeds.added_to_queue(song, position)
            await self._send_response(ctx, embed=embed)
    
    async def _handle_playlist(self, ctx, tracks: List[dict], platform: Platform, player):
        """Handle playlist loading with STREAMING approach"""
        total_tracks = len(tracks)
        
        # Detect YouTube Mix
        is_youtube_mix = 'list=RD' in tracks[0].get('url', '') if tracks else False
        
        # Show loading message
        if is_youtube_mix:
            loading_embed = discord.Embed(
                title="📻 Loading YouTube Mix",
                description=f"YouTube Mixes are dynamic playlists.\nAdding **{total_tracks}** tracks...",
                color=0xff9800
            )
        else:
            loading_embed = discord.Embed(
                title=f"{SearchManager.get_platform_emoji(platform)} Loading Playlist",
                description=f"Adding **{total_tracks}** tracks to queue...",
                color=0x3498db
            )
        
        loading_msg = await self._send_response(ctx, embed=loading_embed)

        added_count = 0
        failed_count = 0
        
        # ✅ STREAMING APPROACH: Add all tracks immediately (no extraction)
        for idx, track_info in enumerate(tracks, 1):
            try:
                song = Song(
                    source="pending",  # All songs lazy-loaded
                    title=track_info['title'],
                    url=track_info['url'],
                    duration=track_info['duration'],
                    thumbnail=track_info['thumbnail'],
                    requester=ctx.author
                )
                
                await player.add_to_queue(song)
                added_count += 1
                
                # Update progress every 25 tracks
                if idx % 25 == 0 and loading_msg:
                    try:
                        loading_embed.description = f"Adding tracks... **{idx}/{total_tracks}**"
                        await loading_msg.edit(embed=loading_embed)
                    except:
                        pass
                    
            except Exception as e:
                logger.error(f"Failed to add track {idx}: {e}")
                failed_count += 1

        # Delete loading message
        if loading_msg:
            try:
                await loading_msg.delete()
            except:
                pass

        # Show summary
        platform_emoji = SearchManager.get_platform_emoji(platform)
        platform_name = SearchManager.get_platform_name(platform)
        
        summary_embed = discord.Embed(
            title=f"{platform_emoji} Playlist Loaded",
            description="Audio will extract during playback for smooth experience.",
            color=0x00D9A3
        )
        
        summary_embed.add_field(
            name="Platform",
            value=platform_name,
            inline=True
        )
        summary_embed.add_field(
            name="Tracks Added",
            value=f"✅ {added_count}",
            inline=True
        )
        
        if failed_count > 0:
            summary_embed.add_field(
                name="Failed",
                value=f"❌ {failed_count}",
                inline=True
            )
        
        queue_pos = player.queue_count - added_count + 1
        summary_embed.add_field(
            name="Status",
            value=f"🎵 {'Now playing' if queue_pos == 0 else f'Starting at position {queue_pos}'}",
            inline=False
        )
        
        if is_youtube_mix:
            summary_embed.set_footer(text=f"⚡ YouTube Mix • Requested by {ctx.author.display_name}")
        else:
            summary_embed.set_footer(text=f"⚡ Fast loading • Requested by {ctx.author.display_name}")
        
        await self._send_response(ctx, embed=summary_embed)
    
    # ==================== EVENT LISTENERS ====================
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle voice state changes"""
        # Ignore bot's own state changes to prevent reconnection loops
        if member.id == self.bot.user.id:
            # Only handle intentional disconnects, not connection failures
            # Check if this is during an active connection attempt - don't remove player!
            if before.channel and not after.channel:
                # IMPORTANT: Check if player EXISTS, don't use get_player (which creates new one)
                player = self.player_manager.players.get(member.guild.id)
                if player and player._is_connecting:
                    # This is a connection failure, not intentional disconnect - don't remove!
                    logger.warning(f"Voice connection failed in {member.guild.name}, not removing player")
                    return
                # This is an intentional disconnect (user kicked bot or bot left)
                self.player_manager.remove_player(member.guild.id)
                logger.info(f"Bot disconnected from {member.guild.name}")
            return
        
        # Check if member left a voice channel
        if before.channel and not after.channel:
            # Use .get() to avoid creating new player
            player = self.player_manager.players.get(member.guild.id)
            if player and player.voice_client and player.voice_client.channel == before.channel:
                # Don't disconnect if currently connecting or lock is held
                if not player._is_connecting and not player._voice_lock.locked():
                    await player.check_empty_channel()
    
    # ==================== MUSIC HELP COMMAND ====================
    
    @commands.hybrid_command(name='musichelp', description='Show available music commands')
    async def music_help(self, ctx):
        """Show available music commands"""
        embed = discord.Embed(
            title="🎵 Music Bot Commands",
            description="Here are all available music commands:",
            color=0x3498db
        )
        
        commands_list = [
            ("!play <song/url>", "Play a song or add to queue"),
            ("!pause", "Pause current playback"),
            ("!resume", "Resume playback"),
            ("!skip", "Skip current song"),
            ("!stop", "Stop playback and clear queue"),
            ("!queue", "Show current queue"),
            ("!nowplaying", "Show current song info"),
            ("!volume <0-100>", "Set playback volume"),
            ("!loop", "Toggle loop mode"),
            ("!shuffle", "Shuffle the queue"),
            ("!like", "Add current song to liked songs"),
            ("!liked", "Show your liked songs"),
            ("!playliked", "Play your liked songs"),
            ("!join", "Join your voice channel"),
            ("!leave", "Leave voice channel"),
            ("!ping", "Check bot latency"),
        ]
        
        for cmd, desc in commands_list:
            embed.add_field(name=cmd, value=desc, inline=False)
        
        embed.set_footer(text="Use ! before commands or / for slash commands")
        await self._send_response(ctx, embed=embed)
    
    # ==================== CONNECTION COMMANDS ====================
    
    @commands.hybrid_command(name='join', description='Join your voice channel')
    async def join(self, ctx, channel: Optional[discord.VoiceChannel] = None):
        """Join a voice channel"""
        if not channel:
            if not ctx.author.voice:
                embed = MusicEmbeds.error("You're not in a voice channel!")
                return await self._send_response(ctx, embed=embed)
            channel = ctx.author.voice.channel
        
        player = self.player_manager.get_player(ctx.guild)
        success = await player.connect(channel)
        
        if success:
            embed = MusicEmbeds.success(f"Joined **{channel.name}**")
        else:
            embed = MusicEmbeds.error("Failed to join voice channel! Please try again in a moment.")
        await self._send_response(ctx, embed=embed)
    
    @commands.hybrid_command(name='leave', description='Leave the voice channel')
    async def leave(self, ctx):
        """Leave the voice channel"""
        player = self.player_manager.get_player(ctx.guild)
        
        if not player.voice_client:
            embed = MusicEmbeds.error("Not connected to a voice channel!")
            return await self._send_response(ctx, embed=embed)
        
        await self.player_manager.disconnect(ctx.guild)
        embed = MusicEmbeds.success("Disconnected from voice channel")
        await self._send_response(ctx, embed=embed)
    
    # ==================== PLAYBACK COMMANDS ====================
    @staticmethod
    async def song_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        """Provide song suggestions as user types"""
        if not current or len(current) < 2:
            return []
        
        logger.info(f"🔍 Autocomplete: {current}")

        try:
            # Create a search manager instance
            search_manager = SearchManager()
            suggestions = await search_manager.get_suggestions(current, limit=5)
            search_manager.shutdown()
            
            if not suggestions:
                logger.info(f"No suggestions for: {current}")
                return []
            
            choices = [
                app_commands.Choice(name=sugg[:100], value=sugg)
                for sugg in suggestions
            ]
            logger.info(f"✓ {len(choices)} suggestions found")
            return choices
        
        except Exception as e:
            logger.error(f"Autocomplete error: {e}")
            return []


    @commands.hybrid_command(name='play', description='Play a song or playlist')
    @app_commands.describe(query='Song name or URL')
    @app_commands.autocomplete(query=song_autocomplete)
    async def play(self, ctx, *, query: str):
        """
        ⚡ ULTRA-FAST playback (4-5 seconds)
        - Anti-bot detection with proxy support
        - Simplified search & extraction
        - Full terminal logging
        """
        logger.info(f"▶️ Play command: {query[:60]}")
        
        try:
            await self._defer_if_slash(ctx)
        except Exception as e:
            logger.error(f"Defer error: {e}")
            embed = discord.Embed(
                description="⚠️ Network issue. Please try again.",
                color=0xffaa00
            )
            if ctx.channel:
                return await ctx.channel.send(embed=embed)
            return

        try:
            player = self.player_manager.get_player(ctx.guild)
            player.text_channel = ctx.channel

            # Connect to voice
            if not player.voice_client or not player.voice_client.is_connected():
                if ctx.author.voice:
                    logger.info(f"🔗 Connecting to voice channel: {ctx.author.voice.channel.name}")
                    success = await player.connect(ctx.author.voice.channel)
                    if not success:
                        embed = MusicEmbeds.error("Failed to join voice! Try again.")
                        logger.error(f"Failed to connect to voice")
                        return await self._send_response(ctx, embed=embed)
                else:
                    embed = MusicEmbeds.error("You're not in a voice channel!")
                    logger.warning(f"User not in voice channel")
                    return await self._send_response(ctx, embed=embed)

            # Show searching
            search_embed = discord.Embed(
                description=f"🔍 Searching: **{query[:60]}**",
                color=0x3498db
            )
            search_msg = await self._send_response(ctx, embed=search_embed)
            logger.info(f"📺 Starting search (timeout: 5s)")

            # Fast search with timeout
            tracks, platform, is_playlist = await self.search_manager.search(query, limit=20)

            # Delete search message
            if search_msg:
                try:
                    await search_msg.delete()
                except:
                    pass

            if not tracks:
                embed = MusicEmbeds.error(f"❌ No tracks found for: {query}")
                logger.warning(f"No tracks found")
                return await self._send_response(ctx, embed=embed)

            logger.info(f"✓ Found {len(tracks)} tracks on {SearchManager.get_platform_name(platform)}")

            # Handle playlist vs single
            if is_playlist and len(tracks) > 1:
                logger.info(f"📋 Loading playlist with {len(tracks)} tracks")
                await self._handle_playlist(ctx, tracks, platform, player)
            else:
                logger.info(f"🎵 Queueing single track: {tracks[0]['title'][:50]}")
                await self._handle_single_track(ctx, tracks[0], player, pre_extract=True)
        
        except Exception as e:
            logger.error(f"Play command error: {e}", exc_info=True)
            embed = MusicEmbeds.error(f"Error: {str(e)[:100]}")
            try:
                await self._send_response(ctx, embed=embed)
            except:
                if ctx.channel:
                    await ctx.channel.send(embed=embed)
    
    @commands.hybrid_command(name='pause', description='Pause playback')
    async def pause(self, ctx):
        """Pause playback"""
        player = self.player_manager.get_player(ctx.guild)
        
        if not player.is_playing:
            embed = MusicEmbeds.error("Nothing is playing!")
            return await self._send_response(ctx, embed=embed)
        
        await player.pause()
        embed = MusicEmbeds.success("⏸️ Playback paused")
        await self._send_response(ctx, embed=embed)
    
    @commands.hybrid_command(name='resume', description='Resume playback')
    async def resume(self, ctx):
        """Resume playback"""
        player = self.player_manager.get_player(ctx.guild)
        
        if not player.is_paused:
            embed = MusicEmbeds.error("Nothing is paused!")
            return await self._send_response(ctx, embed=embed)
        
        await player.resume()
        embed = MusicEmbeds.success("▶️ Playback resumed")
        await self._send_response(ctx, embed=embed)
    
    @commands.hybrid_command(name='skip', description='Skip the current song')
    async def skip(self, ctx):
        """Skip current song"""
        player = self.player_manager.get_player(ctx.guild)

        if not player.is_playing:
            embed = MusicEmbeds.error("Nothing is playing!")
            return await self._send_response(ctx, embed=embed)

        current = player.current

        if player.controller_message:
            try:
                await player.controller_message.delete()
            except:
                pass
            player.controller_message = None

        await player.skip()

        if current:
            embed = MusicEmbeds.info(f"⏭️ Skipped: **{current.title[:50]}**", "Skipped")
        else:
            embed = MusicEmbeds.success("⏭️ Skipped")
        await self._send_response(ctx, embed=embed)
    
    @commands.hybrid_command(name='stop', description='Stop playback and clear queue')
    async def stop(self, ctx):
        """Stop playback and clear queue"""
        player = self.player_manager.get_player(ctx.guild)

        if not player.voice_client:
            embed = MusicEmbeds.error("Not connected!")
            return await self._send_response(ctx, embed=embed)

        if player.controller_message:
            try:
                await player.controller_message.delete()
            except:
                pass
            player.controller_message = None

        await player.stop()
        embed = MusicEmbeds.success("⏹️ Stopped playback and cleared queue")
        await self._send_response(ctx, embed=embed)
    
    # ==================== QUEUE COMMANDS ====================
    
    @commands.hybrid_command(name='queue', description='Show the music queue')
    async def queue(self, ctx):
        """Show the music queue"""
        player = self.player_manager.get_player(ctx.guild)
        
        if not player.current and player.queue_empty:
            embed = MusicEmbeds.info("Queue is empty!")
            return await self._send_response(ctx, embed=embed)
        
        queue_list = player.get_queue_list(limit=10)
        total = player.queue_count
        
        embed = MusicEmbeds.queue_list(queue_list, player.current, total)
        await self._send_response(ctx, embed=embed)
    
    @commands.hybrid_command(name='nowplaying', aliases=['np'], description='Show currently playing track')
    async def nowplaying(self, ctx):
        """Show current track info"""
        player = self.player_manager.get_player(ctx.guild)
        
        if not player.current:
            embed = MusicEmbeds.error("Nothing is playing!")
            return await self._send_response(ctx, embed=embed)
        
        embed = MusicEmbeds.now_playing(player.current, requester=player.current.requester)
        view = MusicControlsView(player, timeout=300)
        message = await self._send_response(ctx, embed=embed, view=view)
        if message:
            view.message = message
    
    @commands.hybrid_command(name='remove', description='Remove a track from the queue')
    @app_commands.describe(position='Position of track to remove (1-based)')
    async def remove(self, ctx, position: int):
        """Remove a track from the queue"""
        player = self.player_manager.get_player(ctx.guild)
        
        if player.queue_empty:
            embed = MusicEmbeds.error("Queue is empty!")
            return await self._send_response(ctx, embed=embed)
        
        removed = player.remove_from_queue(position)
        
        if removed:
            embed = MusicEmbeds.success(f"Removed **{removed.title[:50]}**")
        else:
            embed = MusicEmbeds.error(f"Invalid position! Must be 1-{player.queue_count}")
        await self._send_response(ctx, embed=embed)
    
    @commands.hybrid_command(name='shuffle', description='Shuffle the queue')
    async def shuffle(self, ctx):
        """Shuffle the queue"""
        player = self.player_manager.get_player(ctx.guild)
        
        if player.queue_empty:
            embed = MusicEmbeds.error("Queue is empty!")
            return await self._send_response(ctx, embed=embed)
        
        player.shuffle_queue()
        embed = MusicEmbeds.success("🔀 Queue shuffled!")
        await self._send_response(ctx, embed=embed)
    
    @commands.hybrid_command(name='clear', description='Clear the queue')
    async def clear(self, ctx):
        """Clear the queue"""
        player = self.player_manager.get_player(ctx.guild)
        
        if player.queue_empty:
            embed = MusicEmbeds.error("Queue is already empty!")
            return await self._send_response(ctx, embed=embed)
        
        player.clear_queue()
        embed = MusicEmbeds.success("🗑️ Queue cleared!")
        await self._send_response(ctx, embed=embed)
    
    # ==================== VOLUME COMMAND ====================
    
    @commands.hybrid_command(name='volume', aliases=['vol'], description='Set or view the volume')
    @app_commands.describe(level='Volume level (0-100)')
    async def volume(self, ctx, level: Optional[int] = None):
        """Set or view volume"""
        player = self.player_manager.get_player(ctx.guild)

        if not player.voice_client:
            embed = MusicEmbeds.error("Not connected!")
            return await self._send_response(ctx, embed=embed)

        if level is None:
            vol = int(player.volume * 100)
            view = VolumeModal(player, timeout=60)
            embed = MusicEmbeds.info(f"Current volume: **{vol}%**\n\nUse buttons below to adjust", "🔊 Volume")
            return await self._send_response(ctx, embed=embed, view=view)

        if not 0 <= level <= 100:
            embed = MusicEmbeds.error("Volume must be between 0 and 100!")
            return await self._send_response(ctx, embed=embed)

        player.set_volume(level)
        embed = MusicEmbeds.success(f"🔊 Volume set to **{level}%**")
        await self._send_response(ctx, embed=embed)
    
    # ==================== LOOP COMMAND ====================
    
    @commands.hybrid_command(name='loop', description='Toggle loop for current song')
    async def loop(self, ctx):
        """Toggle loop"""
        player = self.player_manager.get_player(ctx.guild)
        
        if not player.current:
            embed = MusicEmbeds.error("Nothing is playing!")
            return await self._send_response(ctx, embed=embed)
        
        player.loop = not player.loop
        
        if player.loop:
            embed = MusicEmbeds.success(f"🔁 Loop enabled for **{player.current.title[:50]}**")
        else:
            embed = MusicEmbeds.info("Loop disabled", "🔁 Loop")
        await self._send_response(ctx, embed=embed)
    
    # ==================== CONTROLS COMMAND ====================
    
    @commands.hybrid_command(name='controls', description='Show music control panel')
    async def controls(self, ctx):
        """Show interactive music controls"""
        player = self.player_manager.get_player(ctx.guild)
        
        if not player.voice_client:
            embed = MusicEmbeds.error("Not connected to voice!")
            return await self._send_response(ctx, embed=embed)
        
        if player.current:
            embed = MusicEmbeds.now_playing(player.current, requester=player.current.requester)
        else:
            embed = MusicEmbeds.info("Ready to play music!", "🎵 Music Controls")
        
        view = MusicControlsView(player, timeout=300)
        message = await self._send_response(ctx, embed=embed, view=view)
        if message:
            view.message = message
    
    # ==================== LIKED SONGS COMMANDS ====================
    
    @commands.hybrid_command(name='likes', description='View your liked songs playlist')
    async def likes(self, ctx):
        """View your liked songs"""
        try:
            from .logic.liked_songs import get_liked_songs_storage
            storage = get_liked_songs_storage()
            
            user_id = ctx.author.id
            liked_songs = await storage.get_liked_songs(user_id)
            
            if not liked_songs:
                embed = discord.Embed(
                    description="### ❤️ Your Liked Songs\n\n*No liked songs yet! Click the ❤️ button on a playing song to add it.*",
                    color=0xE91E63
                )
                return await self._send_response(ctx, embed=embed)
            
            # Build the embed
            total_duration = sum(s.get('duration', 0) for s in liked_songs)
            mins = int(total_duration // 60)
            
            embed = discord.Embed(
                description=f"### ❤️ Your Liked Songs\n`{len(liked_songs)} tracks` • `~{mins} minutes`\n\n**Click the ❤️ button on any playing song to like it!**",
                color=0xE91E63
            )
            
            # Add songs (limit to 20 for embed)
            songs_text = ""
            for i, song in enumerate(liked_songs[:20], 1):
                title = song.get('title', 'Unknown')[:50]
                duration = song.get('duration', 0)
                mins_dur = duration // 60
                secs_dur = duration % 60
                songs_text += f"`{i}.` {title} • `{mins_dur}:{secs_dur:02d}`\n"
            
            if len(liked_songs) > 20:
                songs_text += f"\n*+{len(liked_songs) - 20} more*"
            
            embed.add_field(name="📜 Liked Songs", value=songs_text or "*Empty*", inline=False)
            
            # Add footer with unlike instructions
            embed.set_footer(text="Use /unlike <number> to remove a song from your liked songs")
            
            await self._send_response(ctx, embed=embed)
            
        except Exception as e:
            logger.error(f"Error in likes command: {e}")
            embed = MusicEmbeds.error("Failed to load liked songs. Please try again.")
            await self._send_response(ctx, embed=embed)
    
    @commands.hybrid_command(name='unlike', description='Remove a song from your liked songs')
    @app_commands.describe(position='Position number of the song to remove (from /likes list)')
    async def unlike(self, ctx, position: int):
        """Remove a song from liked songs by position number"""
        try:
            from .logic.liked_songs import get_liked_songs_storage
            storage = get_liked_songs_storage()
            
            user_id = ctx.author.id
            liked_songs = await storage.get_liked_songs(user_id)
            
            if not liked_songs:
                embed = discord.Embed(
                    description="### 💔 Your Liked Songs\n\n*No liked songs to remove!*",
                    color=0xE91E63
                )
                return await self._send_response(ctx, embed=embed)
            
            # Validate position
            if position < 1 or position > len(liked_songs):
                embed = MusicEmbeds.error(f"Invalid position! Use a number between 1 and {len(liked_songs)}")
                return await self._send_response(ctx, embed=embed)
            
            # Get the song to remove
            song_to_remove = liked_songs[position - 1]
            song_title = song_to_remove.get('title', 'Unknown')
            song_url = song_to_remove.get('url', '')
            
            # Remove the song
            removed = await storage.remove_song(user_id, song_url)
            
            if removed:
                embed = discord.Embed(
                    description=f"### 💔 Removed from Liked Songs\n\n**{song_title}**\n\nUse `/likes` to view your remaining liked songs!",
                    color=0xE91E63
                )
            else:
                embed = MusicEmbeds.error("Failed to remove song. Please try again.")
            
            await self._send_response(ctx, embed=embed)
            
        except Exception as e:
            logger.error(f"Error in unlike command: {e}")
            embed = MusicEmbeds.error("Failed to remove song. Please try again.")
            await self._send_response(ctx, embed=embed)
    
    @commands.hybrid_command(name='playliked', description='Play your liked songs queue')
    async def playliked(self, ctx):
        """Add all liked songs to queue and play"""
        try:
            from .logic.liked_songs import get_liked_songs_storage
            storage = get_liked_songs_storage()
            
            user_id = ctx.author.id
            liked_songs = await storage.get_liked_songs(user_id)
            
            if not liked_songs:
                embed = discord.Embed(
                    description="### ❤️ Your Liked Songs\n\n*No liked songs to play!*",
                    color=0xE91E63
                )
                return await self._send_response(ctx, embed=embed)
            
            # Connect to voice if not connected - check if actually connected
            player = self.player_manager.get_player(ctx.guild)
            
            if not player.voice_client or not player.voice_client.is_connected():
                user_voice = getattr(ctx.author, 'voice', None)
                if not user_voice or not user_voice.channel:
                    embed = MusicEmbeds.error("Join a voice channel first!")
                    return await self._send_response(ctx, embed=embed)
                
                # Connect and wait for connection to establish
                connected = await player.connect(user_voice.channel)
                if not connected:
                    embed = MusicEmbeds.error("Failed to connect to voice channel! Please try again in a moment.")
                    return await self._send_response(ctx, embed=embed)
                
                # Wait briefly for voice connection to establish
                await asyncio.sleep(0.5)
            
            # Add songs to queue
            added_count = 0
            for song_data in liked_songs:
                song = Song(
                    source="pending",
                    title=song_data.get('title', 'Unknown'),
                    url=song_data.get('url', ''),
                    duration=song_data.get('duration', 0),
                    thumbnail=song_data.get('thumbnail'),
                    requester=ctx.author
                )
                await player.add_to_queue(song)
                added_count += 1
            
            embed = discord.Embed(
                description=f"### ❤️ Playing Liked Songs\n\nAdded **{added_count}** songs to queue!",
                color=0xE91E63
            )
            await self._send_response(ctx, embed=embed)
            
        except Exception as e:
            logger.error(f"Error in playliked command: {e}")
            embed = MusicEmbeds.error("Failed to play liked songs. Please try again.")
            await self._send_response(ctx, embed=embed)
    
    # ==================== PLAYLIST COMMANDS ====================
    
    @commands.hybrid_group(name='playlist', description='Manage custom playlists')
    async def playlist(self, ctx):
        """Playlist management commands"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🎵 Playlist Commands",
                description=(
                    "**Available Commands:**\n"
                    "`/playlist save <name>` - Save current queue\n"
                    "`/playlist load <name>` - Load saved playlist\n"
                    "`/playlist list` - Show your playlists\n"
                    "`/playlist delete <name>` - Delete playlist\n"
                    "`/playlist info <name>` - Show details"
                ),
                color=0x3498db
            )
            await self._send_response(ctx, embed=embed)
    
    @playlist.command(name='save', description='Save current queue as a playlist')
    @app_commands.describe(name='Playlist name')
    async def playlist_save(self, ctx, *, name: str):
        """Save current queue as a playlist"""
        player = self.player_manager.get_player(ctx.guild)
        
        if player.queue_empty and not player.current:
            embed = MusicEmbeds.error("Queue is empty!")
            return await self._send_response(ctx, embed=embed)
        
        songs = []
        if player.current:
            songs.append({
                'title': player.current.title,
                'url': player.current.url,
                'duration': player.current.duration,
                'thumbnail': player.current.thumbnail
            })
        
        for song in player.get_queue_list(limit=100):
            songs.append({
                'title': song.title,
                'url': song.url,
                'duration': song.duration,
                'thumbnail': song.thumbnail
            })
        
        playlist_dir = 'playlists'
        os.makedirs(playlist_dir, exist_ok=True)
        
        user_id = str(ctx.author.id)
        playlist_file = os.path.join(playlist_dir, f'{user_id}.json')
        
        playlists = {}
        if os.path.exists(playlist_file):
            try:
                with open(playlist_file, 'r', encoding='utf-8') as f:
                    playlists = json.load(f)
            except:
                pass
        
        playlists[name] = {
            'songs': songs,
            'created': discord.utils.utcnow().isoformat(),
            'count': len(songs)
        }
        
        temp_file = playlist_file + ".tmp"

        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(playlists, f, indent=2, ensure_ascii=False)
        
        os.replace(temp_file, playlist_file)
        

        
        embed = MusicEmbeds.success(f"✅ Saved **{len(songs)}** tracks to **{name}**")
        await self._send_response(ctx, embed=embed)
    
    @playlist.command(name='load', description='Load and play a saved playlist')
    @app_commands.describe(name='Playlist name')
    async def playlist_load(self, ctx, *, name: str):
        """Load a saved playlist"""
        user_id = str(ctx.author.id)
        playlist_file = os.path.join('playlists', f'{user_id}.json')
        
        if not os.path.exists(playlist_file):
            embed = MusicEmbeds.error("You don't have any saved playlists!")
            return await self._send_response(ctx, embed=embed)
        
        try:
            with open(playlist_file, 'r', encoding='utf-8') as f:
                playlists = json.load(f)
        except:
            embed = MusicEmbeds.error("Error reading playlists!")
            return await self._send_response(ctx, embed=embed)
        
        if name not in playlists:
            available = ", ".join(f"`{p}`" for p in list(playlists.keys())[:5])
            embed = MusicEmbeds.error(f"Playlist **{name}** not found!\n\nAvailable: {available}")
            return await self._send_response(ctx, embed=embed)
        
        playlist_data = playlists[name]
        songs = playlist_data['songs']
        
        player = self.player_manager.get_player(ctx.guild)
        player.text_channel = ctx.channel
        
        # Check if actually connected, not just if client exists
        if not player.voice_client or not player.voice_client.is_connected():
            if ctx.author.voice:
                success = await player.connect(ctx.author.voice.channel)
                if not success:
                    embed = MusicEmbeds.error("Failed to join voice! Please try again in a moment.")
                    return await self._send_response(ctx, embed=embed)
            else:
                embed = MusicEmbeds.error("You're not in a voice channel!")
                return await self._send_response(ctx, embed=embed)
        
        loading_embed = discord.Embed(
            title="📋 Loading Playlist",
            description=f"Adding **{len(songs)}** tracks from **{name}**...",
            color=0x3498db
        )
        loading_msg = await self._send_response(ctx, embed=loading_embed)
        
        added = 0
        for song_data in songs:
            song = Song(
                source="pending",
                title=song_data['title'],
                url=song_data['url'],
                duration=song_data['duration'],
                thumbnail=song_data.get('thumbnail', ''),
                requester=ctx.author
            )
            await player.add_to_queue(song)
            added += 1
        
        if loading_msg:
            try:
                await loading_msg.delete()
            except:
                pass
        
        embed = MusicEmbeds.success(f"🎵 Loaded **{name}**\nAdded **{added}** tracks")
        await self._send_response(ctx, embed=embed)
    
    @playlist.command(name='list', description='Show your saved playlists')
    async def playlist_list(self, ctx):
        """List all saved playlists"""
        user_id = str(ctx.author.id)
        playlist_file = os.path.join('playlists', f'{user_id}.json')
        
        if not os.path.exists(playlist_file):
            embed = MusicEmbeds.info("You don't have any playlists yet!\n\nUse `/playlist save <name>`")
            return await self._send_response(ctx, embed=embed)
        
        try:
            with open(playlist_file, 'r', encoding='utf-8') as f:
                playlists = json.load(f)
        except:
            embed = MusicEmbeds.error("Error reading playlists!")
            return await self._send_response(ctx, embed=embed)
        
        if not playlists:
            embed = MusicEmbeds.info("You don't have any playlists yet!")
            return await self._send_response(ctx, embed=embed)
        
        embed = discord.Embed(
            title=f"🎵 Your Playlists ({len(playlists)})",
            color=0x3498db
        )
        
        for name, data in list(playlists.items())[:25]:
            embed.add_field(
                name=name,
                value=f"**{data['count']}** tracks",
                inline=True
            )
        
        embed.set_footer(text=f"Use /playlist load <name> to play")
        await self._send_response(ctx, embed=embed)
    
    @playlist.command(name='delete', description='Delete a saved playlist')
    @app_commands.describe(name='Playlist name')
    async def playlist_delete(self, ctx, *, name: str):
        """Delete a saved playlist"""
        user_id = str(ctx.author.id)
        playlist_file = os.path.join('playlists', f'{user_id}.json')
        
        if not os.path.exists(playlist_file):
            embed = MusicEmbeds.error("You don't have any playlists!")
            return await self._send_response(ctx, embed=embed)
        
        try:
            with open(playlist_file, 'r', encoding='utf-8') as f:
                playlists = json.load(f)
        except:
            embed = MusicEmbeds.error("Error reading playlists!")
            return await self._send_response(ctx, embed=embed)
        
        if name not in playlists:
            embed = MusicEmbeds.error(f"Playlist **{name}** not found!")
            return await self._send_response(ctx, embed=embed)
        
        del playlists[name]
        
        temp_file = playlist_file + ".tmp"

        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(playlists, f, indent=2, ensure_ascii=False)
        
        os.replace(temp_file, playlist_file)
        
        
        embed = MusicEmbeds.success(f"🗑️ Deleted **{name}**")
        await self._send_response(ctx, embed=embed)
    
    @playlist.command(name='info', description='Show playlist details')
    @app_commands.describe(name='Playlist name')
    async def playlist_info(self, ctx, *, name: str):
        """Show detailed playlist info"""
        user_id = str(ctx.author.id)
        playlist_file = os.path.join('playlists', f'{user_id}.json')
        
        if not os.path.exists(playlist_file):
            embed = MusicEmbeds.error("You don't have any playlists!")
            return await self._send_response(ctx, embed=embed)
        
        try:
            with open(playlist_file, 'r', encoding='utf-8') as f:
                playlists = json.load(f)
        except:
            embed = MusicEmbeds.error("Error reading playlists!")
            return await self._send_response(ctx, embed=embed)
        
        if name not in playlists:
            embed = MusicEmbeds.error(f"Playlist **{name}** not found!")
            return await self._send_response(ctx, embed=embed)
        
        playlist_data = playlists[name]
        songs = playlist_data['songs']
        
        total_duration = sum(s.get('duration', 0) for s in songs)
        hours, remainder = divmod(total_duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            duration_str = f"{hours}h {minutes}m"
        else:
            duration_str = f"{minutes}m {seconds}s"
        
        embed = discord.Embed(
            title=f"🎵 {name}",
            color=0x3498db
        )
        
        embed.add_field(name="Tracks", value=str(len(songs)), inline=True)
        embed.add_field(name="Duration", value=duration_str, inline=True)
        embed.add_field(name="Created", value=f"<t:{int(discord.utils.parse_time(playlist_data['created']).timestamp())}:R>", inline=True)
        
        if songs:
            track_list = "\n".join([
                f"{idx}. {song['title'][:45]}"
                for idx, song in enumerate(songs[:5], 1)
            ])
            if len(songs) > 5:
                track_list += f"\n*...and {len(songs) - 5} more*"
            
            embed.add_field(name="Tracks Preview", value=track_list, inline=False)
        
        embed.set_footer(text=f"Use /playlist load {name} to play")
        await self._send_response(ctx, embed=embed)

async def setup(bot):
    cog = Music(bot)
    await bot.add_cog(cog)
    logger.info("⚡ Music cog loaded - ULTRA-FAST mode active")
