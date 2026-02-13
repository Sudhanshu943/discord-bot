"""
LLM Provider Abstraction Layer for Chat Module
==============================================

Provides a unified interface for multiple LLM providers.
"""

import asyncio
import aiohttp
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging
import time

from .config import ProviderConfig
from .exceptions import (
    ProviderException,
    TimeoutException,
    AuthenticationException,
    ChatException
)

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    provider_name: str
    model: str
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None
    response_time: Optional[float] = None


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, config: ProviderConfig, timeout: float = 30.0):
        self.config = config
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def model(self) -> str:
        return self.config.model
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session
    
    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse object
        """
        pass
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class OpenAICompatibleProvider(BaseLLMProvider):
    """
    Provider for OpenAI-compatible APIs (OpenAI, Groq, etc.).
    """
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Generate response using OpenAI-compatible API."""
        logger.info(f"[{self.name}] 🔧 Preparing request...")
        start_time = time.time()
        session = await self._get_session()
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.config.model,
            "messages": messages,
            "temperature": kwargs.get('temperature', self.config.temperature),
            "max_tokens": kwargs.get('max_tokens', self.config.max_tokens)
        }
        
        # Add any additional parameters
        for key in ['top_p', 'presence_penalty', 'frequency_penalty', 'stop']:
            if key in kwargs:
                data[key] = kwargs[key]
        
        logger.info(f"[{self.name}] 📤 Sending POST to {self.config.url}")
        logger.info(f"[{self.name}] 📊 Model: {self.config.model}, Messages: {len(messages)}")
        
        try:
            async with session.post(
                self.config.url,
                headers=headers,
                json=data
            ) as response:
                logger.info(f"[{self.name}] 📥 Got response: HTTP {response.status}")
                response_time = time.time() - start_time
                
                if response.status == 200:
                    result = await response.json()
                    
                    content = result['choices'][0]['message']['content']
                    finish_reason = result['choices'][0].get('finish_reason')
                    
                    # Try to get token usage
                    tokens_used = None
                    if 'usage' in result:
                        tokens_used = result['usage'].get('total_tokens')
                    
                    logger.info(
                        f"[{self.name}] Response received in {response_time:.2f}s "
                        f"(tokens: {tokens_used})"
                    )
                    
                    return LLMResponse(
                        content=content,
                        provider_name=self.name,
                        model=self.config.model,
                        tokens_used=tokens_used,
                        finish_reason=finish_reason,
                        response_time=response_time
                    )
                
                elif response.status == 401:
                    raise AuthenticationException(self.name)
                
                elif response.status == 429:
                    # Rate limited
                    retry_after = response.headers.get('Retry-After', '60')
                    raise ProviderException(
                        self.name,
                        f"Rate limited. Retry after {retry_after}s"
                    )
                
                else:
                    error_text = await response.text()
                    raise ProviderException(
                        self.name,
                        f"API error (status {response.status}): {error_text[:200]}"
                    )
        
        except asyncio.TimeoutError:
            raise TimeoutException(self.name, self.timeout)
        
        except aiohttp.ClientError as e:
            raise ProviderException(
                self.name,
                f"Network error: {str(e)}",
                e
            )
    

