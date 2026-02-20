"""Main chat service orchestrating all layers."""

import logging
from typing import Tuple, Optional

from ..models.chat import ProviderType
from .memory_manager import MemoryManager
from .provider_router import ProviderRouter
from .safety_filter import SafetyFilter

logger = logging.getLogger(__name__)


class ChatService:
    """Main service orchestrating chat processing."""
    
    def __init__(
        self,
        config,
        memory_manager: MemoryManager,
        safety_filter: SafetyFilter,
        provider_router: ProviderRouter
    ):
        """
        Initialize chat service.
        
        Args:
            config: ChatConfig object
            memory_manager: Memory management service
            safety_filter: Safety/validation service
            provider_router: Provider routing service
        """
        self.config = config
        self.memory_manager = memory_manager
        self.safety_filter = safety_filter
        self.provider_router = provider_router
    
    async def process_message(
        self,
        user_id: int,
        channel_id: int,
        message: str,
        guild_id: Optional[int] = None,
        use_channel_memory: bool = True,
        use_guild_memory: bool = True,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> Tuple[str, ProviderType]:
        """
        Process a user message end-to-end.
        
        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
            message: User message text
            guild_id: Discord guild ID (optional)
            use_channel_memory: Include channel context
            use_guild_memory: Include guild context
            max_tokens: Max response tokens
            temperature: Response temperature
            
        Returns:
            Tuple of (response_text, provider_used)
            
        Raises:
            ValueError: If validation fails
        """
        # Step 0: Determine personality for this channel
        selected_personality = self.config.get_channel_personality(channel_id)
        logger.info(f"[Personality] Using: {selected_personality.name} for channel {channel_id}")
        
        # Step 1: Validate user input
        valid, error = await self.safety_filter.validate_user_input(message)
        if not valid:
            raise ValueError(error or "Invalid input")
        
        # Step 2: Build conversation context
        context_parts = []
        
        # Add channel context
        if use_channel_memory and channel_id:
            channel_context = await self.memory_manager.get_channel_context(channel_id, limit=10)
            if channel_context:
                context_parts.append(f"Channel history:\n{channel_context}")
        
        # Add guild context
        if use_guild_memory and guild_id:
            guild_context = await self.memory_manager.get_guild_context(guild_id, limit=5)
            if guild_context:
                context_parts.append(f"Guild history:\n{guild_context}")
        
        context = "\n\n".join(context_parts)
        
        # Validate context length
        valid, error = self.safety_filter.validate_context_length(context)
        if not valid:
            # Trim context if needed
            logger.warning(f"Context too long, trimming: {error}")
            context = context[:self.safety_filter.max_context_length]
        
        # Step 3: Route to provider with selected personality
        try:
            response_text, provider = await self.provider_router.route_request(
                message=message,
                context=context,
                max_tokens=max_tokens,
                temperature=temperature,
                personality=selected_personality
            )
        except Exception as e:
            logger.error(f"Provider error: {e}")
            raise
        
        # Step 4: Save to memory (async, non-blocking)
        try:
            # Save user message
            if use_channel_memory:
                await self.memory_manager.add_to_channel_memory(
                    channel_id, "user", message, user_id
                )
            
            if use_guild_memory and guild_id:
                await self.memory_manager.add_to_guild_memory(
                    guild_id, "user", message, user_id
                )
            
            # Save AI response
            if use_channel_memory:
                await self.memory_manager.add_to_channel_memory(
                    channel_id, "assistant", response_text
                )
            
            if use_guild_memory and guild_id:
                await self.memory_manager.add_to_guild_memory(
                    guild_id, "assistant", response_text
                )
        except Exception as e:
            logger.error(f"Failed to save to memory: {e}")
            # Don't fail the request just because memory save failed
        
        return response_text, provider
    
    async def clear_channel_context(self, channel_id: int) -> None:
        """Clear conversation memory for a channel."""
        await self.memory_manager.clear_channel_memory(channel_id)
        logger.info(f"Cleared memory for channel {channel_id}")
    
    async def clear_guild_context(self, guild_id: int) -> None:
        """Clear conversation memory for a guild."""
        await self.memory_manager.clear_guild_memory(guild_id)
        logger.info(f"Cleared memory for guild {guild_id}")
    
    async def get_channel_stats(self, channel_id: int) -> dict:
        """Get statistics for a channel."""
        memory = await self.memory_manager.get_or_create_channel_memory(channel_id)
        return {
            "channel_id": channel_id,
            "message_count": memory.total_messages,
            "token_count": memory.total_tokens,
            "created_at": memory.created_at,
            "last_updated": memory.last_updated,
        }
    
    async def get_guild_stats(self, guild_id: int) -> dict:
        """Get statistics for a guild."""
        memory = await self.memory_manager.get_or_create_guild_memory(guild_id)
        return {
            "guild_id": guild_id,
            "message_count": memory.total_messages,
            "token_count": memory.total_tokens,
            "created_at": memory.created_at,
            "last_updated": memory.last_updated,
        }
