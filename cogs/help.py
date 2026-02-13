import discord
from discord.ext import commands
from discord import app_commands
import time
from datetime import datetime



class PingEmbeds:
    """Discord-style ping embed"""
    
    @staticmethod
    def pong(client_latency: int, shard_latency: int) -> discord.Embed:
        """Beautiful ping embed with timestamp in top right"""
        
        # Dynamic color based on latency
        if client_latency < 100:
            color = 0x57f287  # Discord green
            status = "🟢 Excellent"
        elif client_latency < 200:
            color = 0xfee75c  # Discord yellow  
            status = "🟡 Good"
        elif client_latency < 300:
            color = 0xfaa61a  # Discord orange
            status = "🟠 Fair"
        else:
            color = 0xed4245  # Discord red
            status = "🔴 Poor"

        current_time = datetime.now().strftime("%I:%M %p")  

        
        embed = discord.Embed(
            title=f"🏓 PONG / LATENCY 🏓 • {current_time}", 
            description=f"**Status:** {status}",
            color=color
        )
        
        # Gateway latency
        embed.add_field(
            name="🌐 Gateway Latency",
            value=f"```yaml\n{client_latency} MS\n```",
            inline=True
        )
        
        # API latency
        embed.add_field(
            name="⚡ API Latency",
            value=f"```yaml\n{shard_latency} MS\n```",
            inline=True
        )
        
        # Empty field for spacing
        embed.add_field(name="", value="", inline=False)
        
        # Warning
        embed.add_field(
            name="",
            value="> ⚠️ Issues on Discord's side could create weird or high latency.",
            inline=False
        )
        
        return embed




class HelpCommand(commands.MinimalHelpCommand):
    async def send_pages(self):
        destination = self.get_destination()
        
        embed = discord.Embed(
            title="🤖 MultiBot Help",
            description="Here are all available commands:",
            color=discord.Color.blue()
        )
        
        for page in self.paginator.pages:
            embed.add_field(name="\u200b", value=page, inline=False)
        
        embed.set_footer(text=f"Use {self.context.prefix}help <command> for more info")
        await destination.send(embed=embed)
    
    async def send_command_help(self, command):
        embed = discord.Embed(
            title=f"📖 {self.get_command_signature(command)}",
            color=discord.Color.green()
        )
        
        if command.help:
            embed.description = command.help
        
        if command.aliases:
            embed.add_field(
                name="Aliases",
                value=", ".join(f"`{alias}`" for alias in command.aliases),
                inline=False
            )
        
        await self.get_destination().send(embed=embed)
    
    async def send_cog_help(self, cog):
        embed = discord.Embed(
            title=f"📂 {cog.qualified_name} Commands",
            description=cog.description or "No description available",
            color=discord.Color.purple()
        )
        
        commands_list = await self.filter_commands(cog.get_commands(), sort=True)
        for command in commands_list:
            embed.add_field(
                name=self.get_command_signature(command),
                value=command.short_doc or "No help available",
                inline=False
            )
        
        await self.get_destination().send(embed=embed)


