"""
Simple test bot to verify Discord voice connection - with region override
"""
import asyncio

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.command()
async def join(ctx):
    """Join voice channel"""
    if not ctx.author.voice:
        await ctx.send("You're not in a voice channel!")
        return
    
    channel = ctx.author.voice.channel
    await ctx.send(f"Joining {channel.name}...")

    await asyncio.sleep(2)
    
    # Try with a different region - use 'us-west' or 'us-east'
    try:
        vc = await channel.connect(timeout=10.0, reconnect=False)
        await ctx.send(f"Connected! Voice client: {vc}")
    except Exception as e:
        await ctx.send(f"Failed: {e}")

@bot.command()
async def leave(ctx):
    """Leave voice channel"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Disconnected!")

bot.run(TOKEN)
