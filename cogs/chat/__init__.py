"""
Chat Module - Robust and Scalable Discord Chatbot System
========================================================

This module provides a production-ready chatbot system with:
- Multiple LLM provider support (Groq, Gemini, OpenAI)
- Conversation context management with persistence
- Rate limiting and cooldown systems
- Comprehensive error handling and logging
- Modular and extensible architecture
"""

from .cog import AIChat, setup
from .rate_limiter import RateLimiter
from .config import ChatConfig
from .exceptions import (
    ChatException,
    ProviderException,
    RateLimitException,
    ConfigurationException
)

__all__ = [
    'AIChat',
    'setup',
    'RateLimiter',
    'ChatConfig',
    'ChatException',
    'ProviderException',
    'RateLimitException',
    'ConfigurationException'
]

__version__ = '2.0.0'
