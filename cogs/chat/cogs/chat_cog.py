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
import asyncio
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

        # ===== State Management for Music Suggestions =====
        # Track: {user_id: {"song": "Song Name", "mood": "happy", "timestamp": time}}
        self.pending_song_suggestions = {}

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

    # ==================== Helper: Detect Music Request ====================

    def _detect_music_request(self, message: str) -> bool:
        """
        Detect if user is explicitly asking for music - ENGLISH & HINDI.
        Only triggers on clear music requests, not just mood mentions.
        """
        message_lower = message.lower()
        
        # English music request patterns
        english_triggers = [
            r'play\s+(some\s+)?music',
            r'play\s+(some\s+)?songs?',
            r'suggest\s+(some\s+)?songs?',
            r'recommend\s+(some\s+)?songs?',
            r'put\s+on\s+music',
            r'queue\s+music',
            r'queue\s+songs?',
            r'find\s+songs?',
            r'search\s+songs?',
        ]
        
        # Hindi music request patterns (Hinglish - Hindi written in English)
        hindi_triggers = [
            r'ga[an]+e?\s+suggest',       # gane/gaana/gana suggest
            r'ga[an]+a?\s+baja',           # gaana/gana baja (play song)
            r'suna?[ao]?\s+de',            # suna de / sunao / sumo de
            r'sun',                        # sunao, sun, etc
            r'songs?\s+suggest',          # songs suggest
            r'ga[an]+[ae]?\s+cha',        # gane/gaana want
            r'music\s+cha',               # want music
            r'koi\s+ga[an]+[ae]?',        # any song (koi gane/gaana)
            r'kuch\s+ga[an]+[ae]?',       # some songs
            r'recommendation',            # recommendation
        ]
        
        import re
        
        # Check English patterns
        for pattern in english_triggers:
            if re.search(pattern, message_lower):
                logger.info(f"🎵 Music request (English) detected: {pattern}")
                return True
        
        # Check Hindi patterns
        for pattern in hindi_triggers:
            if re.search(pattern, message_lower):
                logger.info(f"🎵 Music request (Hindi) detected: {pattern}")
                return True
        
        return False

    # ==================== Helper: Detect Play Confirmation ====================

    def _detect_play_confirmation(self, message: str) -> bool:
        """
        Detect if user is confirming to play music.
        Triggers on: yes, ok, suna le, han baja, etc.
        """
        message_lower = message.lower()
        
        # Confirmation patterns - English + Hindi
        confirm_patterns = [
            # English
            r'\byes\b', r'\bokay?\b', r'\bok\b', r'\bk\b', r'\bgo\b', r'\bdo\s+it\b',
            r'\bstart\b', r'\bplay\b', r'\blet\'s\s+go\b',
            # Hindi/Hinglish
            r'\bha[an]+\b',              # han / haan
            r'\bbaaja?\b',               # baja / baja
            r'\bsuna?[ao]?\s+de\b',      # suna de / sunao
            r'\bch[au]l\b',              # chaal / chul
            r'\bthe[io]k\b',             # theek / theik
            r'\bshadi\b',                # shudd (sure)
            r'\bthee[ko]?',              # theek
            r'\bsho\b',                  # sho (yes/sure)
        ]
        
        import re
        for pattern in confirm_patterns:
            if re.search(pattern, message_lower):
                logger.info(f"🎵 Play confirmation detected: {pattern}")
                return True
        return False

    # ==================== Helper: Detect Song Rejection ====================

    def _detect_song_rejection(self, message: str) -> bool:
        """
        Detect if user is rejecting the suggested song.
        Triggers on: no, ye wala ne, koi aur, etc.
        """
        message_lower = message.lower()
        
        # Rejection patterns - English + Hindi
        reject_patterns = [
            # English
            r'\bno\b', r'\bnope\b', r'\bdon\'t\b', r'\bnot\s+this\b', r'\another\b',
            # Hindi/Hinglish
            r'\bna[ah]+\b',               # nah / naa
            r'\bna\b',                   # na (no)
            r'\bye\s+wala\s+ne',         # ye wala ne (not this one)
            r'\bkoi\s+aur\b',            # koi aur (any other)
            r'\bkuch\s+aur\b',           # kuch aur (something else)
            r'\bfir\s+se\b',             # fir se (again/different)
            r'\bnahin\b',                # nahin (no)
        ]
        
        import re
        for pattern in reject_patterns:
            if re.search(pattern, message_lower):
                logger.info(f"🎵 Song rejection detected: {pattern}")
                return True
        return False

    async def _send_response(
        self,
        message: discord.Message,
        content: str,
        response: str,
        provider: Optional[str]
    ) -> None:
        """Format and send the AI response to Discord."""
        # Step 1: Extract and remove JSON objects from response
        parsed_response = response
        extracted_songs = []
        
        # Remove ALL JSON objects from the response and extract songs
        json_pattern = r'\{[^{}]*(?:"[^"]*"[^{}]*)*\}'
        json_matches = re.finditer(json_pattern, parsed_response)
        
        for match in json_matches:
            try:
                json_text = match.group()
                json_data = json.loads(json_text)
                
                if isinstance(json_data, dict):
                    # Extract songs from JSON
                    if 'song' in json_data:
                        song = json_data['song']
                        if isinstance(song, str):
                            extracted_songs.append(song.strip())
                    
                    if 'songs' in json_data and isinstance(json_data['songs'], list):
                        extracted_songs.extend([s for s in json_data['songs'] if isinstance(s, str)])
                    
                    if 'query' in json_data:
                        query = json_data['query']
                        if isinstance(query, str) and query.startswith('>>'):
                            song_name = query[2:].strip()
                            if song_name and song_name not in extracted_songs:
                                extracted_songs.append(song_name)
                    
                    if 'play_all' in json_data:
                        play_query = json_data['play_all']
                        if isinstance(play_query, str) and play_query.startswith('>>'):
                            song_name = play_query[2:].strip()
                            if song_name and song_name not in extracted_songs:
                                extracted_songs.append(song_name)
            except json.JSONDecodeError:
                # Skip invalid JSON
                pass
        
        # Remove all JSON objects from the display text
        parsed_response = re.sub(json_pattern, '', response)
        # Clean up extra spaces and newlines
        parsed_response = re.sub(r'\s+', ' ', parsed_response).strip()
        
        # If response is empty after JSON removal, use original
        if not parsed_response or len(parsed_response) < 5:
            parsed_response = response
        
        # Format response text
        if self.config.features.show_provider and provider:
            bot_name = self.bot.user.name.lower()
            response_text = f"{parsed_response}\n\n> *— {bot_name}*"
        else:
            response_text = parsed_response

        # Step 2: Extract quoted song names from AI response for later confirmation
        quoted_songs = re.findall(r'["\']([^"\']{3,})["\']', response)
        if quoted_songs:
            self.pending_song_suggestions[message.author.id] = {
                "songs": quoted_songs,
                "timestamp": time.time()
            }
            logger.info(f"🎵 Stored suggested songs from AI response: {quoted_songs}")

        # Step 3: Check for additional song recommendations in regular text
        if not extracted_songs:
            raw_songs = self.music_integration.extract_songs_from_text(response_text)
            for song in raw_songs:
                clean_song = re.sub(r'[^\w\s\-]', '', song).strip()
                if clean_song:
                    extracted_songs.append(clean_song)
        
        # Step 4: Log and send response (NO auto-play - music only on explicit user request)
        json_log = {
            "person": message.author.name,
            "action": "chat",
            "chat": response_text[:500] if len(response_text) > 500 else response_text,
            "song": "",
            "query": ""
        }
        logger.info(f"📥 IN: {content}")
        logger.info(f"📤 OUT: {json.dumps(json_log, indent=2)}")

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

    @commands.hybrid_command(name="setpersonality", description="Set the AI personality for this channel")
    @app_commands.describe(personality="The personality to use (e.g., default, aggressive, professional)")
    async def set_personality(self, ctx: commands.Context, personality: str = None) -> None:
        """Set the AI personality for the current channel.
        
        Available personalities are loaded from the config file.
        This command sets a channel-specific override.
        """
        # List available personalities if none specified
        if personality is None:
            available = self.config.get_all_personality_names()
            current = self.config.channel_personality_map.get(
                ctx.channel.id, 
                self.config.default_personality
            )
            
            personality_list = "\n".join([f"• **{name}**" for name in sorted(available)])
            embed = discord.Embed(
                title="🎭 Available Personalities",
                description=f"Use: `/setpersonality <name>`\n\nCurrent: **{current}**",
                color=discord.Color.blurple()
            )
            embed.add_field(name="Personalities", value=personality_list or "No personalities configured", inline=False)
            embed.set_footer(text="Personalities are defined in config/chat_config.ini")
            await ctx.send(embed=embed)
            return
        
        # Validate and set personality
        personality_lower = personality.lower().strip()
        
        if personality_lower not in self.config.personalities:
            available = self.config.get_all_personality_names()
            await ctx.send(
                f"❌ Personality `{personality}` not found.\n\n"
                f"Available personalities: {', '.join(sorted(available))}"
            )
            return
        
        # Set the channel personality override
        success = self.config.set_channel_personality(ctx.channel.id, personality_lower)
        
        if success:
            personality_config = self.config.get_personality(personality_lower)
            embed = discord.Embed(
                title="🎭 Personality Updated",
                description=f"Channel personality set to: **{personality_config.name}**",
                color=discord.Color.green()
            )
            if hasattr(personality_config, 'tone') and personality_config.tone:
                embed.add_field(name="Tone", value=personality_config.tone, inline=False)
            if hasattr(personality_config, 'allowed_features') and personality_config.allowed_features:
                features = ", ".join(personality_config.allowed_features)
                embed.add_field(name="Features", value=features, inline=False)
            embed.set_footer(text="This override applies only to this channel")
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Failed to set personality. Please check available personalities with `/setpersonality`")

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
                f"✅ Selectable personalities\n"
                f"✅ Rate limiting ({self.config.rate_limit.user_cooldown}s cooldown)\n"
                f"✅ DM support: {'Enabled' if self.config.features.allow_dm else 'Disabled'}"
            ),
            inline=False
        )
        embed.add_field(
            name="🎭 Personality Commands",
            value=(
                "• `/setpersonality` - Show available personalities\n"
                "• `/setpersonality <name>` - Set channel personality"
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

            # --- Handle music requests (only on confirmation, not just suggestion) ---
            if message.author.voice:
                try:
                    user_id = message.author.id
                    
                    # Check if user is confirming to play music (han, baja, yes, ok, etc)
                    if self._detect_play_confirmation(content):
                        logger.info(f"🎵 User confirmed to play music")
                        
                        # Get stored song suggestions from AI response
                        if user_id in self.pending_song_suggestions:
                            stored = self.pending_song_suggestions[user_id]
                            songs_list = stored.get("songs", [])
                            
                            if songs_list:
                                # Pick first song from suggestions
                                song_to_play = songs_list[0]
                                logger.info(f"🎵 Playing first suggested song: {song_to_play}")
                                
                                if message.author.voice:
                                    _, play_response = await self.music_integration.search_and_play(
                                        message, song_to_play
                                    )
                                    await message.reply(play_response, mention_author=False)
                                    # Clear suggestion after playing
                                    del self.pending_song_suggestions[user_id]
                            else:
                                logger.info(f"🎵 Empty songs list in storage")
                        else:
                            logger.info(f"🎵 No songs stored, asking user for song name")
                            await message.reply("🎵 Kaunsa gaana bajun? Naam bata!", mention_author=False)
                    
                    # Detect if user rejected a song suggestion (clear the stored one)
                    elif self._detect_song_rejection(content):
                        logger.info(f"🎵 User rejected songs")
                        if user_id in self.pending_song_suggestions:
                            del self.pending_song_suggestions[user_id]
                        # AI will naturally suggest another song in its response
                
                except Exception as e:
                    logger.debug(f"Music request handling error: {e}")

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

    async def _auto_trigger_mood_playlist(self, message: discord.Message, mood: str) -> None:
        """
        Background task to trigger mood-based auto-playlist
        Runs non-blocking so AI response sends immediately
        """
        try:
            logger.info(f"🎵 Auto-triggering {mood} mood playlist for {message.author.name}")
            success, response = await self.music_integration.play_mood_playlist(message, mood)
            
            if success:
                # Send playlist confirmation (without mentioning)
                await message.reply(response, mention_author=False, silent=True)
                logger.info(f"✅ Auto-playlist triggered successfully for {mood}")
            else:
                logger.warning(f"⚠️ Auto-playlist failed: {response}")
        except Exception as e:
            logger.error(f"Error in auto-playlist: {e}")

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
