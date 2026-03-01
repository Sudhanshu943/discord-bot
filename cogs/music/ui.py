"""
Music UI Module - Professional Edition
Clean, modern design inspired by Spotify and YouTube Music
"""

import discord
from typing import Optional, List
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger('discord.music.ui')


class MusicEmbeds:
    """Premium embed designs"""
    
    # Professional color palette
    COLOR_PLAYING = 0x1ED760    # Spotify green
    COLOR_QUEUE = 0x5865F2      # Discord blurple  
    COLOR_ERROR = 0xFF0033      # Vibrant red
    COLOR_SUCCESS = 0x00D9A3    # Mint green
    
    @staticmethod
    def now_playing(song, requester: discord.Member = None) -> discord.Embed:
        """Beautiful now playing card"""
        embed = discord.Embed(color=MusicEmbeds.COLOR_PLAYING)
        
        # Clean title section
        embed.description = f"## 🎵 {song.title}\n"
        
        # Info bar with icons
        info_parts = []
        if hasattr(song, 'duration') and song.duration > 0:
            info_parts.append(f"⏱️ `{song.duration_str}`")
        if requester:
            info_parts.append(f"👤 {requester.mention}")
        
        if info_parts:
            embed.description += " • ".join(info_parts)
        
        # Large thumbnail for visual appeal
        if hasattr(song, 'thumbnail') and song.thumbnail:
            embed.set_image(url=song.thumbnail)
        
        # Footer with link
        if hasattr(song, 'url') and song.url:
            embed.set_footer(text="🎧 Click title to open in browser")
        
        return embed
    
    @staticmethod
    def added_to_queue(song, position: int) -> discord.Embed:
        """Minimal queue add notification"""
        embed = discord.Embed(
            description=f"### ➕ Added to queue\n**{song.title}**\n\n`Position #{position}` • `{song.duration_str}`",
            color=MusicEmbeds.COLOR_SUCCESS
        )
        
        if hasattr(song, 'thumbnail') and song.thumbnail:
            embed.set_thumbnail(url=song.thumbnail)
        
        return embed
    
    @staticmethod
    def queue_list(queue_items: List, current=None, total: int = 0) -> discord.Embed:
        """Clean queue display"""
        embed = discord.Embed(
            title="",
            color=MusicEmbeds.COLOR_QUEUE
        )
        
        # Header stats
        if total > 0:
            total_duration = sum(getattr(s, 'duration', 0) for s in queue_items)
            mins = int(total_duration // 60)
            embed.description = f"## 📋 Queue\n`{total} tracks` • `~{mins} minutes`\n"
        else:
            embed.description = "## 📋 Queue\n*Empty*\n"
        
        # Now playing (compact)
        if current:
            title_short = current.title[:60] + "..." if len(current.title) > 60 else current.title
            embed.add_field(
                name="▶️ Now Playing",
                value=f"**{title_short}**\n`{current.duration_str}`",
                inline=False
            )
        
        # Queue list (cleaner format)
        if queue_items:
            queue_text = ""
            for i, song in enumerate(queue_items[:10], 1):
                title = song.title[:45] + "..." if len(song.title) > 45 else song.title
                queue_text += f"`{i}.` {title} • `{song.duration_str}`\n"
            
            if len(queue_items) > 10:
                queue_text += f"\n*+{len(queue_items) - 10} more*"
            
            embed.add_field(name="📜 Up Next", value=queue_text, inline=False)
        
        return embed
    
    @staticmethod
    def error(message: str) -> discord.Embed:
        """Clean error message"""
        embed = discord.Embed(
            description=f"### ❌ Error\n{message}",
            color=MusicEmbeds.COLOR_ERROR
        )
        return embed
    
    @staticmethod
    def success(message: str) -> discord.Embed:
        """Clean success message"""
        embed = discord.Embed(
            description=f"### ✅ {message}",
            color=MusicEmbeds.COLOR_SUCCESS
        )
        return embed
    



class MusicControlsView(discord.ui.View):
    """Premium control layout - Grid Design"""

    def __init__(self, player, timeout: float = 300, auto_delete: bool = False):
        super().__init__(timeout=timeout)
        self.player = player
        self.message: Optional[discord.Message] = None
        self.auto_delete = auto_delete
        self._last_action_time = 0
        self._cooldown_seconds = 2
        self._update_states()

        if auto_delete:
            self.monitor_task = asyncio.create_task(self._monitor_playback())

    # ═══════════════════════════════════════
    # ROW 0 — PRIMARY PLAYBACK (5 buttons)
    # ═══════════════════════════════════════

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, custom_id="ctrl:prev", row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⏮️ Previous — Coming soon!", ephemeral=True)

    @discord.ui.button(emoji="⏸️", label="Pause", style=discord.ButtonStyle.primary, custom_id="ctrl:pause", row=0)
    async def pause_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._user_in_same_voice(interaction):
            return await interaction.response.send_message("❌ Join the same voice channel.", ephemeral=True)
        if not self.player or not (self.player.is_playing or self.player.is_paused):
            return await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)
        if self._on_cooldown():
            return await interaction.response.send_message("⏳ Slow down!", ephemeral=True)

        if self.player.is_paused:
            await self.player.resume()
            button.emoji = "⏸️"
            button.label = "Pause"
            button.style = discord.ButtonStyle.primary
            msg = "▶️ Resumed"
        else:
            await self.player.pause()
            button.emoji = "▶️"
            button.label = "Resume"
            button.style = discord.ButtonStyle.success
            msg = "⏸️ Paused"

        await interaction.response.send_message(msg, ephemeral=True)
        await interaction.message.edit(view=self)

    @discord.ui.button(emoji="⏭️", label="Skip", style=discord.ButtonStyle.secondary, custom_id="ctrl:skip", row=0)
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._user_in_same_voice(interaction):
            return await interaction.response.send_message("❌ Join the same voice channel.", ephemeral=True)
        if not self.player or not self.player.is_playing:
            return await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)
        if self._on_cooldown():
            return await interaction.response.send_message("⏳ Slow down!", ephemeral=True)

        skipped = self.player.current
        await self.player.delete_controller()
        await self.player.skip()
        msg = f"⏭️ Skipped: **{skipped.title[:40]}**" if skipped else "⏭️ Skipped"
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(emoji="⏹️", label="Stop", style=discord.ButtonStyle.danger, custom_id="ctrl:stop", row=0)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._user_in_same_voice(interaction):
            return await interaction.response.send_message("❌ Join the same voice channel.", ephemeral=True)
        if not self.player or not self.player.is_playing:
            return await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)
        if self._on_cooldown():
            return await interaction.response.send_message("⏳ Slow down!", ephemeral=True)

        await self.player.delete_controller()
        await self.player.stop()
        await interaction.response.send_message("⏹️ Stopped & queue cleared.", ephemeral=True)

    @discord.ui.button(emoji="🔊", label="Volume", style=discord.ButtonStyle.secondary, custom_id="ctrl:vol", row=0)
    async def volume_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._user_in_same_voice(interaction):
            return await interaction.response.send_message("❌ Join the same voice channel.", ephemeral=True)
        if not self.player or not self.player.is_playing:
            return await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)

        view = VolumeModal(self.player)
        current_vol = int(self.player.volume * 100)
        embed = discord.Embed(
            description=f"## 🔊 Volume Control\n"
                        f"{'█' * (current_vol // 10)}{'░' * (10 - current_vol // 10)} **{current_vol}%**",
            color=0x5865F2
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ═══════════════════════════════════════
    # ROW 1 — QUEUE & EXTRAS (4 buttons)
    # ═══════════════════════════════════════

    @discord.ui.button(emoji="🔀", label="Shuffle", style=discord.ButtonStyle.secondary, custom_id="ctrl:shuffle", row=1)
    async def shuffle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._user_in_same_voice(interaction):
            return await interaction.response.send_message("❌ Join the same voice channel.", ephemeral=True)
        if not self.player or self.player.queue_empty:
            return await interaction.response.send_message("❌ Queue is empty.", ephemeral=True)
        if self._on_cooldown():
            return await interaction.response.send_message("⏳ Slow down!", ephemeral=True)

        self.player.shuffle_queue()
        await interaction.response.send_message(f"🔀 Shuffled **{self.player.queue_count}** tracks", ephemeral=True)

    @discord.ui.button(emoji="🔁", label="Loop", style=discord.ButtonStyle.secondary, custom_id="ctrl:loop", row=1)
    async def loop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._user_in_same_voice(interaction):
            return await interaction.response.send_message("❌ Join the same voice channel.", ephemeral=True)
        if not self.player or not self.player.is_playing:
            return await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)
        if self._on_cooldown():
            return await interaction.response.send_message("⏳ Slow down!", ephemeral=True)

        self.player.loop = not self.player.loop
        if self.player.loop:
            button.style = discord.ButtonStyle.success
            button.label = "Loop ON"
            msg = "🔁 Loop **ON**"
        else:
            button.style = discord.ButtonStyle.secondary
            button.label = "Loop"
            msg = "🔁 Loop **OFF**"

        await interaction.response.send_message(msg, ephemeral=True)
        await interaction.message.edit(view=self)

    @discord.ui.button(emoji="📋", label="Queue", style=discord.ButtonStyle.primary, custom_id="ctrl:queue", row=1)
    async def queue_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player:
            return await interaction.response.send_message("❌ Not connected.", ephemeral=True)

        queue_items = self.player.get_queue_list(10)
        embed = MusicEmbeds.queue_list(queue_items, self.player.current, self.player.queue_count)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(emoji="🗑️", label="Clear Queue", style=discord.ButtonStyle.danger, custom_id="ctrl:clear", row=1)
    async def clear_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._user_in_same_voice(interaction):
            return await interaction.response.send_message("❌ Join the same voice channel.", ephemeral=True)
        if not self.player or self.player.queue_empty:
            return await interaction.response.send_message("❌ Queue already empty.", ephemeral=True)
        if self._on_cooldown():
            return await interaction.response.send_message("⏳ Slow down!", ephemeral=True)

        cleared = self.player.queue_count
        self.player.clear_queue()
        await interaction.response.send_message(f"🗑️ Cleared **{cleared}** tracks", ephemeral=True)

    def _on_cooldown(self) -> bool:
        now = asyncio.get_event_loop().time()
        if now - self._last_action_time < self._cooldown_seconds:
            return True
        self._last_action_time = now
        return False

    def _user_in_same_voice(self, interaction: discord.Interaction) -> bool:
        if not self.player or not self.player.voice_client:
            return False

        user_voice = getattr(interaction.user, "voice", None)
        if not user_voice or not user_voice.channel:
            return False

        return user_voice.channel == self.player.voice_client.channel

    async def _monitor_playback(self):
        """Monitor playback and delete controller when music ends"""
        try:
            while True:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                # Check if player stopped and queue is empty
                if self.player and not self.player.is_playing and not self.player.is_paused and self.player.queue_empty:
                    # Delete the controller message
                    if self.message:
                        try:
                            await self.message.delete()
                            logger.info("Deleted music controller - playback ended")
                        except:
                            pass
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in monitor task: {e}")
    
    def _update_states(self):
        """Update button states"""
        if not self.player:
            return
        
        for item in self.children:
            if hasattr(item, 'custom_id'):
                # Pause button state
                if item.custom_id == "ctrl:pause":
                    if self.player.is_paused:
                        item.emoji = "▶️"
                        item.style = discord.ButtonStyle.success
                    elif self.player.is_playing:
                        item.emoji = "⏸"
                        item.style = discord.ButtonStyle.secondary
                
                # Loop button state
                if item.custom_id == "ctrl:loop":
                    if self.player.loop:
                        item.style = discord.ButtonStyle.success
                    else:
                        item.style = discord.ButtonStyle.secondary

    async def on_timeout(self):
        """Disable buttons on timeout"""
        # Cancel monitor task
        if hasattr(self, 'monitor_task'):
            self.monitor_task.cancel()
        
        for item in self.children:
            item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass


