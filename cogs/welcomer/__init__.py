"""Welcomer Cog - Handles member welcome and farewell messages"""

from .cog import Welcomer


async def setup(bot):
    """Setup function to add the Welcomer cog to the bot"""
    await bot.add_cog(Welcomer(bot))


async def teardown(bot):
    """Teardown function to remove the Welcomer cog from the bot"""
    await bot.remove_cog("Welcomer")
