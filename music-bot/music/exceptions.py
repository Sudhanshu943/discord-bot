"""
Music Error Handler Module
Custom exceptions and error handling for the music system
"""

import discord
from discord.ext import commands
import logging
from typing import Optional

logger = logging.getLogger('discord.music.errors')


class MusicError(Exception):
    """Base exception for music errors"""
    pass


class NotConnectedError(MusicError):
    """Raised when bot is not connected to voice"""
    pass


class NoTrackFoundError(MusicError):
    """Raised when no track is found for query"""
    pass


class QueueEmptyError(MusicError):
    """Raised when queue is empty"""
    pass


class NothingPlayingError(MusicError):
    """Raised when nothing is playing"""
    pass


class MusicErrorHandler:
    """Centralized error handling for music commands"""
    
    @staticmethod
    def get_error_message(error: Exception) -> str:
        """Get user-friendly error message"""
        # Custom music errors
        if isinstance(error, NotConnectedError):
            return "❌ Not connected to a voice channel! Use `/join` first."
        
        if isinstance(error, NoTrackFoundError):
            return "❌ No tracks found! Try a different search term."
        
        if isinstance(error, QueueEmptyError):
            return "❌ The queue is empty!"
        
        if isinstance(error, NothingPlayingError):
            return "❌ Nothing is playing right now!"
        
        # Discord errors
        if isinstance(error, discord.ClientException):
            return "❌ Voice connection error. Try disconnecting and reconnecting."
        
        if isinstance(error, discord.errors.NotFound):
            return "❌ Channel or message not found."
        
        if isinstance(error, discord.errors.Forbidden):
            return "❌ Missing permissions to perform this action."
        
        # Command errors
        if isinstance(error, commands.MissingRequiredArgument):
            return f"❌ Missing required argument: `{error.param.name}`"
        
        if isinstance(error, commands.BadArgument):
            return "❌ Invalid argument provided."
        
        if isinstance(error, commands.CommandOnCooldown):
            return f"❌ Command on cooldown. Try again in {error.retry_after:.1f} seconds."
        
        if isinstance(error, commands.MissingPermissions):
            return "❌ You don't have permission to use this command."
        
        if isinstance(error, commands.BotMissingPermissions):
            return "❌ I don't have the required permissions."
        
        # Generic error
        return f"❌ An error occurred: {str(error)}"
    
    @staticmethod
    async def handle_command_error(ctx: commands.Context, error: Exception):
        """Handle command error with appropriate response"""
        message = MusicErrorHandler.get_error_message(error)
        logger.error(f"Command error in {ctx.command}: {error}")
        
        try:
            if hasattr(ctx, 'interaction') and ctx.interaction:
                if ctx.interaction.response.is_done():
                    await ctx.interaction.followup.send(message, ephemeral=True)
                else:
                    await ctx.interaction.response.send_message(message, ephemeral=True)
            else:
                await ctx.send(message)
        except Exception as e:
            logger.error(f"Error sending error message: {e}")
