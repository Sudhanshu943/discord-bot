"""
Cogs Package - Discord Bot Feature Modules
=========================================

This package contains all the bot's features organized as independent cogs.
Each cog is a self-contained module with its own:
- Commands layer (cog.py)
- Business logic layer
- Configuration layer
- Exceptions layer

Available Cogs:
- chat: AI chat functionality with multiple LLM providers
- music: Music playback system with multi-platform support
- error_handler: Error handling and exception management
- help: Help commands and documentation
- management: Bot and server management commands
- moderation: Server moderation commands
- welcomer: Member welcome and farewell messages
"""

__all__ = [
    'chat',
    'music',
    'error_handler',
    'help', 
    'management',
    'moderation',
    'welcomer'
]

__version__ = '2.0.0'
