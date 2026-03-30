"""
Chat Cog - Main Chat Command Handler
====================================

Discord-specific implementation for chat commands.
Handles on_message events and chat-related slash commands.
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import Optional, List, Tuple
import logging
import time
import re
import json
from datetime import datetime

from ..core import ChatConfig, RateLimiter, get_personality_manager
from ..core import ChatException, RateLimitException
from ..models import ChannelMemory, GuildMemory
from ..services import ChatService, MemoryManager, ProviderRouter, SafetyFilter
from ..storage import MemoryStorage


logger = logging.getLogger(__name__)


class ChatCog(commands.Cog):
    """Advanced AI Chat Cog for Discord."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.config = ChatConfig()
        logging.getLogger(__name__).setLevel(
            getattr(logging, self.config.logging.log_level, logging.INFO)
        )

        self.personality_manager = get_personality_manager(bot=self.bot)
        self.config.personality = self.personality_manager
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

        self.rate_limiter = RateLimiter(
            user_cooldown=self.config.rate_limit.user_cooldown,
            global_requests_per_minute=self.config.rate_limit.global_requests_per_minute
        )

        self._cleanup_task.start()

    def cog_unload(self) -> None:
        self._cleanup_task.cancel()
        logger.info("ChatCog unloaded")

    # ==================== Background Tasks ====================

    @tasks.loop(hours=1)
    async def _cleanup_task(self) -> None:
        try:
            removed = await self.storage.cleanup_old_memories(days=30)
            if removed > 0:
                logger.info(f"Cleaned up {removed} old conversation memories")
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")

    @_cleanup_task.before_loop
    async def _before_cleanup(self) -> None:
        await self.bot.wait_until_ready()

    # ==================== Core Processing ====================

    async def _process_chat_request(
        self,
        user_id: int,
        message: str,
        channel_id: int = None,
        guild_id: int = None,
    ) -> Tuple[str, Optional[str]]:
        """Process a chat request through the service layer."""
        try:
            await self.rate_limiter.acquire(user_id)
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
            raise ChatException(str(e))
        except RateLimitException:
            raise
        except Exception as e:
            logger.error(f"Chat service error: {e}")
            raise ChatException("Failed to process request")

    # ==================== Helper: Send Response ====================

    async def _send_response(
        self,
        message: discord.Message,
        content: str,
        response: str,
        provider: Optional[str]
    ) -> None:
        """Format and send the AI response to Discord."""
        # Format response text
        if self.config.features.show_provider and provider:
            bot_name = self.bot.user.name.lower()
            response_text = f"{response}\n\n> *— {bot_name}*"
        else:
            response_text = response

        # Check for song recommendations (>> format) in AI response
        song_recommendations = []

        # 1️⃣ Try structured JSON extraction first
        json_match = re.search(r'\{.*?\}', response_text, re.DOTALL)
        
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                if isinstance(parsed, dict) and "song" in parsed:
                    clean_song = parsed["song"].strip()
                    if clean_song and clean_song.lower() not in ["none", "", "unknown"]:
                        song_recommendations.append(clean_song)
            except json.JSONDecodeError:
                pass
            
        # 2️⃣ Fallback to >> extraction if no valid JSON found
        if not song_recommendations:
            raw_songs = self.music_integration.extract_songs_from_text(response_text)
            for song in raw_songs:
                clean_song = re.sub(r'[^\w\s\-]', '', song).strip()
                if clean_song:
                    song_recommendations.append(clean_song)
        

        # Only auto-play if user is in a voice channel
        user_in_voice = hasattr(message.author, 'voice') and message.author.voice is not None

        if song_recommendations:
            songs_list = ", ".join([s.strip() for s in song_recommendations])
            queries_list = ", ".join([f">> {s.strip()}" for s in song_recommendations])

            json_response = {
                "person": message.author.name,
                "action": "playing" if user_in_voice else "suggesting",
                "chat": response[:500] if len(response) > 500 else response,
                "song": songs_list,
                "query": queries_list
            }
            logger.info(f"📥 IN: {content}")
            logger.info(f"📤 OUT: {json.dumps(json_response, indent=2)}")

            if len(response_text) > 2000:
                for chunk in self._split_message(response_text, 2000):
                    await message.reply(chunk, mention_author=False)
            else:
                await message.reply(response_text, mention_author=False)

            # Auto-play only if user is in a voice channel
            if user_in_voice:
                for song_query in song_recommendations:
                    if song_query.strip():
                        _, play_response = await self.music_integration.search_and_play(
                            message, song_query.strip()
                        )
                        await message.reply(play_response, mention_author=False)
            else:
                # User not in voice channel - just suggest the songs
                suggest_embed = discord.Embed(
                    title="🎵 Song Suggestions",
                    description=f"**{songs_list}**",
                    color=discord.Color.blue()
                )
                suggest_embed.add_field(
                    name="Join a voice channel to play",
                    value="Use `/play` or `/join` to play these songs",
                    inline=False
                )
                await message.reply(embed=suggest_embed, mention_author=False)
        else:
            json_response = {
                "person": message.author.name,
                "action": "chat",
                "chat": response[:500] if len(response) > 500 else response,
                "song": "",
                "query": ""
            }
            logger.info(f"📥 IN: {content}")
            logger.info(f"📤 OUT: {json.dumps(json_response, indent=2)}")

            if len(response_text) > 2000:
                for chunk in self._split_message(response_text, 2000):
                    await message.reply(chunk, mention_author=False)
            else:
                await message.reply(response_text, mention_author=False)

    # ==================== Commands ====================

    @commands.hybrid_command(name="ask", description="Ask the AI a question")
    @app_commands.describe(question="Your question for the AI")
    async def ask(self, ctx: commands.Context, *, question: str) -> None:
        if isinstance(ctx.channel, discord.DMChannel) and not self.config.features.allow_dm:
            await ctx.send("❌ Chat commands are not allowed in DMs.")
            return

        await ctx.defer()

        try:
            response, provider = await self._process_chat_request(
                ctx.author.id, question, ctx.channel.id,
                ctx.guild.id if ctx.guild else None
            )
            if self.config.features.show_provider and provider:
                response_text = f"{response}\n\n> *— {self.bot.user.name.lower()}*"
            else:
                response_text = response

            if len(response_text) > 2000:
                for chunk in self._split_message(response_text, 2000):
                    await ctx.send(chunk)
            else:
                await ctx.send(response_text)

        except RateLimitException as e:
            await ctx.send(f"⏳ You're sending messages too fast! Please wait {e.retry_after:.1f} seconds.")
        except ChatException:
            await ctx.send("❌ Sorry, I couldn't process your request. Please try again later.")

    @commands.hybrid_command(name="chat", description="Start a chat session with the AI")
    @app_commands.describe(message="Your message to the AI")
    async def chat(self, ctx: commands.Context, *, message: str) -> None:
        await self.ask(ctx, question=message)

    @commands.hybrid_command(name="clearchat", description="Clear your conversation history")
    async def clear_history(self, ctx: commands.Context) -> None:
        if not self.config.features.enable_clear_command:
            await ctx.send("❌ This command is disabled.")
            return
        await self.chat_service.clear_channel_context(ctx.channel.id)
        await ctx.send("✅ Your conversation history for this channel has been cleared.")

    @commands.hybrid_command(name="setprovider", description="Set your preferred AI provider")
    @app_commands.describe(provider="The AI provider to use")
    async def set_provider(self, ctx: commands.Context, provider: str = "groq") -> None:
        if not self.config.features.enable_model_command:
            await ctx.send("❌ This command is disabled.")
            return
        if provider.lower() != "groq":
            await ctx.send("❌ Only 'groq' provider is currently available.")
            return
        await ctx.send("✅ Your preferred provider has been set to **groq**.")

    @commands.hybrid_command(name="chatping", description="Check if the chatbot is responsive")
    async def ping(self, ctx: commands.Context) -> None:
        start_time = time.time()
        latency = (time.time() - start_time) * 1000
        embed = discord.Embed(
            title="🟢 Chatbot Status",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Response Time", value=f"`{latency:.2f}ms`", inline=True)
        embed.add_field(name="Status", value="✅ **Online**", inline=True)
        embed.add_field(name="Provider", value="✅ `Groq`", inline=False)
        embed.set_footer(text="Use /chathelp for more info")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="chathelp", description="Show chatbot help and available commands")
    async def chat_help(self, ctx: commands.Context) -> None:
        embed = discord.Embed(
            title="🤖 AI Chatbot Help",
            description="Here's how to use the AI chatbot:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="💬 How to Chat",
            value=(
                "• `/ask <question>` - Ask the AI anything\n"
                "• `/chat <message>` - Same as /ask\n"
                "• `@mention` the bot - Chat naturally\n"
                "• Reply to bot messages - Continue conversation\n"
                "• Chat in dedicated channels - No tags needed"
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

    # ==================== SINGLE on_message (dedicated + mention + reply) ====================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Listen for messages in dedicated channels, bot mentions, or replies to bot."""
        if message.author.bot:
            return

        # Let command handler deal with commands
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        dedicated_channels = self.config.get_dedicated_channels()
        is_dedicated_channel = message.channel.id in dedicated_channels
        bot_mentioned = self.bot.user in message.mentions
        is_reply_to_bot = (
            message.reference and
            message.reference.resolved and
            message.reference.resolved.author.id == self.bot.user.id
        )

        if not (is_dedicated_channel or bot_mentioned or is_reply_to_bot):
            return

        if isinstance(message.channel, discord.DMChannel) and not self.config.features.allow_dm:
            return

        content = message.content
        if bot_mentioned:
            content = content.replace(f"<@{self.bot.user.id}>", "").strip()
            content = content.replace(f"<@!{self.bot.user.id}>", "").strip()

        if not content:
            return

        # --- Special personality commands ---
        special_response = self.personality_manager.handle_special_command(
            user_id=message.author.id,
            message=content,
            user_name=message.author.name,
            channel=message.channel
        )

        # Who's online check
        msg_lower = content.lower().strip()
        if msg_lower in ["who's online", "who is online", "online users", "active users"]:
            members = await self.personality_manager.get_online_users(message.channel)
            response_text = self.personality_manager.format_whos_online_response(members, message.channel.name)
            await message.reply(response_text, mention_author=False)
            return

        if special_response:
            song_recommendations = [
                re.sub(r'[^\w\s\-]', '', s).strip()
                for s in re.findall(r'>>\s*(.*?)(?=\n|$)', special_response)
            ]

            await message.reply(special_response, mention_author=False)
            if song_recommendations:
                for song_query in song_recommendations:
                    if song_query.strip():
                        ctx = await self.bot.get_context(message)
                        _, play_response = await self.music_integration.search_and_play(
                            ctx, song_query.strip()
                        )
                        await message.reply(play_response, mention_author=False)
            return

        # --- Direct play request (Hindi + English) ---
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

        if play_song_match:
            json_response = {
                "person": message.author.name,
                "action": "playing",
                "chat": f"Playing {play_song_match.title()}",
                "song": play_song_match.title(),
                "query": f">> {play_song_match}"
            }
            logger.info(f"📥 IN: {content}")
            logger.info(f"📤 OUT: {json.dumps(json_response, indent=2)}")

            await message.reply(f"🎵 Playing **{play_song_match.title()}**!", mention_author=False)
            ctx = await self.bot.get_context(message)
            _, play_response = await self.music_integration.search_and_play(
                ctx, play_song_match
            )
            await message.reply(play_response, mention_author=False)
            return

        # --- Update activity & music preferences ---
        self.personality_manager.update_activity(message.author.id)
        await self.music_integration.update_preferences_from_conversation(message.author.id, content)

        # --- Process mentions for context ---
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

        user_context = f"User: {message.author.display_name} (ID: {message.author.id})"
        if mentioned_users_info:
            user_context += mentioned_users_info
        enhanced_message = f"[{user_context}] {content}"

        # --- AI processing ---
        try:
            async with message.channel.typing():
                response, provider = await self._process_chat_request(
                    message.author.id,
                    enhanced_message,
                    message.channel.id,
                    message.guild.id if message.guild else None
                )

            await self._send_response(message, content, response, provider)

        except RateLimitException as e:
            await message.reply(
                f"⏳ You're sending messages too fast! Please wait {e.retry_after:.1f} seconds.",
                mention_author=False
            )
        except ChatException:
            await message.reply(
                "❌ Sorry, I couldn't process your request right now. Please try again later.",
                mention_author=False
            )

    # ==================== Status Listeners ====================

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        logger.info("=" * 50)
        logger.info("🤖 ChatCog is READY!")
        logger.info(f"✅ Loaded {len(self.config.providers)} providers")
        logger.info(f"✅ Provider priority: {self.config.provider_priority}")
        logger.info(f"✅ Max history: {self.config.max_history} messages")
        logger.info(f"✅ Rate limit: {self.config.rate_limit.user_cooldown}s cooldown")
        logger.info(f"✅ Persistence: {'Enabled' if self.config.persist_conversations else 'Disabled'}")
        logger.info("=" * 50)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: `{error.param.name}`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid argument provided.")
        elif isinstance(error, commands.NotOwner):
            await ctx.send("❌ This command is only available to the bot owner.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Command on cooldown. Try again in {error.retry_after:.1f}s")
        else:
            logger.error(f"Command error in {ctx.command}: {error}", exc_info=error)
            await ctx.send("❌ An error occurred while processing the command.")

    # ==================== Helper Methods ====================

    @staticmethod
    def _split_message(text: str, max_length: int) -> List[str]:
        """Split a long message into Discord-compliant chunks."""
        if len(text) <= max_length:
            return [text]

        chunks = []
        remaining = text

        while remaining:
            if len(remaining) <= max_length:
                chunks.append(remaining)
                break

            break_point = max_length
            para_break = remaining.rfind('\n\n', 0, max_length)
            if para_break > max_length // 2:
                break_point = para_break + 2
            else:
                sentence_break = remaining.rfind('.\n', 0, max_length)
                if sentence_break > max_length // 2:
                    break_point = sentence_break + 2
                else:
                    line_break = remaining.rfind('\n', 0, max_length)
                    if line_break > max_length // 2:
                        break_point = line_break + 1
                    else:
                        space_break = remaining.rfind(' ', 0, max_length)
                        if space_break > max_length // 2:
                            break_point = space_break + 1

            chunks.append(remaining[:break_point])
            remaining = remaining[break_point:]

        return chunks