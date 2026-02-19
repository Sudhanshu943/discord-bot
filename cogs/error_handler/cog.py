import discord
from discord.ext import commands
import traceback
import sys

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Global error handler for both text and slash commands"""
        
        # Ignore if command has local error handler
        if hasattr(ctx.command, 'on_error'):
            return
        
        # Get original error
        error = getattr(error, 'original', error)
        
        # Command not found - ignore silently
        if isinstance(error, commands.CommandNotFound):
            return
        
        # Helper function to send error message (handles both ctx and interaction)
        async def send_error(message):
            try:
                # Check if it's a slash command interaction
                if ctx.interaction:
                    # Check if already responded
                    if ctx.interaction.response.is_done():
                        # Use followup if already responded
                        await ctx.interaction.followup.send(message, ephemeral=True)
                    else:
                        # Use response if not responded yet
                        await ctx.interaction.response.send_message(message, ephemeral=True)
                else:
                    # Regular text command
                    await ctx.send(message)
            except discord.errors.NotFound:
                # Interaction expired, try channel send as fallback
                try:
                    await ctx.channel.send(f"{ctx.author.mention} {message}")
                except:
                    pass  # Silently fail if can't send
            except Exception as e:
                # Log other errors but don't crash
                print(f"Error sending error message: {e}")
        
        # Missing permissions
        if isinstance(error, commands.MissingPermissions):
            missing = ", ".join(error.missing_permissions)
            await send_error(f"❌ You need **{missing}** permission(s) to use this command!")
        
        # Bot missing permissions
        elif isinstance(error, commands.BotMissingPermissions):
            missing = ", ".join(error.missing_permissions)
            await send_error(f"❌ I need **{missing}** permission(s) to execute this command!")
        
        # Missing required argument
        elif isinstance(error, commands.MissingRequiredArgument):
            await send_error(f"❌ Missing required argument: **{error.param.name}**\nUse `/help {ctx.command}` for usage.")
        
        # Bad argument
        elif isinstance(error, commands.BadArgument):
            await send_error(f"❌ Invalid argument provided!\nUse `/help {ctx.command}` for usage.")
        
        # Member not found
        elif isinstance(error, commands.MemberNotFound):
            await send_error(f"❌ Member not found: **{error.argument}**")
        
        # User not found
        elif isinstance(error, commands.UserNotFound):
            await send_error(f"❌ User not found: **{error.argument}**")
        
        # Channel not found
        elif isinstance(error, commands.ChannelNotFound):
            await send_error(f"❌ Channel not found: **{error.argument}**")
        
        # Role not found
        elif isinstance(error, commands.RoleNotFound):
            await send_error(f"❌ Role not found: **{error.argument}**")
        
        # Command on cooldown
        elif isinstance(error, commands.CommandOnCooldown):
            await send_error(f"⏳ This command is on cooldown. Try again in **{error.retry_after:.1f}s**")
        
        # Not owner
        elif isinstance(error, commands.NotOwner):
            await send_error("❌ Only the bot owner can use this command!")
        
        # No private message
        elif isinstance(error, commands.NoPrivateMessage):
            await send_error("❌ This command cannot be used in DMs!")
        
        # Check failure (custom checks)
        elif isinstance(error, commands.CheckFailure):
            await send_error("❌ You don't have permission to use this command!")
        
        # Discord HTTP exceptions
        elif isinstance(error, discord.errors.Forbidden):
            await send_error("❌ I don't have permission to do that!")
        
        # Discord NotFound (interaction expired, unknown interaction)
        elif isinstance(error, discord.errors.NotFound):
            error_msg = str(error)
            if "10062" in error_msg or "Unknown interaction" in error_msg:
                # Interaction expired or network issue - no need to show error
                logger.warning(f"Interaction expired or not found: {error_msg}")
                return  # Silent return - interaction already expired
            await send_error("❌ The resource was not found!")
        
        # Discord Gateway errors (network issues)
        elif isinstance(error, discord.errors.GatewayError):
            await send_error("⚠️ Network issue detected. Please try again in a moment.")
        
        # Discord ConnectionClosed
        elif isinstance(error, discord.errors.ConnectionClosed):
            await send_error("⚠️ Connection closed. Please try again.")
        
        # Unknown error - log it
        else:
            error_msg = f"❌ An unexpected error occurred: `{str(error)[:100]}`"
            await send_error(error_msg)
            
            # Print full traceback to console and log file
            print(f'\n=== Error in command {ctx.command} ===', file=sys.stderr)
            print(f'User: {ctx.author} (ID: {ctx.author.id})', file=sys.stderr)
            print(f'Guild: {ctx.guild} (ID: {ctx.guild.id if ctx.guild else "DM"})', file=sys.stderr)
            print(f'Channel: {ctx.channel} (ID: {ctx.channel.id})', file=sys.stderr)
            print(f'Message: {ctx.message.content if hasattr(ctx, "message") else "Slash command"}', file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            print('=' * 50, file=sys.stderr)

    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        """Catch errors outside of commands"""
        print(f'\n=== Error in event {event} ===', file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print('=' * 50, file=sys.stderr)

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
