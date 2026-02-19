import discord
from discord.ext import commands
import configparser
import json
from datetime import datetime, timezone, timedelta
import logging
from cogs.chat.personality import get_personality_manager
from cogs.chat.config import ChatConfig
from cogs.chat.providers import LLMProviderManager


logger = logging.getLogger('discord')


class Welcomer(commands.Cog):
    """Welcome new members to the server"""
    
    def __init__(self, bot):
        self.bot = bot
        self.config = configparser.ConfigParser()
        self.config.read('config/settings.ini', encoding='utf-8')
        self.personality_manager = get_personality_manager(bot=self.bot)
        
        # Initialize chat configuration and provider manager for AI welcome message generation
        self.chat_config = ChatConfig()
        self.provider_manager = LLMProviderManager(
            providers=self.chat_config.get_enabled_providers(),
            timeout=self.chat_config.rate_limit.request_timeout
        )
        
    def get_config(self, guild_id: int, key: str, default=None):
        """Get config value for a specific guild or default"""
        # Try guild-specific config first
        guild_section = f"welcomer_{guild_id}"
        if self.config.has_section(guild_section):
            if self.config.has_option(guild_section, key):
                return self.config.get(guild_section, key)
        
        # Fall back to default welcomer config
        if self.config.has_section('welcomer'):
            if self.config.has_option('welcomer', key):
                return self.config.get('welcomer', key)
        
        return default
    
    def get_config_bool(self, guild_id: int, key: str, default=False):
        """Get boolean config value"""
        value = self.get_config(guild_id, key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', 'yes', '1', 'on')
        return default
    
    def get_config_int(self, guild_id: int, key: str, default=0):
        """Get integer config value"""
        value = self.get_config(guild_id, key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_time_greeting(self):
        """Get greeting based on time of day (IST)"""
        # IST is UTC+5:30
        ist = timezone(timedelta(hours=5, minutes=30))
        hour = datetime.now(ist).hour
        
        if 5 <= hour < 12:
            return "Good morning"
        elif 12 <= hour < 17:
            return "Good afternoon"
        elif 17 <= hour < 22:
            return "Good evening"
        else:
            return "Good night"
    
    def check_milestone(self, guild_id: int, member_count: int):
        """Check if member count hits a milestone"""
        milestones_str = self.get_config(guild_id, 'milestones', '100,250,500,1000')
        
        try:
            milestones = [int(m.strip()) for m in milestones_str.split(',') if m.strip().isdigit()]
        except:
            milestones = [100, 250, 500, 1000]
        
        if member_count in milestones:
            return f"🎉 You're our {member_count}th member!"
        
        return None
    
    def get_custom_event_message(self, guild_id: int):
        """Check for custom events (holidays, etc.)"""
        custom_events_str = self.get_config(guild_id, 'custom_events', '{}')
        
        try:
            if isinstance(custom_events_str, dict):
                custom_events = custom_events_str
            else:
                # Handle both single and double quotes
                custom_events_str = custom_events_str.replace("'", '"')
                custom_events = json.loads(custom_events_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse custom_events: {e}")
            custom_events = {}
        
        if not custom_events:
            return None
        
        # Check current date (IST)
        ist = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(ist)
        
        # Format: "M-D" (e.g., "2-14" for Valentine's Day)
        month_day = f"{now.month}-{now.day}"
        
        # Check exact date match
        if month_day in custom_events:
            return custom_events[month_day]
        
        # Check with leading zeros (e.g., "02-14")
        month_day_padded = f"{now.month:02d}-{now.day:02d}"
        if month_day_padded in custom_events:
            return custom_events[month_day_padded]
        
        return None
    
    def build_welcome_message(self, member: discord.Member):
        """Build a customized welcome message based on previous chat and behavior"""
        guild = member.guild
        guild_id = guild.id
        
        # Get channels
        rules_channel_id = self.get_config_int(guild_id, 'rules_channel_id', 0)
        intro_channel_id = self.get_config_int(guild_id, 'introductions_channel_id', 0)
        
        rules_mention = f"<#{rules_channel_id}>" if rules_channel_id else "#rules"
        intro_mention = f"<#{intro_channel_id}>" if intro_channel_id else "#introductions"
        
        # Get greeting
        greeting = self.get_time_greeting()
        
        # Event
        event = self.get_custom_event_message(guild_id)
        event_text = f" {event}" if event else ""
        
        # Member count
        count = guild.member_count
        milestone = self.check_milestone(guild_id, count)
        
        # Simple embed
        embed = discord.Embed(color=0x5865F2)
        
        # Check if user has previous memory
        user_info = self.personality_manager.get_user_info(member.id)
        
        if user_info['message_count'] > 0:
            # Returning user - customize based on previous behavior
            message = (
                f"Welcome back, {member.mention}! 👋\n\n"
                f"Great to see you again in **{guild.name}**! "
            )
            
            # Mention previous interests or topics
            if user_info['interests']:
                interests_str = ", ".join(user_info['interests'])
                message += f"I remember you're interested in {interests_str}. "
            
            if user_info['last_conversation_topic']:
                message += f"Last time we talked about {user_info['last_conversation_topic']}. "
            
            if milestone:
                message += f"{milestone}{event_text}\n\n"
            else:
                message += f"You're still member **#{count}**! 🎉{event_text}\n\n"
            
            message += f"Check out {rules_mention} and join the conversation in {intro_mention}!"
        else:
            # New user - default welcome
            message = (
                f"{greeting}, {member.mention}! 👋\n\n"
                f"Welcome to **{guild.name}**! "
            )
            
            if milestone:
                message += f"{milestone}{event_text}\n\n"
            else:
                message += f"You're member **#{count}**! 🎉{event_text}\n\n"
            
            message += f"Check out {rules_mention} and say hi in {intro_mention}!"
        
        embed.description = message
        
        # Avatar thumbnail
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)
        
        return embed

    def build_dm_welcome_message(self, member: discord.Member):
        """Build the DM welcome message"""
        guild = member.guild
        guild_id = guild.id
        
        bot_name = self.get_config(guild_id, 'bot_name', 'AI Assistant')
        server_topics = self.get_config(guild_id, 'server_topics', 'general chat and discussions')
        
        time_greeting = self.get_time_greeting()
        
        # Check if user has previous memory
        user_info = self.personality_manager.get_user_info(member.id)
        
        if user_info['message_count'] > 0:
            # Returning user - customize DM welcome
            embed = discord.Embed(
                title=f"🎉 Welcome Back to {guild.name}!",
                description=f"{time_greeting}! I'm **{bot_name}**, the AI assistant for this server.",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Welcome Back!",
                value="Great to see you again! I remember our previous conversations. Feel free to pick up where we left off!",
                inline=False
            )
            
            # Mention previous interests or topics
            if user_info['interests']:
                interests_str = ", ".join(user_info['interests'])
                embed.add_field(
                    name="Your Interests",
                    value=f"I remember you're interested in {interests_str}. Let me know if you want to discuss these topics again!",
                    inline=False
                )
            
            if user_info['last_conversation_topic']:
                embed.add_field(
                    name="Last Conversation",
                    value=f"Last time we talked about {user_info['last_conversation_topic']}. Want to continue that discussion?",
                    inline=False
                )
        else:
            # New user - default DM welcome
            embed = discord.Embed(
                title=f"🎉 Welcome to {guild.name}!",
                description=f"{time_greeting}! I'm **{bot_name}**, the AI assistant for this server.",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="What I Can Help With",
                value=f"I can answer questions, help you navigate the server, and chat about {server_topics}. Just @ mention me anytime in the server!",
                inline=False
            )
            
            embed.add_field(
                name="Get Started",
                value="Head back to the server and check out the welcome message for important channels and rules!",
                inline=False
            )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.set_footer(text=f"You're member #{guild.member_count}!")
        embed.timestamp = datetime.now(timezone.utc)
        
        return embed
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle new member joins"""
        # Skip if member is a bot (optional - can be removed if you want to welcome bots too)
        if member.bot:
            return
        
        guild_id = member.guild.id
        
        # Check if welcomer is enabled
        if not self.get_config_bool(guild_id, 'enabled', False):
            return
        
        # Auto-role assignment
        auto_role_id = self.get_config_int(guild_id, 'auto_role_id', 0)
        if auto_role_id:
            role = member.guild.get_role(auto_role_id)
            if role:
                try:
                    await member.add_roles(role)
                    logger.info(f"Assigned role {role.name} to {member}")
                except discord.Forbidden:
                    logger.error(f"Missing permissions to assign role to {member}")
                except Exception as e:
                    logger.error(f"Error assigning role: {e}")
        
        # Get welcome channel
        welcome_channel_id = self.get_config_int(guild_id, 'welcome_channel_id', 0)
        
        if not welcome_channel_id:
            logger.warning(f"No welcome channel configured for guild {guild_id}")
            return
        
        welcome_channel = self.bot.get_channel(welcome_channel_id)
        
        if not welcome_channel:
            logger.warning(f"Welcome channel {welcome_channel_id} not found for guild {guild_id}")
            return
        
        try:
            # Send welcome message to the welcome channel
            embed = self.build_welcome_message(member)
            await welcome_channel.send(embed=embed)
            logger.info(f"Sent welcome message for {member} in {welcome_channel}")
            
            # Send DM welcome if enabled
            if self.get_config_bool(guild_id, 'dm_welcome', False):
                try:
                    dm_embed = self.build_dm_welcome_message(member)
                    await member.send(embed=dm_embed)
                    logger.info(f"Sent DM welcome to {member}")
                except discord.Forbidden:
                    logger.warning(f"Could not send DM to {member} - likely has DMs disabled")
                except Exception as e:
                    logger.error(f"Error sending DM to {member}: {e}")
                    
        except Exception as e:
            logger.error(f"Error sending welcome message for {member}: {e}")
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Handle voice state updates to welcome users joining voice channels"""
        # Skip if member is a bot
        if member.bot:
            return
        
        # Check if user joined a voice channel
        if before.channel is None and after.channel is not None:
            await self.send_voice_welcome(member, after.channel)
    
    async def send_voice_welcome(self, member: discord.Member, voice_channel: discord.VoiceChannel):
        """Send a welcome message when user joins a voice channel using AI to generate personalized message"""
        guild_id = member.guild.id
        
        # Check if welcomer is enabled
        if not self.get_config_bool(guild_id, 'enabled', False):
            return
        
        # Check if user has previous memory
        user_info = self.personality_manager.get_user_info(member.id)
        
        # Collect previous messages from this voice channel's text chat
        previous_messages = await self.collect_previous_messages(member, voice_channel)
        
        # Generate personalized welcome message using Groq
        ai_welcome_message = await self.generate_ai_welcome_message(member, voice_channel, user_info, previous_messages)
        
        # Create embed for voice welcome
        embed = discord.Embed(
            title=f"🎤 Voice Channel Welcome!",
            description=ai_welcome_message,
            color=discord.Color.blue()
        )
        
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)
        
        try:
            await voice_channel.send(embed=embed)
            logger.info(f"Sent voice welcome message for {member} in {voice_channel}")
        except Exception as e:
            logger.error(f"Error sending voice welcome message for {member}: {e}")
    
    async def collect_previous_messages(self, member: discord.Member, voice_channel: discord.VoiceChannel, limit: int = 10):
        """Collect previous messages from this voice channel's text chat"""
        previous_messages = []
        
        # Try to find the corresponding text channel for this voice channel
        guild = member.guild
        
        # Check for text channels with similar name to voice channel
        voice_channel_name = voice_channel.name.lower().replace(' ', '').replace('-', '')
        candidate_channels = []
        
        for channel in guild.text_channels:
            channel_name = channel.name.lower().replace(' ', '').replace('-', '')
            if voice_channel_name in channel_name or channel_name in voice_channel_name:
                candidate_channels.append(channel)
        
        if candidate_channels:
            # Use the first matching text channel
            text_channel = candidate_channels[0]
            
            try:
                async for message in text_channel.history(limit=limit):
                    # Skip bot messages and messages from current user
                    if message.author.bot or message.author.id == member.id:
                        continue
                    
                    # Get user personality from each message
                    previous_messages.append({
                        "author": message.author.display_name,
                        "content": message.content,
                        "timestamp": message.created_at.isoformat()
                    })
            
            except Exception as e:
                logger.error(f"Error collecting previous messages from {text_channel}: {e}")
        
        return previous_messages
    
    async def generate_ai_welcome_message(self, member: discord.Member, voice_channel: discord.VoiceChannel, user_info, previous_messages):
        """Generate personalized welcome message using Groq AI"""
        # Build prompt for AI
        prompt = (
            f"Generate a personalized welcome message for a Discord user joining a voice channel.\n\n"
            f"**User Information:**\n"
            f"- Name: {member.display_name}\n"
            f"- Previous Messages Count: {user_info['message_count']}\n"
            f"- Interests: {', '.join(user_info['interests']) if user_info['interests'] else 'None'}\n"
            f"- Last Conversation Topic: {user_info['last_topic'] if user_info['last_topic'] else 'None'}\n\n"
            f"**Voice Channel:**\n"
            f"- Name: {voice_channel.name}\n\n"
            f"**Previous Messages in this Channel (last 10 messages):**\n"
        )
        
        if previous_messages:
            for msg in previous_messages:
                prompt += f"- {msg['author']}: {msg['content']}\n"
        else:
            prompt += "No previous messages available in this channel.\n\n"
        
        prompt += (
            "\n**Instructions:**\n"
            "1. Keep the message short, friendly, and engaging\n"
            "2. If it's a returning user, mention their previous interests or topics\n"
            "3. If it's a new user, be welcoming and inviting\n"
            "4. Use Discord Markdown formatting for emphasis\n"
            "5. Include appropriate emojis\n"
            "6. Match the personality from the system prompt\n"
            "7. Address the user by name\n"
        )
        
        try:
            # Build messages for LLM API
            messages = [
                {"role": "system", "content": self.chat_config.system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            # Generate response using Groq
            response, provider_name = await self.provider_manager.generate_with_fallback(
                messages=messages,
                max_tokens=500
            )
            
            logger.info(f"Generated AI welcome message using {provider_name}")
            return response.content
            
        except Exception as e:
            logger.error(f"Error generating AI welcome message: {e}")
            
            # Fallback to default welcome message
            if user_info['message_count'] > 0:
                return (
                    f"Hey {member.mention}! 👋\n\n"
                    f"Welcome to {voice_channel.mention}! Great to see you again!"
                    "\n\nHope you enjoy your time here!"
                )
            else:
                return (
                    f"Hey {member.mention}! 👋\n\n"
                    f"Welcome to {voice_channel.mention}! "
                    f"This is your first time here, make yourself comfortable!"
                    "\n\nFeel free to say hi and join the conversation!"
                )
    
    # Configuration commands for the welcomer
    @commands.group(name='welcomer', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def welcomer_group(self, ctx):
        """Welcomer configuration commands"""
        await ctx.send_help(ctx.command)
    
    @welcomer_group.command(name='enable')
    @commands.has_permissions(manage_guild=True)
    async def welcomer_enable(self, ctx):
        """Enable the welcomer"""
        embed = discord.Embed(
            title="✅ Welcomer Enabled",
            description="The welcomer is now enabled! Make sure to configure the settings in `config/settings.ini`",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Required Settings",
            value="• `welcome_channel_id` - Channel for welcome messages\n• `bot_name` - Name of the bot\n• `server_topics` - What the server is about",
            inline=False
        )
        await ctx.send(embed=embed)
    
    @welcomer_group.command(name='disable')
    @commands.has_permissions(manage_guild=True)
    async def welcomer_disable(self, ctx):
        """Disable the welcomer"""
        embed = discord.Embed(
            title="⚠️ Disable Welcomer",
            description="To disable the welcomer, set `enabled = false` in `config/settings.ini`",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
    
    @welcomer_group.command(name='test')
    @commands.has_permissions(manage_guild=True)
    async def welcomer_test(self, ctx, member: discord.Member = None):
        """Test the welcome message"""
        if member is None:
            member = ctx.author
        
        embed = self.build_welcome_message(member)
        await ctx.send("**Here's how the welcome message will look:**", embed=embed)
        
        # Show custom event if any
        custom_event = self.get_custom_event_message(ctx.guild.id)
        if custom_event:
            event_embed = discord.Embed(
                title="📅 Today's Event",
                description=custom_event,
                color=discord.Color.blue()
            )
            await ctx.send(embed=event_embed)
        else:
            await ctx.send("ℹ️ No custom event today.")
    
    @welcomer_group.command(name='config')
    @commands.has_permissions(manage_guild=True)
    async def welcomer_config(self, ctx):
        """Show current welcomer configuration"""
        guild_id = ctx.guild.id
        
        # Get all config values
        enabled = self.get_config_bool(guild_id, 'enabled', False)
        welcome_channel_id = self.get_config_int(guild_id, 'welcome_channel_id', 0)
        dm_welcome = self.get_config_bool(guild_id, 'dm_welcome', False)
        bot_name = self.get_config(guild_id, 'bot_name', 'AI Assistant')
        server_topics = self.get_config(guild_id, 'server_topics', 'general chat and discussions')
        auto_role_id = self.get_config_int(guild_id, 'auto_role_id', 0)
        milestones = self.get_config(guild_id, 'milestones', '100,250,500,1000')
        
        # Build embed
        embed = discord.Embed(
            title="⚙️ Welcomer Configuration",
            description=f"Configuration for **{ctx.guild.name}**",
            color=discord.Color.blue()
        )
        
        # Status
        status = "✅ Enabled" if enabled else "❌ Disabled"
        embed.add_field(name="Status", value=status, inline=True)
        
        # Welcome channel
        welcome_channel = ctx.guild.get_channel(welcome_channel_id) if welcome_channel_id else None
        welcome_channel_text = welcome_channel.mention if welcome_channel else "Not set"
        embed.add_field(name="Welcome Channel", value=welcome_channel_text, inline=True)
        
        # DM Welcome
        dm_status = "✅ Enabled" if dm_welcome else "❌ Disabled"
        embed.add_field(name="DM Welcome", value=dm_status, inline=True)
        
        # Bot info
        embed.add_field(name="Bot Name", value=bot_name, inline=True)
        embed.add_field(name="Server Topics", value=server_topics, inline=False)
        
        # Auto-role
        auto_role = ctx.guild.get_role(auto_role_id) if auto_role_id else None
        auto_role_text = auto_role.mention if auto_role else "Not set"
        embed.add_field(name="Auto Role", value=auto_role_text, inline=True)
        
        # Milestones
        embed.add_field(name="Milestones", value=milestones, inline=True)
        
        # Custom events count
        custom_events_str = self.get_config(guild_id, 'custom_events', '{}')
        try:
            custom_events = json.loads(custom_events_str.replace("'", '"'))
            event_count = len(custom_events)
        except:
            event_count = 0
        embed.add_field(name="Custom Events", value=f"{event_count} configured", inline=True)
        
        embed.set_footer(text="Edit config/settings.ini to change these settings")
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Welcomer(bot))
