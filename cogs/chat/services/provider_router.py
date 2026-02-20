"""Provider routing for AI service selection."""

import logging
import time
from typing import Tuple, Optional

from ..models.chat import ChatResponse, ProviderType

logger = logging.getLogger(__name__)


class ProviderRouter:
    """Routes requests to appropriate AI provider (currently Groq only)."""
    
    def __init__(self, config, safety_filter):
        """
        Initialize provider router.
        
        Args:
            config: ChatConfig object with provider settings
            safety_filter: SafetyFilter for output validation
        """
        self.config = config
        self.safety_filter = safety_filter
        self.groq_client = None
        self.groq_model = "mixtral-8x7b-32768"
        
        # Get Groq API key from config.providers
        groq_key = None
        for provider in config.providers:
            if provider.name.startswith("groq"):
                groq_key = provider.api_key
                self.groq_model = provider.model or "mixtral-8x7b-32768"
                break
        
        if not groq_key:
            logger.error("No Groq API key found in configuration")
            return
        
        try:
            from groq import AsyncGroq
            self.groq_client = AsyncGroq(api_key=groq_key)
        except ImportError:
            logger.error("Groq module not available - install with: pip install groq")
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
    
    async def route_request(
        self,
        message: str,
        context: str,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> Tuple[str, ProviderType]:
        """
        Route request to appropriate provider.
        
        Args:
            message: User message
            context: Conversation context
            max_tokens: Maximum tokens in response
            temperature: Response temperature
            
        Returns:
            Tuple of (response_text, provider_used)
            
        Raises:
            ValueError: If request validation fails
            Exception: If provider request fails
        """
        if not self.groq_client:
            raise Exception("Groq provider not initialized. Ensure GROQ_API_KEY is set.")
        
        # Build system prompt with personality
        system_prompt = self._build_system_prompt()
        
        # Build conversation context
        conversation_history = context
        
        # Prepare messages for API
        messages = []
        if conversation_history:
            messages.append({
                "role": "system",
                "content": f"{system_prompt}\n\nPrevious conversation:\n{conversation_history}"
            })
        else:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": message
        })
        
        try:
            start_time = time.time()
            
            # Call Groq API with configured model
            response = await self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=1.0,
            )
            
            response_text = response.choices[0].message.content
            response_time = time.time() - start_time
            
            # Redact secrets from response
            redacted_response, detected_secrets = await self.safety_filter.validate_ai_output(response_text)
            
            if detected_secrets:
                logger.warning(f"Groq response contained secrets: {detected_secrets}")
            
            logger.info(f"Groq response ({response_time:.2f}s): {len(redacted_response)} chars")
            
            return redacted_response, ProviderType.GROQ
            
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise
    
    def _build_system_prompt(self) -> str:
        """Build system prompt from config."""
        # Try to use personality manager if available
        if hasattr(self.config, 'personality') and self.config.personality:
            try:
                prompt = self.config.personality.get_system_prompt()
                if prompt:
                    return prompt
            except Exception as e:
                logger.warning(f"Failed to get personality prompt: {e}")
        
        # Use config system prompt
        if hasattr(self.config, 'system_prompt') and self.config.system_prompt:
            return self.config.system_prompt
        
        # Fallback
        return "You are a helpful Discord bot assistant. Be concise and friendly."
    
    def get_preferred_provider(self) -> ProviderType:
        """Get the preferred provider (always Groq for now)."""
        return ProviderType.GROQ
