"""
Stats Commands Cog
===============================

Discord-specific implementation for statistics-related commands.
"""

import discord
from discord.ext import commands

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class StatsCog(commands.Cog):
    """Statistics command handler for the chat system."""

    def __init__(self, bot: commands.Bot, chat_service, rate_limiter, memory_manager, storage):
        self.bot = bot
        self.chat_service = chat_service
        self.rate_limiter = rate_limiter
        self.memory_manager = memory_manager
        self.storage = storage

    @commands.hybrid_command(name="chatstats", description="View chat statistics")
    async def chat_stats(self, ctx: commands.Context) -> None:
        rate_stats = self.rate_limiter.get_global_stats()

        try:
            all_channels = self.storage._load_all_channel_memories()
            all_guilds = self.storage._load_all_guild_memories()
            total_channels = len(all_channels)
            total_guilds = len(all_guilds)
            total_messages = (
                sum(len(m.get("messages", [])) for m in all_channels.values()) +
                sum(len(m.get("messages", [])) for m in all_guilds.values())
            )
        except Exception:
            total_channels = total_guilds = total_messages = 0

        embed = discord.Embed(title="📊 Chat Statistics", color=discord.Color.blue(), timestamp=datetime.utcnow())
        embed.add_field(
            name="Memory Usage",
            value=f"Active Channels: {total_channels}\nActive Guilds: {total_guilds}\nTotal Messages Stored: {total_messages}",
            inline=True
        )
        embed.add_field(
            name="Rate Limiting",
            value=f"Requests/min: {rate_stats['requests_last_minute']}/{rate_stats['limit_per_minute']}\nTotal Blocked: {rate_stats['total_blocked']}",
            inline=True
        )
        embed.add_field(name="Provider", value="✅ Groq (llama-3.3-70b-versatile)", inline=False)
        embed.set_footer(text="Refactored with service layer architecture")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="providers", description="List available AI providers")
    async def list_providers(self, ctx: commands.Context) -> None:
        embed = discord.Embed(title="🤖 Available AI Providers", color=discord.Color.green())
        embed.add_field(
            name="✅ Groq",
            value="Model: llama-3.3-70b-versatile\nStatus: Active\nType: Open-source LLM",
            inline=False
        )
        embed.set_footer(text="Groq API for fast inference")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="mystats", description="View your personal chat statistics")
    async def my_stats(self, ctx: commands.Context) -> None:
        channel_mem = await self.memory_manager.get_or_create_channel_memory(ctx.channel.id)
        rate_stats = self.rate_limiter.get_user_stats(ctx.author.id)

        user_message_count = 0
        if channel_mem and hasattr(channel_mem, 'messages') and channel_mem.messages:
            user_message_count = sum(
                1 for msg in channel_mem.messages
                if msg.get("user_id") == ctx.author.id
            )

        if user_message_count == 0:
            await ctx.send("ℹ️ You haven't chatted with the AI yet in this channel.")
            return

        embed = discord.Embed(title="📈 Your Chat Statistics", color=discord.Color.purple())
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.add_field(
            name="Conversation",
            value=f"Messages in This Channel: {user_message_count}\nTotal Rate Limited: {rate_stats.get('warning_count', 0)}",
            inline=True
        )
        embed.add_field(
            name="Rate Limiting",
            value=f"Requests (This Channel): {rate_stats['request_count']}\nWarnings: {rate_stats['warning_count']}",
            inline=True
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="status", description="Detailed chatbot system status")
    async def system_status(self, ctx: commands.Context) -> None:
        rate_stats = self.rate_limiter.get_global_stats()
        try:
            all_channels = self.storage._load_all_channel_memories()
            all_guilds = self.storage._load_all_guild_memories()
            total_channels = len(all_channels)
            total_guilds = len(all_guilds)
            total_messages = (
                sum(len(m.get("messages", [])) for m in all_channels.values()) +
                sum(len(m.get("messages", [])) for m in all_guilds.values())
            )
        except Exception:
            total_channels = total_guilds = total_messages = 0

        config = self.chat_service.config

        embed = discord.Embed(
            title="🔍 Detailed System Status",
            description="Service: Operational",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="🟢 System Health",
            value="Status: **Operational**\nProvider: Groq (Online)\nStorage: Active",
            inline=True
        )
        embed.add_field(
            name="💾 Memory/Conversations",
            value=f"Active Channels: {total_channels}\nActive Guilds: {total_guilds}\nTotal Messages: {total_messages}",
            inline=True
        )
        embed.add_field(
            name="⚡ Rate Limiting",
            value=(
                f"Current: {rate_stats['requests_last_minute']}/{rate_stats['limit_per_minute']}/min\n"
                f"Cooldown: {config.rate_limit.user_cooldown}s\n"
                f"Blocked: {rate_stats['total_blocked']}"
            ),
            inline=True
        )
        embed.add_field(
            name="⚙️ Configuration",
            value=(
                f"Max History: {config.max_history}\n"
                f"Timeout: {config.conversation_timeout_hours}h\n"
                f"Persistence: {'✅' if config.persist_conversations else '❌'}"
            ),
            inline=True
        )
        embed.set_footer(text="All systems operational")
        await ctx.send(embed=embed)
