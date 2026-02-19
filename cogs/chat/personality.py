"""
Personality Module for AI Chat
===============================

Handles AI personality traits, user memory, and special command responses.
Includes Discord user permission checking and role hierarchy analysis.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
import logging
import discord

logger = logging.getLogger(__name__)


@dataclass
class UserMemory:
    """Stores information about a user."""
    user_id: int
    interests: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    last_conversation_topic: str = ""
    things_remembered: List[str] = field(default_factory=list)
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    message_count: int = 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserMemory':
        """Create from dictionary."""
        return cls(**data)
    
    def update_activity(self) -> None:
        """Update last seen timestamp."""
        self.last_seen = time.time()
        self.message_count += 1


class PersonalityManager:
    """
    Manages AI personality, user memory, and special responses.
    
    Features:
    - User memory (interests, preferences, things to remember)
    - Special command handling (help, who's online, remember, etc.)
    - Channel awareness (active users)
    """
    
    DEFAULT_MEMORY_PATH = "data/user_memory.json"
    
    def __init__(
        self,
        memory_path: str = None,
        bot: discord.Client = None
    ):
        """
        Initialize the personality manager.
        
        Args:
            memory_path: Path for user memory persistence
            bot: Discord bot instance for channel awareness
        """
        self.memory_path = memory_path or self.DEFAULT_MEMORY_PATH
        self.bot = bot
        
        # In-memory storage for user memories
        self._user_memories: Dict[int, UserMemory] = {}
        
        # Load persisted memories
        self._load_from_disk()
        
        logger.info("PersonalityManager initialized")
    
    def _load_from_disk(self) -> None:
        """Load user memories from disk."""
        try:
            path = Path(self.memory_path)
            
            if not path.exists():
                logger.debug("No memory file found, starting fresh")
                return
            
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._user_memories = {
                int(user_id): UserMemory.from_dict(mem_data)
                for user_id, mem_data in data.get("users", {}).items()
            }
            
            logger.info(f"Loaded memories for {len(self._user_memories)} users")
            
        except Exception as e:
            logger.error(f"Failed to load user memories: {e}")
    
    def _save_to_disk(self) -> None:
        """Save user memories to disk."""
        try:
            path = Path(self.memory_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "users": {
                    str(user_id): mem.to_dict()
                    for user_id, mem in self._user_memories.items()
                }
            }
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            logger.debug("User memories saved to disk")
            
        except Exception as e:
            logger.error(f"Failed to save user memories: {e}")
    
    def get_memory(self, user_id: int) -> UserMemory:
        """Get or create memory for a user."""
        if user_id not in self._user_memories:
            self._user_memories[user_id] = UserMemory(user_id=user_id)
        return self._user_memories[user_id]
    
    def remember(self, user_id: int, thing: str) -> None:
        """Store something in user's memory."""
        memory = self.get_memory(user_id)
        if thing not in memory.things_remembered:
            memory.things_remembered.append(thing)
            self._save_to_disk()
            logger.info(f"User {user_id} remembered: {thing}")
    
    def get_remembered(self, user_id: int) -> List[str]:
        """Get all remembered things for a user."""
        memory = self.get_memory(user_id)
        return memory.things_remembered.copy()
    
    def add_interest(self, user_id: int, interest: str) -> None:
        """Add an interest to user's profile."""
        memory = self.get_memory(user_id)
        interest_lower = interest.lower()
        if interest_lower not in [i.lower() for i in memory.interests]:
            memory.interests.append(interest)
            self._save_to_disk()
    
    def set_preference(self, user_id: int, key: str, value: Any) -> None:
        """Set a user preference."""
        memory = self.get_memory(user_id)
        memory.preferences[key] = value
        self._save_to_disk()
    
    def get_user_info(self, user_id: int) -> Dict:
        """Get all stored info about a user."""
        memory = self.get_memory(user_id)
        return {
            "interests": memory.interests,
            "preferences": memory.preferences,
            "things_remembered": memory.things_remembered,
            "last_topic": memory.last_conversation_topic,
            "message_count": memory.message_count,
            "first_seen": memory.first_seen,
            "last_seen": memory.last_seen
        }
    
    def update_activity(self, user_id: int) -> None:
        """Update user's last activity."""
        memory = self.get_memory(user_id)
        memory.update_activity()
    
    def set_topic(self, user_id: int, topic: str) -> None:
        """Set the current conversation topic for a user."""
        memory = self.get_memory(user_id)
        memory.last_conversation_topic = topic
    
    async def get_online_users(self, channel: discord.TextChannel) -> List[discord.Member]:
        """Get list of online members in a channel."""
        try:
            if not channel.guild:
                return []
            
            # Get members who have a role (usually means they're not idle/invisible)
            members = []
            async for member in channel.guild.fetch_members(limit=None):
                if member.status != discord.Status.offline:
                    # Check if they're in this specific channel
                    if any(vc.channel.id == channel.id for vc in self.bot.get_all_voice_states() 
                           if vc.member.id == member.id):
                        members.append(member)
                    elif member in channel.members:
                        members.append(member)
            
            return members
        except Exception as e:
            logger.error(f"Error getting online users: {e}")
            return []
    
    def format_help_response(self, user_name: str) -> str:
        """Format the help response."""
        return (
            f"Hey {user_name}. I'm here to respond with sarcasm and short answers. "
            f"Use `/ask` or `/chat`, or just mention me.\n\n"
            f"**Commands:**\n"
            f"• `who's online` - See active users (if anyone's actually here)\n"
            f"• `remember [something]` - I'll 'remember' that (no promises)\n"
            f"• `what do you know about me` - See if I bother to recall anything\n\n"
            f"Don't expect too much. 😉"
        )
    
    def format_whos_online_response(self, members: List[discord.Member], channel_name: str) -> str:
        """Format the who's online response."""
        if not members:
            return f"Crickets in #{channel_name}. No one's here but us bots."
        
        mentions = [f"<@{m.id}>" for m in members[:10]]  # Max 10 mentions
        others = len(members) - 10 if len(members) > 10 else 0
        
        response = f"Active in #{channel_name} (somehow): " + ", ".join(mentions)
        if others > 0:
            response += f" +{others} more losers"
        
        return response
    
    def format_remember_response(self, thing: str, user_name: str) -> str:
        """Format the remember confirmation response."""
        return f"Fine, {user_name}. I'll remember that {thing}. Don't expect me to care though."
    
    def format_what_know_response(self, user_id: int, user_name: str) -> str:
        """Format the 'what do you know about me' response."""
        info = self.get_user_info(user_id)
        
        response = f"Here's what I bother to remember about you, {user_name}:\n\n"
        
        if info["things_remembered"]:
            response += f"**Random stuff:**\n"
            for thing in info["things_remembered"]:
                response += f"• {thing}\n"
            response += "\n"
        
        if info["interests"]:
            response += f"**Your所谓 interests:** {', '.join(info['interests'])}\n\n"
        
        if info["preferences"]:
            response += f"**Your weird preferences:**\n"
            for key, value in info["preferences"].items():
                response += f"• {key}: {value}\n"
            response += "\n"
        
        if info["last_topic"]:
            response += f"**Last thing we talked about (that I cared about):** {info['last_topic']}\n\n"
        
        response += f"**Stats:** {info['message_count']} messages I've had to respond to"
        
        if not info["things_remembered"] and not info["interests"] and not info["preferences"]:
            response = (
                f"I don't know anything about you yet, {user_name}. "
                f"Not that I'm dying to learn. 😒"
            )
        
        return response
    
    def handle_special_command(self, user_id: int, message: str, 
                               user_name: str, channel = None) -> Optional[str]:
        """
        Check if message is a special command and return response if so.
        
        Returns response string if handled, None if not a special command.
        """
        msg_lower = message.lower().strip()
        
        # Help command
        if msg_lower in ["help", "what can you do", "what do you do"]:
            return self.format_help_response(user_name)
        
        # Who's online command
        if msg_lower in ["who's online", "who is online", "online users", "active users"]:
            # We'll handle this in the main chat handler since we need channel context
            return None  # Let main handler deal with it
        
        # Remember command
        if msg_lower.startswith("remember "):
            thing = message[9:].strip()  # Remove "remember " prefix
            if thing:
                self.remember(user_id, thing)
                return self.format_remember_response(thing, user_name)
        
        # What do you know about me
        if msg_lower in ["what do you know about me", "what do you know about me?", 
                         "tell me about me", "my info"]:
            return self.format_what_know_response(user_id, user_name)
        
        return None
    
    def can_user_mention(self, user: discord.Member, target: discord.Member, channel: discord.TextChannel) -> bool:
        """
        Check if a user can mention another user in a specific channel.
        
        In Discord, users can mention:
        - Everyone (if they have @everyone permission or are higher in role hierarchy)
        - Users with lower role hierarchy
        - Users in the same role
        
        Returns True if allowed, False if not allowed.
        """
        # Bot's perspective - check if the USER can mention the TARGET
        
        # Get the channel's permission overwrites
        try:
            # Check if target is mentionable (has a role that allows mentioning)
            if target.mentionable:
                return True
            
            # Check role hierarchy
            # User can mention if they are higher in role hierarchy than the target
            if user.top_role > target.top_role:
                return True
            
            # Check if user has administrator or mention everyone permission
            channel_perms = channel.permissions_for(user)
            if channel_perms.administrator or channel_perms.mention_everyone:
                return True
            
            # Check if they share a role
            user_roles = set(r.id for r in user.roles)
            target_roles = set(r.id for r in target.roles)
            if user_roles & target_roles:  # Intersection
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking mention permissions: {e}")
            return False
    
    async def get_user_details(self, user: discord.Member) -> Dict:
        """
        Get detailed information about a Discord user/member.
        
        Returns a dictionary with user details.
        """
        try:
            # Get guild info
            guild = user.guild
            
            # Calculate account age
            account_age = (discord.utils.utcnow() - user.created_at).days
            
            # Calculate server join age
            join_age = (discord.utils.utcnow() - user.joined_at).days if user.joined_at else 0
            
            # Get role info
            roles = [r.name for r in user.roles if r.name != '@everyone']
            top_role = user.top_role.name if user.top_role else "None"
            
            # Get permissions
            permissions = []
            guild_perms = user.guild_permissions
            important_perms = [
                ("administrator", guild_perms.administrator),
                ("manage_messages", guild_perms.manage_messages),
                ("manage_roles", guild_perms.manage_roles),
                ("manage_server", guild_perms.manage_guild),
                ("kick_members", guild_perms.kick_members),
                ("ban_members", guild_perms.ban_members),
                ("mention_everyone", guild_perms.mention_everyone),
            ]
            for perm_name, perm_value in important_perms:
                if perm_value:
                    permissions.append(perm_name)
            
            # Status
            status = str(user.status).capitalize()
            
            return {
                "id": user.id,
                "name": user.name,
                "display_name": user.display_name,
                "nickname": user.nick,
                "avatar_url": str(user.display_avatar.url),
                "account_created": f"{account_age} days ago",
                "joined_server": f"{join_age} days ago" if user.joined_at else "Unknown",
                "roles": roles,
                "top_role": top_role,
                "permissions": permissions,
                "status": status,
                "is_bot": user.bot,
            }
        except Exception as e:
            logger.error(f"Error getting user details: {e}")
            return {}
    
    def format_user_details(self, user: discord.Member, include_permissions: bool = True) -> str:
        """
        Format user details as a readable string.
        """
        try:
            details = []
            
            # Basic info
            display_name = user.display_name
            if user.nick and user.nick != user.name:
                display_name += f" (nick: {user.nick})"
            
            details.append(f"**{display_name}**")
            details.append(f"ID: `{user.id}`")
            
            # Account age
            account_age = (discord.utils.utcnow() - user.created_at).days
            details.append(f"Account age: {account_age} days")
            
            # Server join
            if user.joined_at:
                join_age = (discord.utils.utcnow() - user.joined_at).days
                details.append(f"Joined {join_age} days ago")
            
            # Roles
            roles = [r.name for r in user.roles if r.name != '@everyone']
            if roles:
                details.append(f"Roles: {', '.join(roles)}")
            else:
                details.append("Roles: None")
            
            # Status
            details.append(f"Status: {str(user.status).capitalize()}")
            
            # Bot?
            if user.bot:
                details.append("🤖 This is a bot")
            
            # Permissions
            if include_permissions:
                guild_perms = user.guild_permissions
                perms = []
                if guild_perms.administrator:
                    perms.append("Administrator")
                if guild_perms.manage_messages:
                    perms.append("Manage Messages")
                if guild_perms.manage_roles:
                    perms.append("Manage Roles")
                if guild_perms.manage_guild:
                    perms.append("Manage Server")
                if guild_perms.kick_members:
                    perms.append("Kick Members")
                if guild_perms.ban_members:
                    perms.append("Ban Members")
                if guild_perms.mention_everyone:
                    perms.append("Mention Everyone")
                
                if perms:
                    details.append(f"Key permissions: {', '.join(perms)}")
            
            return "\n".join(details)
            
        except Exception as e:
            logger.error(f"Error formatting user details: {e}")
            return "Could not get user details"
    
    def process_mentions(self, message: discord.Message) -> List[Dict]:
        """
        Process all mentions in a message and return details about them.
        
        Returns list of dicts with mention info and permission checks.
        """
        mentioned_info = []
        
        # Only process if in a guild
        if not isinstance(message.author, discord.Member):
            return mentioned_info
        
        channel = message.channel
        if not isinstance(channel, discord.TextChannel):
            return mentioned_info
        
        user = message.author
        
        # Process user mentions
        for member in message.mentions:
            if member.id == self.bot.user.id:
                continue  # Skip mentioning the bot itself
            
            can_mention = self.can_user_mention(user, member, channel)
            
            mentioned_info.append({
                "member": member,
                "name": member.display_name,
                "id": member.id,
                "can_mention": can_mention,
                "roles": [r.name for r in member.roles if r.name != '@everyone'],
                "top_role": member.top_role.name if member.top_role else "None",
                "mentionable": member.mentionable,
            })
        
        return mentioned_info


# Global personality manager instance
_personality_manager: Optional[PersonalityManager] = None


def get_personality_manager(bot: discord.Client = None) -> PersonalityManager:
    """Get or create the global personality manager."""
    global _personality_manager
    if _personality_manager is None:
        _personality_manager = PersonalityManager(bot=bot)
    return _personality_manager
