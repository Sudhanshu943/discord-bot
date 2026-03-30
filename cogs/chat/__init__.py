"""
AI Chat Module
===============================

Main module initialization with setup() function for Discord bot extension loading.
Coordinates all layers: cogs, core, models, services, storage, and integrations.
"""

import discord
from discord.ext import commands

import logging

from .cogs import ChatCog, StatsCog, AdminCog

logger = logging.getLogger(__name__)


async def setup(bot: commands.Bot) -> None:
    """
    Initialize the chat module and register all cogs with the bot.
    
    This function is called by `bot.load_extension("chat")` in the main bot.py file.
    It sets up all service layers and registers the Discord command handlers.
    
    Args:
        bot: The Discord bot instance
        
    Example:
        # In bot.py
        await bot.load_extension("chat")
    """
    
    # Initialize main ChatCog (handles all core chat functionality)
    chat_cog = ChatCog(bot)
    await bot.add_cog(chat_cog)
    logger.info("✅ ChatCog loaded")

    # Initialize StatsCog
    stats_cog = StatsCog(
        bot,
        chat_cog.chat_service,
        chat_cog.rate_limiter,
        chat_cog.memory_manager,
        chat_cog.storage
    )
    await bot.add_cog(stats_cog)
    logger.info("✅ StatsCog loaded")

    # Initialize AdminCog
    admin_cog = AdminCog(bot, chat_cog.rate_limiter, chat_cog.config, chat_cog.storage)
    await bot.add_cog(admin_cog)
    logger.info("✅ AdminCog loaded")

    logger.info("=" * 50)
    logger.info("🤖 Chat module fully initialized!")
    logger.info("=" * 50)