class VolumeModal(discord.ui.View):
    """Compact volume slider"""
    
    def __init__(self, player, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.player = player
        self.vol = int(player.volume * 100) if player else 50
    
    async def _update(self, interaction: discord.Interaction):
        """Update volume display"""
        embed = discord.Embed(
            description=f"## 🔊 Volume\n### {self.vol}%",
            color=0x5865F2
        )
        try:
            await interaction.message.edit(embed=embed, view=self)
        except:
            pass
    
    @discord.ui.button(emoji="🔇", style=discord.ButtonStyle.danger, custom_id="v:0", row=0)
    async def v0(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.vol = 0
        self.player.set_volume(0)
        await interaction.response.defer()
        await self._update(interaction)
    
    @discord.ui.button(label="25%", style=discord.ButtonStyle.secondary, custom_id="v:25", row=0)
    async def v25(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.vol = 25
        self.player.set_volume(25)
        await interaction.response.defer()
        await self._update(interaction)
    
    @discord.ui.button(label="50%", style=discord.ButtonStyle.secondary, custom_id="v:50", row=0)
    async def v50(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.vol = 50
        self.player.set_volume(50)
        await interaction.response.defer()
        await self._update(interaction)
    
    @discord.ui.button(label="75%", style=discord.ButtonStyle.secondary, custom_id="v:75", row=0)
    async def v75(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.vol = 75
        self.player.set_volume(75)
        await interaction.response.defer()
        await self._update(interaction)
    
    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.success, custom_id="v:100", row=0)
    async def v100(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.vol = 100
        self.player.set_volume(100)
        await interaction.response.defer()
        await self._update(interaction)
    
    @discord.ui.button(emoji="➖", label="Lower", style=discord.ButtonStyle.secondary, custom_id="v:down", row=1)
    async def vdown(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.vol = max(0, self.vol - 10)
        self.player.set_volume(self.vol)
        await interaction.response.defer()
        await self._update(interaction)
    
    @discord.ui.button(emoji="➕", label="Raise", style=discord.ButtonStyle.secondary, custom_id="v:up", row=1)
    async def vup(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.vol = min(100, self.vol + 10)
        self.player.set_volume(self.vol)
        await interaction.response.defer()
        await self._update(interaction)


# Alias for backward compatibility
VolumeControlView = VolumeModal