class Help(commands.Cog):
    """Help and information commands"""
    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = HelpCommand()
        bot.help_command.cog = self
    
    def cog_unload(self):
        self.bot.help_command = self._original_help_command
    
    # Slash command: Help overview
    @app_commands.command(name='help')
    @app_commands.describe(command='Specific command to get help for (optional)')
    async def help_slash(self, interaction: discord.Interaction, command: str = None):
        """Show bot commands and help information"""
        if command:
            # Show help for specific command
            cmd = self.bot.get_command(command)
            if cmd:
                embed = discord.Embed(
                    title=f"📖 Help: {cmd.name}",
                    description=cmd.help or "No description available",
                    color=discord.Color.green()
                )
                
                # Show usage
                usage = f"/{cmd.name}"
                if hasattr(cmd, 'clean_params'):
                    for param_name, param in cmd.clean_params.items():
                        if param.default == param.empty:
                            usage += f" <{param_name}>"
                        else:
                            usage += f" [{param_name}]"
                
                embed.add_field(name="Usage", value=f"`{usage}`", inline=False)
                
                if cmd.aliases:
                    embed.add_field(name="Aliases", value=", ".join(f"`{a}`" for a in cmd.aliases), inline=False)
                
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(f"❌ Command `{command}` not found!", ephemeral=True)
        else:
            # Show all commands by category
            embed = discord.Embed(
                title="🤖 MultiBot Help",
                description="Here are all available command categories:",
                color=discord.Color.blue()
            )
            
            # Group commands by cog
            for cog_name, cog in self.bot.cogs.items():
                if cog_name in ['Help', 'ErrorHandler']:  # Skip utility cogs
                    continue
                
                commands_list = [cmd for cmd in cog.get_commands() if not cmd.hidden]
                if commands_list:
                    command_names = ", ".join([f"`{cmd.name}`" for cmd in commands_list[:5]])
                    if len(commands_list) > 5:
                        command_names += f" *+{len(commands_list)-5} more*"
                    
                    embed.add_field(
                        name=f"📂 {cog_name}",
                        value=command_names,
                        inline=False
                    )
            
            embed.set_footer(text="Use /help <command> for detailed information • Prefix: !")
            await interaction.response.send_message(embed=embed)
    
    # Slash command: Commands list
    @app_commands.command(name='commands')
    async def commands_slash(self, interaction: discord.Interaction):
        """List all available commands"""
        embed = discord.Embed(
            title="📜 All Commands",
            description="Complete list of bot commands:",
            color=discord.Color.blue()
        )
        
        # Moderation
        embed.add_field(
            name="🛡️ Moderation",
            value="`/kick` `/ban` `/unban` `/timeout` `/purge`",
            inline=False
        )
        
        # Management
        embed.add_field(
            name="⚙️ Management",
            value="`/createrole` `/deleterole` `/addrole` `/removerole` `/createchannel` `/deletechannel` `/createcategory`",
            inline=False
        )
        
        # Chat & Fun
        embed.add_field(
            name="🎮 Chat & Fun",
            value="`/8ball` `/roll` `/flip` `/choose` `/serverinfo` `/userinfo`",
            inline=False
        )
        
        # Music
        embed.add_field(
            name="🎵 Music",
            value="`/join` `/play` `/pause` `/resume` `/skip` `/stop` `/leave` `/queue` `/volume` `/nowplaying`",
            inline=False
        )
        
        # Info
        embed.add_field(
            name="ℹ️ Information",
            value="`/help` `/commands` `/about` `/ping`",
            inline=False
        )
        
        embed.set_footer(text="Use /help <command> for details • All commands also work with ! prefix")
        await interaction.response.send_message(embed=embed)
    
    # Hybrid about command
    @commands.hybrid_command(name='about')
    async def about(self, ctx):
        """Information about the bot"""
        embed = discord.Embed(
            title="🤖 MultiBot",
            description="A multipurpose Discord bot with moderation, music, and more!",
            color=discord.Color.blue()
        )
        embed.add_field(name="Prefix", value="`!` or `/`", inline=True)
        embed.add_field(name="Servers", value=len(self.bot.guilds), inline=True)
        embed.add_field(name="Users", value=sum(g.member_count for g in self.bot.guilds), inline=True)
        embed.add_field(name="Commands", value=len(self.bot.commands), inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Version", value="discord.py 2.x", inline=True)
        embed.set_footer(text="Made with discord.py")
        
        await ctx.send(embed=embed)
    
    # Discord-style ping command
    @commands.hybrid_command(name='ping', description='Check bot latency')
    async def ping(self, ctx):
        """Check bot latency"""
        # Client latency (WebSocket/Gateway)
        client_latency = round(self.bot.latency * 1000)

        # Start timing for shard latency (API)
        start = time.perf_counter()

        # Defer to show "Bot is thinking..."
        if ctx.interaction:
            await ctx.interaction.response.defer()

        # Calculate shard latency
        shard_latency = round((time.perf_counter() - start) * 1000)

        # Create Discord-style embed (timestamp automatically top right)
        embed = PingEmbeds.pong(client_latency, shard_latency)

        # Send
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Help(bot))
