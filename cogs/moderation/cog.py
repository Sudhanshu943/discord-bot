import discord
from discord.ext import commands
from discord import app_commands

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Hybrid kick command (works as both !kick and /kick)
    @commands.hybrid_command(name='kick')
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = None):
        """Kick a member from the server"""
        if member == ctx.author:
            return await ctx.send("You can't kick yourself!")
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("You can't kick someone with a higher or equal role!")
        
        await member.kick(reason=reason)
        await ctx.send(f"✅ {member.mention} has been kicked. Reason: {reason or 'No reason provided'}")

    # Hybrid ban command
    @commands.hybrid_command(name='ban')
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = None):
        """Ban a member from the server"""
        if member == ctx.author:
            return await ctx.send("You can't ban yourself!")
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("You can't ban someone with a higher or equal role!")
        
        await member.ban(reason=reason)
        await ctx.send(f"🔨 {member.mention} has been banned. Reason: {reason or 'No reason provided'}")

    # Hybrid timeout command
    @commands.hybrid_command(name='timeout')
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, minutes: int, *, reason: str = None):
        """Timeout a member for specified minutes"""
        if member == ctx.author:
            return await ctx.send("You can't timeout yourself!")
        if minutes < 1 or minutes > 40320:
            return await ctx.send("Duration must be between 1 minute and 28 days!")
        
        duration = discord.utils.utcnow() + discord.timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await ctx.send(f"⏰ {member.mention} timed out for {minutes} minutes. Reason: {reason or 'No reason provided'}")

    # Hybrid purge command
    @commands.hybrid_command(name='purge')
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        """Delete a number of messages (max 100)"""
        if amount < 1 or amount > 100:
            return await ctx.send("Amount must be between 1-100!")
        
        deleted = await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"🗑️ Deleted {len(deleted)-1} messages.", delete_after=3)

    # Pure slash command example (unban by ID)
    @app_commands.command(name='unban')
    @app_commands.describe(user_id='User ID to unban')
    async def unban_slash(self, interaction: discord.Interaction, user_id: str):
        """Unban a user by their ID"""
        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message("❌ You need Ban Members permission!", ephemeral=True)
        
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            await interaction.response.send_message(f"✅ {user.mention} has been unbanned.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