class GeminiProvider(BaseLLMProvider):
    """
    Provider for Google Gemini API.
    """
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Generate response using Gemini API."""
        start_time = time.time()
        session = await self._get_session()
        
        # Convert messages to Gemini format
        # Gemini uses a different format than OpenAI
        contents = self._convert_messages_to_gemini(messages)
        
        url = f"{self.config.url}?key={self.config.api_key}"
        
        data = {
            "contents": contents,
            "generationConfig": {
                "temperature": kwargs.get('temperature', self.config.temperature),
                "maxOutputTokens": kwargs.get('max_tokens', self.config.max_tokens),
                "topP": kwargs.get('top_p', 0.95)
            }
        }
        
        try:
            logger.debug(f"[{self.name}] Sending request to Gemini API")
            
            async with session.post(url, json=data) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    result = await response.json()
                    
                    # Extract content from Gemini response
                    candidates = result.get('candidates', [])
                    if not candidates:
                        raise ProviderException(
                            self.name,
                            "No candidates in response"
                        )
                    
                    parts = candidates[0].get('content', {}).get('parts', [])
                    if not parts:
                        raise ProviderException(
                            self.name,
                            "No content parts in response"
                        )
                    
                    content = parts[0].get('text', '')
                    finish_reason = candidates[0].get('finishReason')
                    
                    # Token usage
                    tokens_used = None
                    if 'usageMetadata' in result:
                        tokens_used = result['usageMetadata'].get('totalTokenCount')
                    
                    logger.info(
                        f"[{self.name}] Response received in {response_time:.2f}s "
                        f"(tokens: {tokens_used})"
                    )
                    
                    return LLMResponse(
                        content=content,
                        provider_name=self.name,
                        model=self.config.model,
                        tokens_used=tokens_used,
                        finish_reason=finish_reason,
                        response_time=response_time
                    )
                
                elif response.status == 400:
                    error_text = await response.text()
                    raise ProviderException(
                        self.name,
                        f"Bad request: {error_text[:200]}"
                    )
                
                elif response.status == 403:
                    raise AuthenticationException(self.name)
                
                elif response.status == 429:
                    raise ProviderException(
                        self.name,
                        "Rate limited. Please try again later."
                    )
                
                else:
                    error_text = await response.text()
                    raise ProviderException(
                        self.name,
                        f"API error (status {response.status}): {error_text[:200]}"
                    )
        
        except asyncio.TimeoutError:
            raise TimeoutException(self.name, self.timeout)
        
        except aiohttp.ClientError as e:
            raise ProviderException(
                self.name,
                f"Network error: {str(e)}",
                e
            )
    
    def _convert_messages_to_gemini(self, messages: List[Dict[str, str]]) -> List[Dict]:
        """Convert OpenAI-style messages to Gemini format."""
        contents = []
        system_message = None
        
        for msg in messages:
            role = msg['role']
            content = msg['content']
            
            # Store system message to prepend to first user message
            if role == 'system':
                system_message = content
                continue
            
            # Map roles
            gemini_role = 'user' if role == 'user' else 'model'
            
            # Prepend system message to first user message
            if system_message and gemini_role == 'user' and not contents:
                content = f"{system_message}\n\n{content}"
                system_message = None  # Only prepend once
            
            contents.append({
                "role": gemini_role,
                "parts": [{"text": content}]
            })
        
        return contents



class LLMProviderManager:
    """
    Manages multiple LLM providers with fallback support.
    
    Features:
    - Automatic provider selection
    - Fallback to backup providers on failure
    - Load balancing across multiple keys
    - Health tracking
    """
    
    def __init__(self, providers: List[ProviderConfig], timeout: float = 30.0):
        """
        Initialize the provider manager.
        
        Args:
            providers: List of provider configurations
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._provider_order: List[str] = []
        self._health_status: Dict[str, Dict] = {}
        
        # Initialize providers
        for config in providers:
            if not config.is_valid():
                logger.warning(f"Skipping invalid provider config: {config.name}")
                continue
            
            provider = self._create_provider(config)
            self._providers[config.name] = provider
            self._provider_order.append(config.name)
            
            # Initialize health status
            self._health_status[config.name] = {
                "healthy": True,
                "consecutive_failures": 0,
                "total_requests": 0,
                "total_failures": 0,
                "last_failure": None,
                "avg_response_time": 0.0
            }
        
        logger.info(f"Initialized {len(self._providers)} providers: {self._provider_order}")
    
    def _create_provider(self, config: ProviderConfig) -> BaseLLMProvider:
        """Create appropriate provider instance based on config."""
        if 'gemini' in config.name.lower():
            return GeminiProvider(config, self.timeout)
        else:
            return OpenAICompatibleProvider(config, self.timeout)
    
    async def generate_with_fallback(
            self,
            messages: List[Dict[str, str]],
            preferred_provider: str = None,
            **kwargs
        ) -> Tuple[LLMResponse, str]:
        """Generate response with automatic fallback."""
        logger.info(f"🔍 Starting provider fallback (preferred: {preferred_provider})")
        logger.info(f"📝 Available providers: {self._provider_order}")

        # Determine provider order
        provider_order = list(self._provider_order)

        # Move preferred provider to front if specified
        if preferred_provider and preferred_provider in provider_order:
            provider_order.remove(preferred_provider)
            provider_order.insert(0, preferred_provider)

        # Filter out unhealthy providers (with too many consecutive failures)
        max_consecutive_failures = 3
        healthy_providers = [
            p for p in provider_order
            if self._health_status[p]["consecutive_failures"] < max_consecutive_failures
        ]

        logger.info(f"✅ Healthy providers: {healthy_providers}")

        if not healthy_providers:
            # Reset all health statuses and try again
            logger.warning("All providers unhealthy, resetting health status")
            for name in self._health_status:
                self._health_status[name]["consecutive_failures"] = 0
            healthy_providers = provider_order

        errors = []

        for provider_name in healthy_providers:
            provider = self._providers.get(provider_name)
            if not provider:
                logger.warning(f"❌ Provider {provider_name} not found in _providers dict")
                continue
            
            try:
                logger.info(f"⏳ Trying provider: {provider_name}")

                response = await provider.generate(messages, **kwargs)

                # Update health status - success
                self._record_success(provider_name, response.response_time)

                logger.info(f"✅ Provider {provider_name} succeeded!")
                return response, provider_name

            except (ProviderException, TimeoutException, AuthenticationException) as e:
                errors.append((provider_name, str(e)))
                self._record_failure(provider_name, str(e))
                logger.warning(f"❌ Provider {provider_name} failed: {e}")
                continue
            except Exception as e:
                logger.error(f"❌ Unexpected error with provider {provider_name}: {e}", exc_info=True)
                errors.append((provider_name, str(e)))
                continue
            
        # All providers failed
        error_summary = "; ".join([f"{p}: {e}" for p, e in errors])
        logger.error(f"❌ All providers failed! Errors: {error_summary}")
        raise ChatException(
            f"All providers failed. Errors: {error_summary}"
        )

    
    def _record_success(self, provider_name: str, response_time: float) -> None:
        """Record a successful request."""
        status = self._health_status[provider_name]
        status["healthy"] = True
        status["consecutive_failures"] = 0
        status["total_requests"] += 1
        
        # Update average response time
        if status["avg_response_time"] == 0:
            status["avg_response_time"] = response_time
        else:
            status["avg_response_time"] = (
                status["avg_response_time"] * 0.9 + response_time * 0.1
            )
    
    def _record_failure(self, provider_name: str, error: str) -> None:
        """Record a failed request."""
        status = self._health_status[provider_name]
        status["consecutive_failures"] += 1
        status["total_failures"] += 1
        status["total_requests"] += 1
        status["last_failure"] = error
        
        if status["consecutive_failures"] >= 3:
            status["healthy"] = False
    
    def get_provider_names(self) -> List[str]:
        """Get list of available provider names."""
        return list(self._provider_order)
    
    def get_health_status(self) -> Dict[str, Dict]:
        """Get health status of all providers."""
        return dict(self._health_status)
    
    def get_provider_stats(self, provider_name: str) -> Optional[Dict]:
        """Get statistics for a specific provider."""
        return self._health_status.get(provider_name)
    
    async def close_all(self) -> None:
        """Close all provider sessions."""
        for provider in self._providers.values():
            await provider.close()
        
        logger.info("All provider sessions closed")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_all()
