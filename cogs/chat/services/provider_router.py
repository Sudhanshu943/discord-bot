"""Provider routing for AI service selection."""

import logging
import time
from typing import Tuple, Optional

from ..models.chat import ProviderType

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
        self.groq_model = "llama-3.3-70b-versatile"
        self.groq_fallback_models = []
        
        # Get Groq API key and config from config.providers
        groq_key = None
        for provider in config.providers:
            if provider.name.startswith("groq"):
                groq_key = provider.api_key
                self.groq_model = provider.model or "llama-3.3-70b-versatile"
                # Get fallback models from provider config
                if hasattr(provider, 'fallback_models') and provider.fallback_models:
                    self.groq_fallback_models = provider.fallback_models
                logger.info(f"✅ Groq primary model: {self.groq_model}")
                logger.info(f"✅ Groq fallback models: {self.groq_fallback_models}")
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
        temperature: float = 0.7,
        personality = None
    ) -> Tuple[str, ProviderType]:
        """
        Route request to appropriate provider with automatic fallback on rate limits.
        
        Args:
            message: User message
            context: Conversation context
            max_tokens: Maximum tokens in response
            temperature: Response temperature
            personality: PersonalityConfig object (optional)
            
        Returns:
            Tuple of (response_text, provider_used)
            
        Raises:
            ValueError: If request validation fails
            Exception: If provider request fails
        """
        if not self.groq_client:
            raise Exception("Groq provider not initialized. Ensure GROQ_API_KEY is set.")
        
        # Build system prompt with personality
        system_prompt = self._build_system_prompt(personality)
        
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
        
        # Try primary model first, then fallback models on rate limit
        models_to_try = [self.groq_model] + self.groq_fallback_models
        
        for attempt, model in enumerate(models_to_try):
            try:
                logger.info(f"🔄 Trying Groq model: {model} (attempt {attempt + 1}/{len(models_to_try)})")
                
                start_time = time.time()
                
                # Call Groq API
                response = await self.groq_client.chat.completions.create(
                    model=model,
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
                
                logger.info(f"✅ Groq {model} response ({response_time:.2f}s): {len(redacted_response)} chars")
                
                return redacted_response, ProviderType.GROQ
                
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a 429 rate limit error
                if "429" in error_str or "rate_limit_exceeded" in error_str or "rate limit" in error_str.lower():
                    logger.warning(f"⚠️ Rate limit hit on {model}, trying fallback...")
                    
                    # If this is the last model, raise the error
                    if attempt == len(models_to_try) - 1:
                        logger.error(f"❌ All models exhausted due to rate limits. Last error: {e}")
                        raise
                    # Otherwise, continue to next model
                    continue
                
                # Check if it's a 400 decommissioned model error
                elif "400" in error_str or "decommissioned" in error_str.lower() or "model_decommissioned" in error_str:
                    logger.warning(f"⚠️ Model {model} has been decommissioned, trying fallback...")
                    
                    # If this is the last model, raise the error
                    if attempt == len(models_to_try) - 1:
                        logger.error(f"❌ All models exhausted or decommissioned. Last error: {e}")
                        raise
                    # Otherwise, continue to next model
                    continue
                
                else:
                    # Non-recoverable error, stop trying
                    logger.error(f"❌ Groq API error on {model}: {e}")
                    raise
    
    def _build_system_prompt(self, personality = None) -> str:
        """Build system prompt from personality or config.
        
        Args:
            personality: PersonalityConfig object (optional)
            
        Returns:
            System prompt string
        """
        # Use provided personality
        if personality and hasattr(personality, 'system_prompt'):
            return personality.system_prompt
        
        # Try to use config personality system
        if hasattr(self.config, 'personalities') and self.config.personalities:
            # Get default personality
            default_personality = self.config.personalities.get(self.config.default_personality)
            if default_personality:
                return default_personality.system_prompt
        
        # Try to use config system prompt (legacy)
        if hasattr(self.config, 'system_prompt') and self.config.system_prompt:
            return self.config.system_prompt
        
        # Fallback
        return "You are a helpful Discord bot assistant. Be concise and friendly."
    
    def get_preferred_provider(self) -> ProviderType:
        """Get the preferred provider (always Groq for now)."""
        return ProviderType.GROQ
