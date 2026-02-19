"""Help Cog - Provides help commands and documentation for the bot"""

from .cog import Help


async def setup(bot):
    """Setup function to add the Help cog to the bot"""
    await bot.add_cog(Help(bot))


async def teardown(bot):
    """Teardown function to remove the Help cog from the bot"""
    await bot.remove_cog("Help")
