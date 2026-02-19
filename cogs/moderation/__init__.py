"""Moderation Cog - Provides moderation commands for server management"""

from .cog import Moderation


async def setup(bot):
    """Setup function to add the Moderation cog to the bot"""
    await bot.add_cog(Moderation(bot))


async def teardown(bot):
    """Teardown function to remove the Moderation cog from the bot"""
    await bot.remove_cog("Moderation")
