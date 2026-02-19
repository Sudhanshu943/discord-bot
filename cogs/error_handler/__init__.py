"""Error Handler Cog - Handles Discord.py errors and exceptions"""

from .cog import ErrorHandler


async def setup(bot):
    """Setup function to add the ErrorHandler cog to the bot"""
    await bot.add_cog(ErrorHandler(bot))


async def teardown(bot):
    """Teardown function to remove the ErrorHandler cog from the bot"""
    await bot.remove_cog("ErrorHandler")
