import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging
import asyncio
from typing import List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[{asctime}] [{levelname:<8}] {name}: {message}',
    datefmt='%Y-%m-%d %H:%M:%S',
    style='{',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8', mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('discord')

# Reduce gateway verbosity
logging.getLogger('discord.gateway').setLevel(logging.WARNING)

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True  # Required for voice connections
intents.guild_messages = True
intents.members = True  # Fixed: was guild_members


class DiscordBot(commands.Bot):
    """Main Discord Bot class with enhanced architecture"""
    
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=intents,
            max_messages=1000,
            heartbeat_timeout=60,
            guild_ready_timeout=10,
        )
        self.cogs_dir = 'cogs'
        self.loaded_cogs: List[str] = []
    
    async def setup_hook(self):
        """Called after the bot is initialized but before login"""
        logger.info("Setting up bot...")
        await self.load_all_cogs()
    
    async def load_all_cogs(self):
        """Load all available cogs from the cogs directory"""
        self.loaded_cogs = []
        
        if not os.path.exists(self.cogs_dir):
            logger.warning(f"Cogs directory '{self.cogs_dir}' not found")
            return
        
        for item in os.listdir(self.cogs_dir):
            item_path = os.path.join(self.cogs_dir, item)
            
            # Skip hidden files and directories
            if item.startswith('_') or item == '__pycache__':
                continue
                
            # Load cog packages (directories with __init__.py)
            if os.path.isdir(item_path):
                init_path = os.path.join(item_path, '__init__.py')
                if os.path.exists(init_path):
                    try:
                        await self.load_extension(f'cogs.{item}')
                        self.loaded_cogs.append(item)
                        logger.info(f"✅ Loaded cog: {item}")
                    except Exception as e:
                        logger.error(f"❌ Failed to load cog {item}: {e}")
                        continue
        
        logger.info(f"Loaded {len(self.loaded_cogs)} cogs successfully")
    
    async def unload_all_cogs(self):
        """Unload all currently loaded cogs"""
        for cog_name in self.loaded_cogs.copy():
            try:
                await self.unload_extension(f'cogs.{cog_name}')
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
        if cog_name in self.loaded_cogs:
            logger.warning(f"Cog {cog_name} is already loaded")
            return False
            
        try:
            await self.load_extension(f'cogs.{cog_name}')
            self.loaded_cogs.append(cog_name)
            logger.info(f"✅ Loaded cog: {cog_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load cog {cog_name}: {e}")
            return False
    
    async def unload_cog(self, cog_name: str) -> bool:
        """Unload a specific cog by name"""
        if cog_name not in self.loaded_cogs:
            logger.warning(f"Cog {cog_name} is not loaded")
            return False
            
        try:
            await self.unload_extension(f'cogs.{cog_name}')
            self.loaded_cogs.remove(cog_name)
            logger.info(f"✅ Unloaded cog: {cog_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to unload cog {cog_name}: {e}")
            return False
    
    async def reload_cog(self, cog_name: str) -> bool:
        """Reload a specific cog by name"""
        try:
            if cog_name in self.loaded_cogs:
                await self.unload_extension(f'cogs.{cog_name}')
            
            await self.load_extension(f'cogs.{cog_name}')
            
            if cog_name not in self.loaded_cogs:
                self.loaded_cogs.append(cog_name)
                
            logger.info(f"✅ Reloaded cog: {cog_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to reload cog {cog_name}: {e}")
            return False


bot = DiscordBot()


@bot.event
async def on_ready():
    logger.info(f'{bot.user} is online!')
    logger.info(f'Connected to {len(bot.guilds)} guilds')
    logger.info(f'Loaded cogs: {", ".join(bot.loaded_cogs)}')
    
    try:
        # Sync commands globally
        synced = await bot.tree.sync()
        logger.info(f"✅ Synced {len(synced)} commands globally")
        
        # Also sync to all connected guilds for instant availability
        for guild in bot.guilds:
            try:
                bot.tree.copy_global_to(guild=guild)
                guild_synced = await bot.tree.sync(guild=guild)
                logger.info(f"✅ Synced {len(guild_synced)} commands to guild: {guild.name} (ID: {guild.id})")
            except Exception as e:
                logger.error(f"❌ Failed to sync commands to guild {guild.name} (ID: {guild.id}): {e}")
                
    except Exception as e:
        logger.error(f"❌ Failed to sync commands: {e}")


@bot.event
async def on_disconnect():
    logger.warning("Bot disconnected from Discord Gateway")


@bot.event
async def on_resume():
    logger.info("Bot resumed connection to Discord Gateway")


# Cog management commands
@bot.command()
@commands.is_owner()
async def sync(ctx, guild_id: Optional[int] = None):
    """Sync slash commands (owner only)"""
    try:
        if guild_id:
            guild = discord.Object(id=guild_id)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            await ctx.send(f"✅ Synced {len(synced)} commands to guild {guild_id}")
        else:
            synced = await bot.tree.sync()
            await ctx.send(f"✅ Synced {len(synced)} commands globally")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")


@bot.command()
@commands.is_owner()
async def load(ctx, cog_name: str):
    """Load a specific cog (owner only)"""
    if await bot.load_cog(cog_name):
        await ctx.send(f"✅ Loaded cog: {cog_name}")
    else:
        await ctx.send(f"❌ Failed to load cog: {cog_name}")


@bot.command()
@commands.is_owner()
async def unload(ctx, cog_name: str):
    """Unload a specific cog (owner only)"""
    if await bot.unload_cog(cog_name):
        await ctx.send(f"✅ Unloaded cog: {cog_name}")
    else:
        await ctx.send(f"❌ Failed to unload cog: {cog_name}")


@bot.command()
@commands.is_owner()
async def reload(ctx, cog_name: Optional[str] = None):
    """Reload a specific cog or all cogs (owner only)"""
    if cog_name:
        if await bot.reload_cog(cog_name):
            await ctx.send(f"✅ Reloaded cog: {cog_name}")
        else:
            await ctx.send(f"❌ Failed to reload cog: {cog_name}")
    else:
        await bot.reload_all_cogs()
        await ctx.send(f"✅ Reloaded all cogs ({len(bot.loaded_cogs)} loaded)")


@bot.command()
@commands.is_owner()
async def cogs(ctx):
    """List all loaded cogs (owner only)"""
    if bot.loaded_cogs:
        embed = discord.Embed(
            title="Loaded Cogs",
            description="\n".join(f"• {cog}" for cog in sorted(bot.loaded_cogs)),
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("No cogs are currently loaded")


async def main():
    """Main function with reconnection handling"""
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            logger.info("Starting bot...")
            await bot.start(TOKEN)
            retry_count = 0  # Reset on successful connection
        except discord.LoginFailure:
            logger.error("Invalid token - cannot reconnect")
            break
        except Exception as e:
            retry_count += 1
            logger.error(f"Error (attempt {retry_count}/{max_retries}): {e}")
            if retry_count < max_retries:
                wait_time = min(5 * retry_count, 30)  # Exponential backoff
                logger.info(f"Reconnecting in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.error("Max retries reached. Exiting.")
                break


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
