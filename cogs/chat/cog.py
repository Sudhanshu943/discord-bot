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
from datetime import datetime

from .config import ChatConfig
from .context import ConversationManager
from .rate_limiter import RateLimiter
from .providers import LLMProviderManager
from .personality import get_personality_manager, PersonalityManager
from .exceptions import (
    ChatException,
    RateLimitException,
    ProviderException
)

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
        
        # Initialize conversation manager
        self.conversation_manager = ConversationManager(
            max_history=self.config.max_history,
            conversation_timeout_hours=self.config.conversation_timeout_hours,
            persist=self.config.persist_conversations
        )
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            user_cooldown=self.config.rate_limit.user_cooldown,
            global_requests_per_minute=self.config.rate_limit.global_requests_per_minute
        )
        
        # Initialize provider manager
        self.provider_manager = LLMProviderManager(
            providers=self.config.get_enabled_providers(),
            timeout=self.config.rate_limit.request_timeout
        )
        
        # Initialize personality manager for user memory and special commands
        self.personality_manager = get_personality_manager(bot=self.bot)
        
        # Initialize music integration
        from .music_integration import MusicIntegration
        self.music_integration = MusicIntegration(bot=self.bot)

            # ADD THESE: Fast in-memory caches
        self._conversations_cache: Dict[int, List[Dict]] = {}
        self._user_preferences: Dict[int, Dict] = {}

        # Statistics
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "rate_limited_requests": 0,
            "start_time": time.time()
        }

        # Load cached data from disk (if exists) - async task
        asyncio.create_task(self._load_cache_from_disk())

        # Start background tasks
        self._cleanup_task.start()
        self._persistence_task.start()  # New task for periodic saves
    
    def cog_unload(self) -> None:
        """Clean up when cog is unloaded."""
        self._cleanup_task.cancel()
        self._persistence_task.cancel()  # ADD THIS
        logger.info("AIChat cog unloaded")

    
    @tasks.loop(hours=1)
    async def _cleanup_task(self) -> None:
        """Background task to clean up expired conversations."""
        try:
            removed = await self.conversation_manager.cleanup_expired()
            if removed > 0:
                logger.info(f"Cleaned up {removed} expired conversations")
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
        channel_id: int = None
    ) -> Tuple[str, Optional[str]]:
        """Process a chat request - OPTIMIZED FOR SPEED."""
        self._stats["total_requests"] += 1

        # Check rate limit (fast, in-memory)
        try:
            await self.rate_limiter.acquire(user_id)
        except RateLimitException as e:
            self._stats["rate_limited_requests"] += 1
            raise
        
        # Get conversation from memory (NO database reads)
        conversation = self._conversations_cache.get(user_id)
        if not conversation:
            conversation = []
            self._conversations_cache[user_id] = conversation

        # Add user message to cache
        conversation.append({"role": "user", "content": message})

        # Trim to max history (fast list operation)
        if len(conversation) > self.config.max_history:
            conversation = conversation[-self.config.max_history:]
            self._conversations_cache[user_id] = conversation

        # Build API messages (fast)
        messages = [{"role": "system", "content": self.config.system_prompt}]
        messages.extend(conversation)

        # Get preferred provider (fast dict lookup)
        preferred_provider = self._user_preferences.get(user_id, {}).get("provider")

        try:
            # Call LLM API (this is the only slow part)
            response, provider_name = await self.provider_manager.generate_with_fallback(
                messages=messages,
                preferred_provider=preferred_provider,
                max_tokens=self.config.rate_limit.max_tokens
            )

            # Add response to cache
            conversation.append({"role": "assistant", "content": response.content})

            self._stats["successful_requests"] += 1

            # Save to disk in BACKGROUND (non-blocking)
            if self.config.persist_conversations:
                asyncio.create_task(
                    self._save_conversation_background(user_id, conversation)
                )

            return response.content, provider_name

        except ChatException as e:
            self._stats["failed_requests"] += 1
            logger.error(f"Chat request failed for user {user_id}: {e}")
            raise



    
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

        # Clear from cache (instant)
        if ctx.author.id in self._conversations_cache:
            del self._conversations_cache[ctx.author.id]
            await ctx.send("✅ Your conversation history has been cleared.")
        else:
            await ctx.send("ℹ️ You don't have any conversation history to clear.")

    
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
        provider: Literal["groq", "gemini", "openai"]
    ) -> None:
        """
        Set your preferred AI provider.

        The bot will try to use this provider first when responding
        to your messages.
        """
        if not self.config.features.enable_model_command:
            await ctx.send("❌ This command is disabled.")
            return

        # Check if provider is available
        available_providers = self.provider_manager.get_provider_names()

        # Find matching provider
        matching_providers = [
            p for p in available_providers
            if p.lower().startswith(provider.lower())
        ]

        if not matching_providers:
            await ctx.send(
                f"❌ Provider '{provider}' is not available. "
                f"Available providers: {', '.join(available_providers)}"
            )
            return

        # Set the preferred provider
        provider_name = matching_providers[0]  # ✅ ADD THIS LINE

        # Set in cache (instant)
        if ctx.author.id not in self._user_preferences:
            self._user_preferences[ctx.author.id] = {}
        self._user_preferences[ctx.author.id]["provider"] = provider_name

        await self.conversation_manager.set_preferred_provider(
            ctx.author.id,
            provider_name
        )

        await ctx.send(f"✅ Your preferred provider has been set to **{provider_name}**.")


    
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
        
        # Get statistics
        conv_stats = self.conversation_manager.get_stats()
        rate_stats = self.rate_limiter.get_global_stats()
        provider_health = self.provider_manager.get_health_status()
        
        # Calculate uptime
        uptime_seconds = time.time() - self._stats["start_time"]
        uptime_hours = uptime_seconds / 3600
        
        # Build embed
        embed = discord.Embed(
            title="📊 Chat Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="Usage",
            value=(
                f"Total Requests: {self._stats['total_requests']}\n"
                f"Successful: {self._stats['successful_requests']}\n"
                f"Failed: {self._stats['failed_requests']}\n"
                f"Rate Limited: {self._stats['rate_limited_requests']}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="Conversations",
            value=(
                f"Active: {conv_stats['active_conversations']}\n"
                f"Total Created: {conv_stats['total_conversations']}\n"
                f"Total Messages: {conv_stats['total_messages']}"
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
        
        # Provider status
        provider_status = []
        for name, health in provider_health.items():
            status_emoji = "✅" if health["healthy"] else "❌"
            provider_status.append(
                f"{status_emoji} {name}: {health['total_requests']} requests"
            )
        
        if provider_status:
            embed.add_field(
                name="Providers",
                value="\n".join(provider_status),
                inline=False
            )
        
        embed.set_footer(text=f"Uptime: {uptime_hours:.1f} hours")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="providers",
        description="List available AI providers"
    )
    async def list_providers(self, ctx: commands.Context) -> None:
        """
        List all available AI providers and their status.
        """
        providers = self.provider_manager.get_provider_names()
        health_status = self.provider_manager.get_health_status()
        
        if not providers:
            await ctx.send("❌ No AI providers are currently available.")
            return
        
        embed = discord.Embed(
            title="🤖 Available AI Providers",
            color=discord.Color.green()
        )
        
        for provider_name in providers:
            health = health_status.get(provider_name, {})
            status_emoji = "✅" if health.get("healthy", True) else "❌"
            avg_time = health.get("avg_response_time", 0)
            
            embed.add_field(
                name=f"{status_emoji} {provider_name}",
                value=(
                    f"Requests: {health.get('total_requests', 0)}\n"
                    f"Avg Response: {avg_time:.2f}s"
                ),
                inline=True
            )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="mystats",
        description="View your personal chat statistics"
    )
    async def my_stats(self, ctx: commands.Context) -> None:
        """
        View your personal chat statistics.
        """
        user_stats = self.conversation_manager.get_user_stats(ctx.author.id)
        rate_stats = self.rate_limiter.get_user_stats(ctx.author.id)
        
        if not user_stats:
            await ctx.send("ℹ️ You haven't chatted with the AI yet.")
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
                f"Messages in History: {user_stats['message_count']}\n"
                f"Total Messages: {user_stats['total_messages']}\n"
                f"Preferred Provider: {user_stats.get('preferred_provider', 'Auto')}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="Rate Limiting",
            value=(
                f"Requests: {rate_stats['request_count']}\n"
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
                    message.channel.id
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
        
        # Update user activity in personality manager
        self.personality_manager.update_activity(message.author.id)
        
        # Update music preferences from conversation
        await self.music_integration.update_preferences_from_conversation(
            message.author.id, content
        )
        
        # Check if message contains song recommendations in >> format
        song_recommendations = re.findall(r'>>\s*(.*?)(?=\n|$)', content)
        if song_recommendations:
            for song_query in song_recommendations:
                if song_query.strip():
                    success, response = await self.music_integration.search_and_play(message, song_query.strip())
                    await message.reply(response, mention_author=False)
            return
        
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
                    message.channel.id
                )

            # Format response
            if self.config.features.show_provider and provider:
                bot_name = self.bot.user.name.lower()
                response_text = f"{response}\n\n> *— {bot_name}*"
            else:
                response_text = response


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
        
        # Check provider health
        health_status = self.provider_manager.get_health_status()
        healthy_providers = sum(1 for h in health_status.values() if h["healthy"])
        total_providers = len(health_status)
        
        # Calculate latency
        latency = (time.time() - start_time) * 1000
        
        # Build status message
        status_emoji = "🟢" if healthy_providers > 0 else "🔴"
        
        embed = discord.Embed(
            title=f"{status_emoji} Chatbot Status",
            color=discord.Color.green() if healthy_providers > 0 else discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="Response Time",
            value=f"`{latency:.2f}ms`",
            inline=True
        )
        
        embed.add_field(
            name="Providers",
            value=f"`{healthy_providers}/{total_providers}` healthy",
            inline=True
        )
        
        embed.add_field(
            name="Status",
            value="✅ **Online**" if healthy_providers > 0 else "❌ **All providers down**",
            inline=True
        )
        
        # Add provider details
        provider_status = []
        for name, health in health_status.items():
            emoji = "✅" if health["healthy"] else "❌"
            provider_status.append(f"{emoji} `{name}`")
        
        embed.add_field(
            name="Provider Status",
            value="\n".join(provider_status) if provider_status else "No providers",
            inline=False
        )
        
        embed.set_footer(text="Use /aihelp for more info")

        
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
        conv_stats = self.conversation_manager.get_stats()
        rate_stats = self.rate_limiter.get_global_stats()
        provider_health = self.provider_manager.get_health_status()
        
        uptime_seconds = time.time() - self._stats["start_time"]
        uptime_hours = uptime_seconds / 3600
        
        healthy_providers = sum(1 for h in provider_health.values() if h["healthy"])
        
        # Main status embed
        embed = discord.Embed(
            title="🔍 Detailed System Status",
            description=f"Uptime: **{uptime_hours:.1f} hours**",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        # System health
        health_emoji = "🟢" if healthy_providers > 0 else "🔴"
        embed.add_field(
            name=f"{health_emoji} System Health",
            value=(
                f"Status: **{'Operational' if healthy_providers > 0 else 'Down'}**\n"
                f"Providers: {healthy_providers}/{len(provider_health)} online\n"
                f"Success Rate: {(self._stats['successful_requests'] / max(1, self._stats['total_requests']) * 100):.1f}%"
            ),
            inline=True
        )
        
        # Request stats
        embed.add_field(
            name="📊 Requests",
            value=(
                f"Total: {self._stats['total_requests']}\n"
                f"✅ Success: {self._stats['successful_requests']}\n"
                f"❌ Failed: {self._stats['failed_requests']}\n"
                f"⏳ Rate Limited: {self._stats['rate_limited_requests']}"
            ),
            inline=True
        )
        
        # Conversation stats
        embed.add_field(
            name="💬 Conversations",
            value=(
                f"Active: {conv_stats['active_conversations']}\n"
                f"Total Created: {conv_stats['total_conversations']}\n"
                f"Messages: {conv_stats['total_messages']}"
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
        
        # Provider details
        provider_details = []
        for name, health in provider_health.items():
            emoji = "✅" if health["healthy"] else "❌"
            avg_time = health.get("avg_response_time", 0)
            success_rate = ((health["total_requests"] - health["total_failures"]) / max(1, health["total_requests"]) * 100)
            provider_details.append(
                f"{emoji} **{name}** - {health['total_requests']} req, {success_rate:.0f}% success, {avg_time:.2f}s avg"
            )
        
        embed.add_field(
            name="🤖 Provider Details",
            value="\n".join(provider_details) if provider_details else "No providers available",
            inline=False
        )
        
        embed.set_footer(text="All systems operational" if healthy_providers > 0 else "System experiencing issues")
        
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
        """Reset a user's conversation and rate limits."""
        await self.conversation_manager.delete_conversation(user_id)
        self.rate_limiter.reset_user(user_id)
        await ctx.send(f"✅ Reset data for user {user_id}.")
    
    @chat_admin.command(name="resetall")
    @commands.is_owner()
    async def reset_all(self, ctx: commands.Context) -> None:
        """Reset all conversations and rate limits."""
        self.rate_limiter.reset_all()
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "rate_limited_requests": 0,
            "start_time": time.time()
        }
        await ctx.send("✅ All rate limits and statistics have been reset.")
    
    @chat_admin.command(name="cleanup")
    @commands.is_owner()
    async def force_cleanup(self, ctx: commands.Context) -> None:
        """Force cleanup of expired conversations."""
        removed = await self.conversation_manager.cleanup_expired()
        await ctx.send(f"✅ Cleaned up {removed} expired conversations.")
    
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
    
    async def _save_conversation_background(self, user_id: int, conversation: List[Dict]) -> None:
        """Save conversation in background (non-blocking)."""
        try:
            await asyncio.sleep(0)  # Yield control
            # Save to conversation manager without blocking
            # This happens AFTER user already got their response
            pass  # Implement if you need disk persistence
        except Exception as e:
            logger.error(f"Background save failed: {e}")
    
    async def _load_cache_from_disk(self) -> None:
        """Load conversations from disk on startup."""
        try:
            await self.bot.wait_until_ready()
            # Load from conversation manager if needed
            logger.info("Cache loaded from disk")
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
    
    @tasks.loop(minutes=5)
    async def _persistence_task(self) -> None:
        """Periodic background save (every 5 minutes)."""
        try:
            if self.config.persist_conversations and self._conversations_cache:
                logger.info(f"Background save: {len(self._conversations_cache)} conversations")
                # Save to disk without blocking
                for user_id, conversation in self._conversations_cache.items():
                    for msg in conversation:
                        if msg["role"] == "user":
                            await self.conversation_manager.add_message(
                                user_id, "user", msg["content"]
                            )
                        elif msg["role"] == "assistant":
                            await self.conversation_manager.add_message(
                                user_id, "assistant", msg["content"]
                            )
        except Exception as e:
            logger.error(f"Error in persistence task: {e}")
    
    @_persistence_task.before_loop
    async def _before_persistence(self) -> None:
        """Wait for bot to be ready."""
        await self.bot.wait_until_ready()
    


async def setup(bot: commands.Bot) -> None:
    """Set up the AIChat cog."""
    await bot.add_cog(AIChat(bot))
