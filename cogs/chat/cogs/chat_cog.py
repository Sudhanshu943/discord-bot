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
from ..integrations import MusicIntegration

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
        self.music_integration = MusicIntegration(bot=self.bot)

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
        song_requested = self._is_song_request(content)

        if self.config.features.show_provider and provider:
            bot_name = self.bot.user.name.lower()
            response_text = f"{response}\n\n> *— {bot_name}*"
        else:
            response_text = response

        # Hide any inline song/query JSON from Discord-visible text.
        response_text = self._strip_song_json(response_text).strip()
        if not response_text:
            response_text = "Done."

        song_recommendations = []
        json_match = re.search(r'\{.*?\}', response, re.DOTALL)

        if song_requested and json_match:
            try:
                parsed = json.loads(json_match.group())
                if isinstance(parsed, dict) and "song" in parsed:
                    clean_song = parsed["song"].strip()
                    if clean_song and clean_song.lower() not in ["none", "", "unknown"]:
                        song_recommendations.append(clean_song)
            except json.JSONDecodeError:
                pass

        if song_requested and not song_recommendations:
            raw_songs = self.music_integration.extract_songs_from_text(response_text)
            for song in raw_songs:
                clean_song = re.sub(r'[^\w\s\-]', '', song).strip()
                if clean_song:
                    song_recommendations.append(clean_song)

        if song_requested and not song_recommendations:
            extracted_song, extracted_query = self._extract_song_query_from_content(content)
            if extracted_song and extracted_query:
                song_recommendations.append(extracted_song)

        user_in_voice = hasattr(message.author, 'voice') and message.author.voice is not None

        if song_requested and song_recommendations:
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

            await message.reply(
                json.dumps({"song": songs_list, "query": queries_list}, ensure_ascii=False),
                mention_author=False
            )

            if user_in_voice:
                for song_query in song_recommendations:
                    if song_query.strip():
                        _, play_response = await self.music_integration.search_and_play(
                            message, song_query.strip()
                        )
                        await message.reply(play_response, mention_author=False)
            return

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

    @staticmethod
    def _is_song_request(content: str) -> bool:
        """True only when user explicitly asks to play/listen music."""
        msg = (content or "").lower()
        patterns = [
            r"\bplay\b",
            r"\bplay\s+song\b",
            r"\bsong\b",
            r"\bmusic\b",
            r"\bbaja\b",
            r"\bsunao\b",
            r"\bsuna\s*de\b",
            r"\bgana\b",
            r"\bgaana\b",
        ]
        return any(re.search(pattern, msg) for pattern in patterns)

    @staticmethod
    def _extract_song_query_from_content(content: str) -> Tuple[str, str]:
        """Extract song title/query from explicit user request text."""
        text = (content or "").strip()
        lowered = text.lower()
        if not text:
            return "", ""

        patterns = [
            r'^\s*play\s+song\s+(.+?)\s*$',
            r'^\s*play\s+(.+?)\s*$',
            r'^\s*baja\s+(.+?)\s*$',
            r'^\s*sunao\s+(.+?)\s*$',
            r'^\s*suna\s+de\s+(.+?)\s*$',
        ]

        for pattern in patterns:
            match = re.match(pattern, lowered, flags=re.IGNORECASE)
            if not match:
                continue
            query = match.group(1).strip()
            if not query:
                continue
            if "trending" in query and "song" in query:
                return "Trending Song", "trending song"
            return query.title(), query

        if "trending song" in lowered:
            return "Trending Song", "trending song"

        return "", ""

    @staticmethod
    def _strip_song_json(text: str) -> str:
        """Remove inline {'song','query'} JSON blocks from text."""
        if not text:
            return text
        return re.sub(
            r'\s*\{\s*"song"\s*:\s*".*?"\s*,\s*"query"\s*:\s*".*?"\s*\}\s*',
            " ",
            text,
            flags=re.IGNORECASE | re.DOTALL
        )
    def _format_user_message_for_memory(self, message: discord.Message, content: str) -> str:
        """Create a speaker-labeled memory line for stronger multi-user context."""
        normalized = " ".join(content.split())
        return f"[User: {message.author.display_name} (ID: {message.author.id})] {normalized}"

    async def _is_reply_to_bot(self, message: discord.Message) -> bool:
        """Robustly determine if message replies to the bot, even when reference is unresolved."""
        if not message.reference:
            return False

        resolved = message.reference.resolved
        if resolved is None and message.reference.message_id and hasattr(message.channel, "fetch_message"):
            try:
                resolved = await message.channel.fetch_message(message.reference.message_id)
            except Exception:
                return False

        return bool(
            resolved and
            getattr(resolved, "author", None) and
            resolved.author.id == self.bot.user.id
        )

    async def _store_passive_context(self, message: discord.Message, content: str) -> None:
        """Store non-trigger chat messages so the next bot query sees recent group discussion."""
        if not content or not content.strip():
            return

        formatted = self._format_user_message_for_memory(message, content)
        await self.memory_manager.add_to_channel_memory(
            message.channel.id,
            "user",
            formatted,
            message.author.id
        )

        if message.guild:
            await self.memory_manager.add_to_guild_memory(
                message.guild.id,
                "user",
                formatted,
                message.author.id
            )
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
        is_reply_to_bot = await self._is_reply_to_bot(message)

        if not (is_dedicated_channel or bot_mentioned or is_reply_to_bot):
            # Capture background conversation for future context understanding.
            try:
                await self._store_passive_context(message, message.content)
            except Exception as e:
                logger.error(f"Failed to store passive context: {e}")
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
        extracted_song, extracted_query = self._extract_song_query_from_content(content)
        if extracted_song and extracted_query:
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


