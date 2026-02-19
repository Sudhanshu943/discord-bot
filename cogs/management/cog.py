import discord
from discord.ext import commands

class Management(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Create role
    @commands.command(name='createrole')
    @commands.has_permissions(manage_roles=True)
    async def create_role(self, ctx, *, role_name: str):
        """Create a new role"""
        guild = ctx.guild
        existing_role = discord.utils.get(guild.roles, name=role_name)
        if existing_role:
            return await ctx.send(f"❌ Role `{role_name}` already exists!")
        
        new_role = await guild.create_role(name=role_name, mentionable=True)
        await ctx.send(f"✅ Created role {new_role.mention}")

    # Delete role
    @commands.command(name='deleterole')
    @commands.has_permissions(manage_roles=True)
    async def delete_role(self, ctx, role: discord.Role):
        """Delete an existing role"""
        if role >= ctx.author.top_role:
            return await ctx.send("❌ Cannot delete a role higher than yours!")
        
        await role.delete()
        await ctx.send(f"✅ Deleted role `{role.name}`")

    # Assign role to user
    @commands.command(name='addrole')
    @commands.has_permissions(manage_roles=True)
    async def add_role(self, ctx, member: discord.Member, role: discord.Role):
        """Add a role to a member"""
        if role >= ctx.author.top_role:
            return await ctx.send("❌ Cannot assign a role higher than yours!")
        if role in member.roles:
            return await ctx.send(f"❌ {member.mention} already has {role.mention}!")
        
        await member.add_roles(role)
        await ctx.send(f"✅ Added {role.mention} to {member.mention}")

    # Remove role from user
    @commands.command(name='removerole')
    @commands.has_permissions(manage_roles=True)
    async def remove_role(self, ctx, member: discord.Member, role: discord.Role):
        """Remove a role from a member"""
        if role not in member.roles:
            return await ctx.send(f"❌ {member.mention} doesn't have {role.mention}!")
        
        await member.remove_roles(role)
        await ctx.send(f"✅ Removed {role.mention} from {member.mention}")

    # Create text channel
    @commands.command(name='createchannel')
    @commands.has_permissions(manage_channels=True)
    async def create_channel(self, ctx, channel_type: str, *, channel_name: str):
        """Create a text or voice channel. Usage: !createchannel text/voice name"""
        guild = ctx.guild
        
        if channel_type.lower() == 'text':
            channel = await guild.create_text_channel(channel_name)
            await ctx.send(f"✅ Created text channel {channel.mention}")
        elif channel_type.lower() == 'voice':
            channel = await guild.create_voice_channel(channel_name)
            await ctx.send(f"✅ Created voice channel `{channel.name}`")
        else:
            await ctx.send("❌ Invalid type! Use `text` or `voice`")

    # Delete channel
    @commands.command(name='deletechannel')
    @commands.has_permissions(manage_channels=True)
    async def delete_channel(self, ctx, channel: discord.TextChannel):
        """Delete a text channel"""
        await channel.delete()
        await ctx.send(f"✅ Deleted channel `{channel.name}`")

    # Create category
    @commands.command(name='createcategory')
    @commands.has_permissions(manage_channels=True)
    async def create_category(self, ctx, *, category_name: str):
        """Create a new category"""
        guild = ctx.guild
        category = await guild.create_category(category_name)
        await ctx.send(f"✅ Created category `{category.name}`")

    # Move channel to category
    @commands.command(name='movechannel')
    @commands.has_permissions(manage_channels=True)
    async def move_channel(self, ctx, channel: discord.TextChannel, *, category_name: str):
        """Move a channel to a category"""
        guild = ctx.guild
        category = discord.utils.get(guild.categories, name=category_name)
        
        if not category:
            return await ctx.send(f"❌ Category `{category_name}` not found!")
        
        await channel.edit(category=category)
        await ctx.send(f"✅ Moved {channel.mention} to `{category.name}`")

    # Error handling
    @create_role.error
    @delete_role.error
    @add_role.error
    @remove_role.error
    @create_channel.error
    @delete_channel.error
    async def manage_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command!")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid argument. Check command usage with `!help`")

async def setup(bot):
    await bot.add_cog(Management(bot))
