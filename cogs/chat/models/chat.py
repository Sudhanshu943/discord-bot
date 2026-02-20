"""Chat request and response models."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class ProviderType(Enum):
    """Supported AI providers."""
    GROQ = "groq"


@dataclass
class ChatRequest:
    """Request to process a chat message."""
    
    user_id: int
    channel_id: int
    message: str
    guild_id: Optional[int] = None
    use_channel_memory: bool = True
    use_guild_memory: bool = True
    max_tokens: int = 1000
    temperature: float = 0.7
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    """Response from chat processing."""
    
    content: str
    provider: ProviderType
    tokens_used: int
    response_time: float
    model: str = "mixtral-8x7b-32768"
    conversation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
