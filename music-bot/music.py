"""
Standalone Music Bot
A dedicated Discord bot for music playback using yt-dlp.
No Lavalink required! Supports YouTube, Spotify, SoundCloud, and 1000+ platforms.
"""

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging
import asyncio
from typing import List, Optional

from config import MusicBotConfig

logging.basicConfig(
    level=logging.INFO,
    format='[{asctime}] [{levelname:<8}] {name}: {message}',
    datefmt='%Y-%m-%d %H:%M:%S',
    style='{',
    handlers=[
        logging.FileHandler(MusicBotConfig.LOG_FILE, encoding='utf-8', mode='a'),
        logging.StreamHandler()
    ]
)

# Show yt-dlp output in terminal
logging.getLogger('yt_dlp').setLevel(logging.WARNING)
logging.getLogger('discord.gateway').setLevel(logging.WARNING)
logging.getLogger('discord.voice_state').setLevel(logging.INFO)

load_dotenv()
TOKEN = MusicBotConfig.get_discord_token()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True  # Required for voice connections
intents.guild_messages = True
intents.members = True


class MusicBot(commands.Bot):
    """Standalone Music Bot class"""
    
    def __init__(self):
        super().__init__(
            command_prefix=MusicBotConfig.COMMAND_PREFIX,
            intents=intents,
            max_messages=1000,
            heartbeat_timeout=60,
            guild_ready_timeout=10,
        )
        self.cogs_dir = 'music'
        self.loaded_cogs: List[str] = []
    
    async def setup_hook(self):
        """Called after the bot is initialized but before login"""
        logger.info("Setting up music bot...")
        await self.load_all_cogs()
    
    async def load_all_cogs(self):
        """Load all available cogs from the cogs directory"""
        self.loaded_cogs = []
        
        if not os.path.exists(self.cogs_dir):
            logger.warning(f"Cogs directory '{self.cogs_dir}' not found")
            return
        
        # Load the music cog directly
        try:
            await self.load_extension('music')
            self.loaded_cogs.append('music')
            logger.info(f"✅ Loaded cog: music")
        except Exception as e:
            logger.error(f"❌ Failed to load cog music: {e}")
        
        logger.info(f"Loaded {len(self.loaded_cogs)} cogs successfully")
    
    async def unload_all_cogs(self):
        """Unload all currently loaded cogs"""
        for cog_name in self.loaded_cogs.copy():
            try:
                await self.unload_extension(f'music.{cog_name}')
                self.loaded_cogs.remove(cog_name)
                logger.info(f"✅ Unloaded cog: {cog_name}")
            except Exception as e:
                logger.error(f"❌ Failed to unload cog {cog_name}: {e}")
    
    async def reload_all_cogs(self):
        """Reload all cogs"""
        logger.info("Reloading all cogs...")
        await self.unload_all_cogs()
        await self.load_all_cogs()
    
    async def load_cog(self, cog_name: str) -> bool:
        """Load a specific cog by name"""
        try:
            await self.load_extension(f'music.{cog_name}')
            if cog_name not in self.loaded_cogs:
                self.loaded_cogs.append(cog_name)
            logger.info(f"✅ Loaded cog: {cog_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load cog {cog_name}: {e}")
            return False
    
    async def unload_cog(self, cog_name: str) -> bool:
        """Unload a specific cog by name"""
        try:
            await self.unload_extension(f'music.{cog_name}')
            if cog_name in self.loaded_cogs:
                self.loaded_cogs.remove(cog_name)
            logger.info(f"✅ Unloaded cog: {cog_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to unload cog {cog_name}: {e}")
            return False
    
    async def reload_cog(self, cog_name: str) -> bool:
        """Reload a specific cog by name"""
        try:
            await self.reload_extension(f'music.{cog_name}')
            logger.info(f"✅ Reloaded cog: {cog_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to reload cog {cog_name}: {e}")
            return False
    
    async def on_ready(self):
        """Called when the bot is ready"""
        # Download cookies first
        from music.logic.player_manager import download_youtube_cookies
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, download_youtube_cookies)

        logger.info(f'🎵 Music Bot connected as {self.user}')
        logger.info(f'📡 Connected to {len(self.guilds)} guilds')
        
        # Sync slash commands with Discord
        try:
            synced = await self.tree.sync()
            logger.info(f'✅ Synced {len(synced)} slash commands')
        except Exception as e:
            logger.error(f'❌ Failed to sync commands: {e}')
        
        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{MusicBotConfig.COMMAND_PREFIX}play | Music Bot"
        )
        await self.change_presence(activity=activity)
        
        logger.info("🎵 Music Bot is ready!")
    
    async def on_command_error(self, ctx, error):
        """Global error handler for commands"""
        if isinstance(error, commands.CommandNotFound):
            return
        
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.")
            return
        
        if isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I don't have the required permissions to execute this command.")
            return
        
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏰ Command on cooldown. Try again in {error.retry_after:.2f} seconds.")
            return
        
        # Log unexpected errors
        logger.error(f"Command error in {ctx.command}: {error}", exc_info=error)


async def main():
    """Main entry point for the music bot"""
    if not MusicBotConfig.validate():
        logger.error("❌ DISCORD_TOKEN not found in .env file!")
        return
    
    bot = MusicBot()
    
    try:
        logger.info("🎵 Starting Music Bot...")
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        logger.info("🛑 Music Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=e)
    finally:
        if not bot.is_closed():
            await bot.close()
        logger.info("🎵 Music Bot shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
