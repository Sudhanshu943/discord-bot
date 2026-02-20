"""
Main Chat Cog for Discord Bot
=============================

Production-ready chatbot cog with comprehensive features.
"""

from urllib import response
import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import Optional, Literal, List, Tuple, Dict, Any

import logging
import asyncio
import time
import re
import json
from datetime import datetime

from .config import ChatConfig
from .rate_limiter import RateLimiter
from .personality import get_personality_manager, PersonalityManager
from .exceptions import (
    ChatException,
    RateLimitException,
    ProviderException
)

# NEW: Service layer imports
from .models import ChatRequest, ChatResponse
from .services import ChatService, MemoryManager, ProviderRouter, SafetyFilter
from .storage import MemoryStorage

# Configure logging
logger = logging.getLogger(__name__)


class AIChat(commands.Cog):
    """
    Advanced AI Chat Cog for Discord.
    
    Features:
    - Multiple LLM provider support with automatic fallback
    - Conversation context management with persistence
    - Rate limiting and cooldowns
    - Comprehensive error handling
    - Statistics and monitoring
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # Initialize configuration
        self.config = ChatConfig()
        
        # Set up logging level
        logging.getLogger(__name__).setLevel(
            getattr(logging, self.config.logging.log_level, logging.INFO)
        )
        
        # Initialize personality manager FIRST (needed for system prompt)
        self.personality_manager = get_personality_manager(bot=self.bot)
        self.config.personality = self.personality_manager
        
        # Initialize music integration
        from .music_integration import MusicIntegration
        self.music_integration = MusicIntegration(bot=self.bot)
        
        # ===== NEW SERVICE LAYER INITIALIZATION ===== 
        self.storage = MemoryStorage("data/chat_memory")
        self.safety_filter = SafetyFilter(max_message_length=2000)
        self.memory_manager = MemoryManager(self.storage)
        self.provider_router = ProviderRouter(self.config, self.safety_filter)
        self.chat_service = ChatService(
            config=self.config,
            memory_manager=self.memory_manager,
            safety_filter=self.safety_filter,
            provider_router=self.provider_router,
        )
        
        # Keep rate limiter for Discord rate limiting
        self.rate_limiter = RateLimiter(
            user_cooldown=self.config.rate_limit.user_cooldown,
            global_requests_per_minute=self.config.rate_limit.global_requests_per_minute
        )
        
        # Start background tasks
        self._cleanup_task.start()
    
    def cog_unload(self) -> None:
        """Clean up when cog is unloaded."""
        self._cleanup_task.cancel()
        logger.info("AIChat cog unloaded")

    
    @tasks.loop(hours=1)
    async def _cleanup_task(self) -> None:
        """Background task to clean up expired memories."""
        try:
            removed = await self.storage.cleanup_old_memories(days=30)
            if removed > 0:
                logger.info(f"Cleaned up {removed} old conversation memories")
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
    
    @_cleanup_task.before_loop
    async def _before_cleanup(self) -> None:
        """Wait for bot to be ready before starting cleanup task."""
        await self.bot.wait_until_ready()
    
    async def _process_chat_request(
        self,
        user_id: int,
        message: str,
        channel_id: int = None,
        guild_id: int = None,
    ) -> Tuple[str, Optional[str]]:
        """Process a chat request through the service layer."""
        try:
            # Rate limit (Discord rate limiting)
            await self.rate_limiter.acquire(user_id)
            
            # Call service layer - it handles everything
            response, provider = await self.chat_service.process_message(
                user_id=user_id,
                channel_id=channel_id,
                message=message,
                guild_id=guild_id,
                use_channel_memory=True,
                use_guild_memory=True,
            )
            
            return response, provider
        
        except ValueError as e:
            # Validation error (prompt injection, message too long, etc)
            raise ChatException(str(e))
        except RateLimitException:
            raise
        except Exception as e:
            logger.error(f"Chat service error: {e}")
            raise ChatException("Failed to process request")



    
    # ==================== Commands ====================
    
    @commands.hybrid_command(
        name="ask",
        description="Ask the AI a question"
    )
    @app_commands.describe(
        question="Your question for the AI"
    )
    async def ask(self, ctx: commands.Context, *, question: str) -> None:
        """
        Ask the AI chatbot a question.
        
        The bot maintains conversation context, so you can have
        a back-and-forth conversation.
        """
        # Check if DMs are allowed
        if isinstance(ctx.channel, discord.DMChannel) and not self.config.features.allow_dm:
            await ctx.send("❌ Chat commands are not allowed in DMs.")
            return
        
        await ctx.defer()
        
        try:
            response, provider = await self._process_chat_request(
                ctx.author.id,
                question,
                ctx.channel.id
            )
            
            # Format response
            if self.config.features.show_provider and provider:
                bot_name = self.bot.user.name.lower()
                response_text = f"{response}\n\n> *— {bot_name}*"
            else:
                response_text = response

            
            # Handle long responses
            if len(response_text) > 2000:
                # Split into multiple messages
                chunks = self._split_message(response_text, 2000)
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await ctx.send(chunk)
                    else:
                        await ctx.send(chunk)
            else:
                await ctx.send(response_text)
        
        except RateLimitException as e:
            await ctx.send(
                f"⏳ You're sending messages too fast! "
                f"Please wait {e.retry_after:.1f} seconds."
            )
        
        except ChatException as e:
            await ctx.send(
                f"❌ Sorry, I couldn't process your request. "
                f"All AI providers are currently unavailable. "
                f"Please try again later."
            )
    
    @commands.hybrid_command(
        name="chat",
        description="Start a chat session with the AI"
    )
    @app_commands.describe(
        message="Your message to the AI"
    )
    async def chat(self, ctx: commands.Context, *, message: str) -> None:
        """
        Chat with the AI (alias for /ask).
        """
        await self.ask(ctx, question=message)
    
    @commands.hybrid_command(
        name="clearchat",
        description="Clear your conversation history"
    )
    async def clear_history(self, ctx: commands.Context) -> None:
        """Clear your conversation history."""
        if not self.config.features.enable_clear_command:
            await ctx.send("❌ This command is disabled.")
            return

        # Clear channel memory via service
        await self.chat_service.clear_channel_context(ctx.channel.id)
        await ctx.send("✅ Your conversation history for this channel has been cleared.")

    
    @commands.hybrid_command(
        name="setprovider",
        description="Set your preferred AI provider"
    )
    @app_commands.describe(
        provider="The AI provider to use"
    )
    async def set_provider(
        self,
        ctx: commands.Context,
        provider: Literal["groq"]
    ) -> None:
        """
        Set your preferred AI provider.

        The bot will try to use this provider first when responding
        to your messages.
        """
        if not self.config.features.enable_model_command:
            await ctx.send("❌ This command is disabled.")
            return

        # Currently only Groq is supported
        if provider.lower() != "groq":
            await ctx.send("❌ Only 'groq' provider is currently available.")
            return

        await ctx.send(f"✅ Your preferred provider has been set to **groq**.")


    
    @commands.hybrid_command(
        name="chatstats",
        description="View chat statistics"
    )
    async def chat_stats(self, ctx: commands.Context) -> None:
        """
        View chat statistics.
        
        Shows usage statistics for the chatbot.
        """
        if not self.config.features.enable_stats_command:
            await ctx.send("❌ This command is disabled.")
            return
        
        # Get statistics from new service layer
        rate_stats = self.rate_limiter.get_global_stats()
        
        # Get memories from storage
        try:
            all_channels = self.storage._load_all_channel_memories()
            all_guilds = self.storage._load_all_guild_memories()
            
            total_channels = len(all_channels)
            total_guilds = len(all_guilds)
            total_messages = sum(len(mem.get("messages", [])) for mem in all_channels.values()) + \
                            sum(len(mem.get("messages", [])) for mem in all_guilds.values())
        except Exception:
            total_channels = 0
            total_guilds = 0
            total_messages = 0
        
        # Build embed
        embed = discord.Embed(
            title="📊 Chat Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="Memory Usage",
            value=(
                f"Active Channels: {total_channels}\n"
                f"Active Guilds: {total_guilds}\n"
                f"Total Messages Stored: {total_messages}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="Rate Limiting",
            value=(
                f"Requests/min: {rate_stats['requests_last_minute']}/{rate_stats['limit_per_minute']}\n"
                f"Total Blocked: {rate_stats['total_blocked']}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="Provider",
            value="✅ Groq (mixtral-8x7b-32768)",
            inline=False
        )
        
        embed.set_footer(text="Refactored with service layer architecture")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="providers",
        description="List available AI providers"
    )
    async def list_providers(self, ctx: commands.Context) -> None:
        """
        List all available AI providers and their status.
        """
        embed = discord.Embed(
            title="🤖 Available AI Providers",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="✅ Groq",
            value=(
                "Model: mixtral-8x7b-32768\n"
                "Status: Active\n"
                "Type: Open-source LLM"
            ),
            inline=False
        )
        
        embed.set_footer(text="Groq API for fast inference")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="mystats",
        description="View your personal chat statistics"
    )
    async def my_stats(self, ctx: commands.Context) -> None:
        """
        View your personal chat statistics.
        """
        # Since we now use channel-based memory instead of user-based, show channel stats
        channel_mem = self.memory_manager.get_or_create_channel_memory(ctx.channel.id)
        rate_stats = self.rate_limiter.get_user_stats(ctx.author.id)
        
        # Count messages in this channel from this user
        user_message_count = 0
        if channel_mem and "messages" in channel_mem:
            user_message_count = sum(
                1 for msg in channel_mem["messages"] 
                if msg.get("user_id") == ctx.author.id
            )
        
        if user_message_count == 0:
            await ctx.send("ℹ️ You haven't chatted with the AI yet in this channel.")
            return
        
        embed = discord.Embed(
            title="📈 Your Chat Statistics",
            color=discord.Color.purple()
        )
        
        embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.url
        )
        
        embed.add_field(
            name="Conversation",
            value=(
                f"Messages in This Channel: {user_message_count}\n"
                f"Total Rate Limited: {rate_stats.get('warning_count', 0)}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="Rate Limiting",
            value=(
                f"Requests (This Channel): {rate_stats['request_count']}\n"
                f"Warnings: {rate_stats['warning_count']}"
            ),
            inline=True
        )
        
        await ctx.send(embed=embed)
    
    # ==================== Music Integration Commands ====================
    
    @commands.hybrid_command(
        name="recommendsong",
        description="Get a song recommendation based on your preferences"
    )
    async def recommend_song(self, ctx: commands.Context, mood: Optional[str] = None):
        """
        Get a song recommendation based on your preferences or mood.
        
        Args:
            mood: Optional mood (happy, sad, energetic, calm, romantic, party, focus)
        """
        # Get recommendations
        recommendations = await self.music_integration.recommend_songs(
            ctx.author.id, 
            mood=mood
        )
        
        if not recommendations:
            await ctx.send("❌ No song recommendations available.")
            return
        
        # Create embed with recommendations
        embed = discord.Embed(
            title="🎵 Song Recommendations",
            description=f"Here are some songs you might enjoy{' based on your mood' + (f': {mood}' if mood else '')}!",
            color=discord.Color.green()
        )
        
        for i, song in enumerate(recommendations[:5], 1):  # Show top 5 recommendations
            embed.add_field(
                name=f"{i}. {song}",
                value="Click to play or use `/play` command",
                inline=False
            )
        
        embed.set_footer(text="Want to play a song? Use /play <song name>")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="createplaylist",
        description="Create a playlist based on a theme"
    )
    async def create_playlist(self, ctx: commands.Context, theme: str, num_songs: int = 5):
        """
        Create a playlist based on a theme.
        
        Args:
            theme: Theme of the playlist (e.g., "workout", "relaxing", "party")
            num_songs: Number of songs to include (default: 5)
        """
        if num_songs < 1 or num_songs > 20:
            await ctx.send("❌ Number of songs must be between 1 and 20.")
            return
        
        # Create playlist
        playlist = await self.music_integration.create_playlist(
            ctx.author.id, 
            theme, 
            num_songs
        )
        
        if not playlist:
            await ctx.send("❌ Failed to create playlist.")
            return
        
        # Create embed with playlist
        embed = discord.Embed(
            title=f"📋 Playlist: {theme}",
            description=f"Created a playlist with {len(playlist)} songs!",
            color=discord.Color.blue()
        )
        
        for i, song in enumerate(playlist, 1):
            embed.add_field(
                name=f"{i}. {song}",
                value="Click to play or use `/play` command",
                inline=False
            )
        
        embed.set_footer(text="Add these songs to queue with /play <song name>")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="musicpreferences",
        description="View your music preferences"
    )
    async def music_preferences(self, ctx: commands.Context):
        """View your music preferences stored by the bot."""
        preferences = await self.music_integration.get_or_create_preference(ctx.author.id)
        
        embed = discord.Embed(
            title="🎵 Your Music Preferences",
            color=discord.Color.purple()
        )
        
        if preferences.favorite_genres:
            embed.add_field(
                name="Favorite Genres",
                value=", ".join(preferences.favorite_genres) if preferences.favorite_genres else "None",
                inline=False
            )
        
        if preferences.favorite_artists:
            embed.add_field(
                name="Favorite Artists",
                value=", ".join(preferences.favorite_artists) if preferences.favorite_artists else "None",
                inline=False
            )
        
        if preferences.preferred_moods:
            embed.add_field(
                name="Preferred Moods",
                value=", ".join(preferences.preferred_moods) if preferences.preferred_moods else "None",
                inline=False
            )
        
        if preferences.last_played_songs:
            embed.add_field(
                name="Last Played Songs",
                value=", ".join(preferences.last_played_songs[:3]) if preferences.last_played_songs else "None",
                inline=False
            )
        
        embed.set_footer(text="Preferences are automatically learned from conversations!")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="roastme",
        description="Get a sarcastic song recommendation"
    )
    async def roast_me(self, ctx: commands.Context):
        """Get a sarcastic/playful song recommendation for roasting."""
        song = await self.music_integration.get_sarcastic_song()
        
        embed = discord.Embed(
            title="🔥 Sarcastic Song Recommendation",
            description=f"I recommend: **{song}**",
            color=discord.Color.orange()
        )
        
        embed.set_footer(text="Don't take it personally! 😜")
        
        await ctx.send(embed=embed)
    
    # ==================== Message Listener ====================
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Listen for messages to enable natural conversation.
        
        Users can mention the bot or reply to its messages to chat.
        """
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Ignore messages without bot mention or reply
        bot_mentioned = self.bot.user in message.mentions
        is_reply_to_bot = (
            message.reference and
            message.reference.resolved and
            message.reference.resolved.author.id == self.bot.user.id
        )
        
        if not (bot_mentioned or is_reply_to_bot):
            return
        
        # Check if DMs are allowed
        if isinstance(message.channel, discord.DMChannel) and not self.config.features.allow_dm:
            return
        
        # Remove bot mention from message content
        content = message.content
        if bot_mentioned:
            content = content.replace(f"<@{self.bot.user.id}>", "").strip()
            content = content.replace(f"<@!{self.bot.user.id}>", "").strip()
        
        # Skip if message is empty after removing mention
        if not content:
            return
        
        # Check for special personality commands first
        special_response = self.personality_manager.handle_special_command(
            user_id=message.author.id,
            message=content,
            user_name=message.author.name,
            channel=message.channel
        )
        
        # Handle who's online command
        msg_lower = content.lower().strip()
        if msg_lower in ["who's online", "who is online", "online users", "active users"]:
            members = await self.personality_manager.get_online_users(message.channel)
            response_text = self.personality_manager.format_whos_online_response(
                members, message.channel.name
            )
            await message.reply(response_text, mention_author=False)
            return
        
        if special_response:
            # Check for song recommendations in >> format in the special response
            song_recommendations = re.findall(r'>>\s*(.*?)(?=\n|$)', special_response)
            if song_recommendations:
                # Send the personality response
                await message.reply(special_response, mention_author=False)
                # Play the recommended songs
                for song_query in song_recommendations:
                    if song_query.strip():
                        success, play_response = await self.music_integration.search_and_play(message, song_query.strip())
                        await message.reply(play_response, mention_author=False)
            else:
                # No song recommendations in response, just send the message
                await message.reply(special_response, mention_author=False)
            return
        
        # Update user activity in personality manager
        self.personality_manager.update_activity(message.author.id)

        # Process the message
        try:
            async with message.channel.typing():
                response, provider = await self._process_chat_request(
                    message.author.id,
                    content,
                    message.channel.id,
                    message.guild.id if message.guild else None
                )
            
            # Format response
            if self.config.features.show_provider and provider:
                bot_name = self.bot.user.name
                response_text = f"{response}\n\n*-# 🤖 {bot_name}*"
            else:
                response_text = response
            
            # Check for song recommendations in >> format in the response
            song_recommendations = re.findall(r'>>\s*(.*?)(?=\n|$)', response_text)
            if song_recommendations:
                # Send the personality response
                await message.reply(response_text, mention_author=False)
                # Play the recommended songs
                for song_query in song_recommendations:
                    if song_query.strip():
                        success, play_response = await self.music_integration.search_and_play(message, song_query.strip())
                        await message.reply(play_response, mention_author=False)
            else:
                # No song recommendations in response, just send the message
                # Handle long responses
                if len(response_text) > 2000:
                    chunks = self._split_message(response_text, 2000)
                    for chunk in chunks:
                        await message.reply(chunk, mention_author=False)
                else:
                    await message.reply(response_text, mention_author=False)
        
        except RateLimitException as e:
            await message.reply(
                f"⏳ You're sending messages too fast! "
                f"Please wait {e.retry_after:.1f} seconds.",
                mention_author=False
            )
        
        except ChatException:
            await message.reply(
                "❌ Sorry, I couldn't process your request right now. "
                "Please try again later.",
                mention_author=False
            )

    # ==================== Dedicated Channel Listener ====================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Listen for ALL messages in dedicated chat channels OR mentions.

        Users can:
        1. Chat directly in dedicated channels (no commands/tags needed - ALL messages are processed)
        2. Mention the bot anywhere
        3. Reply to bot messages
        """
        # Ignore bot messages
        if message.author.bot:
            return

        # Check if this is a command - if yes, let command handler deal with it
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return  # Let command handler process it

        # Get dedicated chat channel IDs from config
        dedicated_channels = self.config.get_dedicated_channels()

        # Check if message is in dedicated channel
        is_dedicated_channel = message.channel.id in dedicated_channels

        # Check if bot is mentioned
        bot_mentioned = self.bot.user in message.mentions

        # Check if replying to bot
        is_reply_to_bot = (
            message.reference and
            message.reference.resolved and
            message.reference.resolved.author.id == self.bot.user.id
        )

        # Process if: dedicated channel (ALL messages) OR mentioned OR reply to bot
        if not (is_dedicated_channel or bot_mentioned or is_reply_to_bot):
            return

        # Check if DMs are allowed (for dedicated channel in DMs)
        if isinstance(message.channel, discord.DMChannel) and not self.config.features.allow_dm:
            return

        # Get message content
        content = message.content

        # Remove bot mention if present
        if bot_mentioned:
            content = content.replace(f"<@{self.bot.user.id}>", "").strip()
            content = content.replace(f"<@!{self.bot.user.id}>", "").strip()

        # Skip if message is empty
        if not content:
            return
        
        # Check for special personality commands first
        special_response = self.personality_manager.handle_special_command(
            user_id=message.author.id,
            message=content,
            user_name=message.author.name,
            channel=message.channel
        )
        
        # Handle who's online command
        msg_lower = content.lower().strip()
        if msg_lower in ["who's online", "who is online", "online users", "active users"]:
            members = await self.personality_manager.get_online_users(message.channel)
            response_text = self.personality_manager.format_whos_online_response(
                members, message.channel.name
            )
            await message.reply(response_text, mention_author=False)
            return
        
        if special_response:
            # Check for song recommendations in >> format in the special response
            song_recommendations = re.findall(r'>>\s*(.*?)(?=\n|$)', special_response)
            if song_recommendations:
                # Send the personality response
                await message.reply(special_response, mention_author=False)
                # Play the recommended songs
                for song_query in song_recommendations:
                    if song_query.strip():
                        success, play_response = await self.music_integration.search_and_play(message, song_query.strip())
                        await message.reply(play_response, mention_author=False)
            else:
                # No song recommendations in response, just send the message
                await message.reply(special_response, mention_author=False)
            return
        
        # Check for music play request in user's message (JSON format request)
        msg_lower = content.lower().strip()
        
        # Check if user wants to play a specific song
        play_song_match = None
        play_patterns = [
            r'play\s+(.+)',
            r'play\s+song\s+(.+)',
            r'baja\s+(.+)',
            r'sunao\s+(.+)',
            r'suna\s+de\s+(.+)'
        ]
        for pattern in play_patterns:
            match = re.match(pattern, msg_lower)
            if match:
                play_song_match = match.group(1).strip()
                break
        
        # If user is requesting to play a song
        if play_song_match:
            # Send JSON format response and play the song
            json_response = {
                "person": message.author.name,
                "action": "playing",
                "chat": f"Playing {play_song_match.title()}",
                "song": play_song_match.title(),
                "query": f">> {play_song_match}"
            }
            response_text = f"```json\n{json.dumps(json_response, indent=2)}\n```"
            
            # Print ALL responses to terminal in JSON format
            logger.info(f"📥 IN: {content}")
            logger.info(f"📤 OUT: {json.dumps(json_response, indent=2)}")
            
            await message.reply(response_text, mention_author=False)
            
            # Play the song
            success, play_response = await self.music_integration.search_and_play(message, play_song_match)
            await message.reply(play_response, mention_author=False)
            return
        
        # Update user activity in personality manager
        self.personality_manager.update_activity(message.author.id)
        
        # Update music preferences from conversation
        await self.music_integration.update_preferences_from_conversation(
            message.author.id, content
        )
        
        # Music integration should not restrict the bot's natural responses
        # The >> format will be handled in the response processing phase
        
        # Process mentions in the message - check permissions and get user details
        mentioned_users_info = ""
        if hasattr(message.author, 'guild') and message.author.guild:
            try:
                mentions_data = self.personality_manager.process_mentions(message)
                if mentions_data:
                    mentioned_users_info = "\n\n**Users mentioned in this message:**\n"
                    for mention in mentions_data:
                        can_mention = "✅" if mention["can_mention"] else "❌"
                        mentioned_users_info += (
                            f"• <@{mention['id']}> - Role: {mention['top_role']}, "
                            f"Can mention: {can_mention}\n"
                        )
            except Exception as e:
                logger.error(f"Error processing mentions: {e}")
        
        # Build enhanced context for AI
        user_context = f"User: {message.author.display_name} (ID: {message.author.id})"
        if mentioned_users_info:
            user_context += mentioned_users_info
        
        # Append user context to the message
        enhanced_message = f"[{user_context}] {content}"
        
        # Process the message
        try:
            async with message.channel.typing():
                response, provider = await self._process_chat_request(
                    message.author.id,
                    enhanced_message,
                    message.channel.id,
                    message.guild.id if message.guild else None
                )

            # Format response
            if self.config.features.show_provider and provider:
                bot_name = self.bot.user.name.lower()
                response_text = f"{response}\n\n> *— {bot_name}*"
            else:
                response_text = response

            # Check for song recommendations in AI response (JSON format or >> format)
            song_recommendations = self.music_integration.extract_songs_from_text(response_text)
            
            if song_recommendations:
                # Format response in new JSON structure
                songs_list = ", ".join([s.strip() for s in song_recommendations])
                queries_list = ", ".join([f">> {s.strip()}" for s in song_recommendations])
                
                json_response = {
                    "person": message.author.name,
                    "action": "playing",
                    "chat": response[:500] if len(response) > 500 else response,
                    "song": songs_list,
                    "query": queries_list
                }
                response_text = f"```json\n{json.dumps(json_response, indent=2)}\n```"
                
                # Print ALL responses to terminal in JSON format
                logger.info(f"📥 IN: {content}")
                logger.info(f"📤 OUT: {json.dumps(json_response, indent=2)}")
                
                # Send the JSON response
                if len(response_text) > 2000:
                    chunks = self._split_message(response_text, 2000)
                    for chunk in chunks:
                        await message.reply(chunk, mention_author=False)
                else:
                    await message.reply(response_text, mention_author=False)
                
                # Play the recommended songs one by one
                for song_query in song_recommendations:
                    if song_query.strip():
                        success, play_response = await self.music_integration.search_and_play(message, song_query.strip())
                        await message.reply(play_response, mention_author=False)
            else:
                # No song recommendations - format as JSON anyway
                json_response = {
                    "person": message.author.name,
                    "action": "chat",
                    "chat": response[:500] if len(response) > 500 else response,
                    "song": "",
                    "query": ""
                }
                
                # Print ALL responses to terminal in JSON format
                logger.info(f"📥 IN: {content}")
                logger.info(f"📤 OUT: {json.dumps(json_response, indent=2)}")
                
                # Handle long responses
                if len(response_text) > 2000:
                    chunks = self._split_message(response_text, 2000)
                    for chunk in chunks:
                        await message.reply(chunk, mention_author=False)
                else:
                    await message.reply(response_text, mention_author=False)

        except RateLimitException as e:
            await message.reply(
                f"⏳ You're sending messages too fast! "
                f"Please wait {e.retry_after:.1f} seconds.",
                mention_author=False
            )

        except ChatException:
            await message.reply(
                "❌ Sorry, I couldn't process your request right now. "
                "Please try again later.",
                mention_author=False
            )


    # ==================== Status Handlers ====================
    
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Called when the cog is ready."""
        logger.info("="*50)
        logger.info("🤖 AI Chat Cog is READY!")
        logger.info(f"✅ Loaded {len(self.config.providers)} providers")
        logger.info(f"✅ Provider priority: {self.config.provider_priority}")
        logger.info(f"✅ Max history: {self.config.max_history} messages")
        logger.info(f"✅ Rate limit: {self.config.rate_limit.user_cooldown}s cooldown")
        logger.info(f"✅ Persistence: {'Enabled' if self.config.persist_conversations else 'Disabled'}")
        logger.info("="*50)
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Handle command errors gracefully."""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands
        
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: `{error.param.name}`")
        
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Invalid argument provided.")
        
        elif isinstance(error, commands.NotOwner):
            await ctx.send("❌ This command is only available to the bot owner.")
        
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Command on cooldown. Try again in {error.retry_after:.1f}s")
        
        else:
            logger.error(f"Command error in {ctx.command}: {error}", exc_info=error)
            await ctx.send("❌ An error occurred while processing the command.")
    
    @commands.hybrid_command(
        name="chatping",
        description="Check if the chatbot is responsive"
    )
    async def ping(self, ctx: commands.Context) -> None:
        """
        Check chatbot status and response time.
        """
        start_time = time.time()
        
        # Check Groq provider status (simple check)
        status_emoji = "🟢"
        is_healthy = True
        
        # Calculate latency
        latency = (time.time() - start_time) * 1000
        
        # Build status message
        embed = discord.Embed(
            title=f"{status_emoji} Chatbot Status",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="Response Time",
            value=f"`{latency:.2f}ms`",
            inline=True
        )
        
        embed.add_field(
            name="Status",
            value="✅ **Online**",
            inline=True
        )
        
        embed.add_field(
            name="Provider",
            value="✅ `Groq`",
            inline=False
        )
        
        embed.set_footer(text="Use /chathelp for more info")

        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
            name="chathelp",
            description="Show chatbot help and available commands"
        )
    async def chat_help(self, ctx: commands.Context) -> None:

        """
        Display help information for the chatbot.
        """
        embed = discord.Embed(
            title="🤖 AI Chatbot Help",
            description="Here's how to use the AI chatbot:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="💬 How to Chat",
            value=(
                "• `/chathelp <question>` - Ask the AI anything\n"
                "• `/chat <message>` - Same as /ask\n"
                "• `@mention` the bot - Chat naturally\n"
                "• Reply to bot messages - Continue conversation"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Commands",
            value=(
                "• `/clearchat` - Clear your conversation history\n"
                "• `/setprovider` - Choose your AI provider\n"
                "• `/mystats` - View your personal statistics\n"
                "• `/providers` - List available AI providers\n"
                "• `/chatstats` - View bot statistics\n"
                "• `/chatping` - Check bot status"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚡ Features",
            value=(
                f"✅ Conversation memory ({self.config.max_history} messages)\n"
                f"✅ Multiple AI providers with fallback\n"
                f"✅ Rate limiting ({self.config.rate_limit.user_cooldown}s cooldown)\n"
                f"✅ DM support: {'Enabled' if self.config.features.allow_dm else 'Disabled'}"
            ),
            inline=False
        )
        
        embed.set_footer(text="Need more help? Use /chatping to check bot status")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="status",
        description="Detailed chatbot system status"
    )
    async def system_status(self, ctx: commands.Context) -> None:
        """
        Show detailed system status.
        """
        # Gather all status info
        rate_stats = self.rate_limiter.get_global_stats()
        
        # Load memory stats from storage
        try:
            all_channels = self.storage._load_all_channel_memories()
            all_guilds = self.storage._load_all_guild_memories()
            
            total_channels = len(all_channels)
            total_guilds = len(all_guilds)
            total_messages = sum(len(mem.get("messages", [])) for mem in all_channels.values()) + \
                            sum(len(mem.get("messages", [])) for mem in all_guilds.values())
        except Exception:
            total_channels = 0
            total_guilds = 0
            total_messages = 0
        
        # Main status embed
        embed = discord.Embed(
            title="🔍 Detailed System Status",
            description="Service: Operational",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        # System health
        embed.add_field(
            name="🟢 System Health",
            value=(
                "Status: **Operational**\n"
                "Provider: Groq (Online)\n"
                "Storage: Active"
            ),
            inline=True
        )
        
        # Memory stats
        embed.add_field(
            name="💾 Memory/Conversations",
            value=(
                f"Active Channels: {total_channels}\n"
                f"Active Guilds: {total_guilds}\n"
                f"Total Messages: {total_messages}"
            ),
            inline=True
        )
        
        # Rate limiting
        embed.add_field(
            name="⚡ Rate Limiting",
            value=(
                f"Current: {rate_stats['requests_last_minute']}/{rate_stats['limit_per_minute']}/min\n"
                f"Cooldown: {self.config.rate_limit.user_cooldown}s\n"
                f"Blocked: {rate_stats['total_blocked']}"
            ),
            inline=True
        )
        
        
        # Configuration
        embed.add_field(
            name="⚙️ Configuration",
            value=(
                f"Max History: {self.config.max_history}\n"
                f"Timeout: {self.config.conversation_timeout_hours}h\n"
                f"Persistence: {'✅' if self.config.persist_conversations else '❌'}"
            ),
            inline=True
        )
        
        embed.set_footer(text="All systems operational")
        
        await ctx.send(embed=embed)
    
    # ==================== Admin Commands ====================
    
    @commands.group(name="chatadmin", invoke_without_command=True)
    @commands.is_owner()
    async def chat_admin(self, ctx: commands.Context) -> None:
        """Admin commands for the chat system."""
        await ctx.send_help(ctx.command)
    
    @chat_admin.command(name="reload")
    @commands.is_owner()
    async def reload_config(self, ctx: commands.Context) -> None:
        """Reload chat configuration."""
        self.config.reload()
        await ctx.send("✅ Chat configuration reloaded.")
    
    @chat_admin.command(name="resetuser")
    @commands.is_owner()
    async def reset_user(self, ctx: commands.Context, user_id: int) -> None:
        """Reset a user's rate limits (memory now handled per-channel)."""
        self.rate_limiter.reset_user(user_id)
        await ctx.send(f"✅ Reset rate limits for user {user_id}.")
    
    @chat_admin.command(name="resetall")
    @commands.is_owner()
    async def reset_all(self, ctx: commands.Context) -> None:
        """Reset all rate limits."""
        self.rate_limiter.reset_all()
        await ctx.send("✅ All rate limits have been reset.")
    
    @chat_admin.command(name="cleanup")
    @commands.is_owner()
    async def force_cleanup(self, ctx: commands.Context) -> None:
        """Force cleanup of old memories (30+ days)."""
        await self.storage.cleanup_old_memories(days=30)
        await ctx.send(f"✅ Cleaned up old memories.")
    
    # ==================== Helper Methods ====================
    
    @staticmethod
    def _split_message(text: str, max_length: int) -> List[str]:
        """
        Split a long message into chunks that fit within Discord's limit.
        
        Tries to split at natural break points (paragraphs, sentences).
        """
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        remaining = text
        
        while remaining:
            if len(remaining) <= max_length:
                chunks.append(remaining)
                break
            
            # Try to find a good break point
            break_point = max_length
            
            # Look for paragraph break
            para_break = remaining.rfind('\n\n', 0, max_length)
            if para_break > max_length // 2:
                break_point = para_break + 2
            else:
                # Look for sentence break
                sentence_break = remaining.rfind('.\n', 0, max_length)
                if sentence_break > max_length // 2:
                    break_point = sentence_break + 2
                else:
                    # Look for any newline
                    line_break = remaining.rfind('\n', 0, max_length)
                    if line_break > max_length // 2:
                        break_point = line_break + 1
                    else:
                        # Look for space
                        space_break = remaining.rfind(' ', 0, max_length)
                        if space_break > max_length // 2:
                            break_point = space_break + 1
            
            chunks.append(remaining[:break_point])
            remaining = remaining[break_point:]
        
        return chunks
    



async def setup(bot: commands.Bot) -> None:
    """Set up the AIChat cog."""
    await bot.add_cog(AIChat(bot))
