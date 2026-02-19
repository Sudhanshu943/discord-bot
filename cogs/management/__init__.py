"""Management Cog - Provides bot and server management commands"""

from .cog import Management


async def setup(bot):
    """Setup function to add the Management cog to the bot"""
    await bot.add_cog(Management(bot))


async def teardown(bot):
    """Teardown function to remove the Management cog from the bot"""
    await bot.remove_cog("Management")
