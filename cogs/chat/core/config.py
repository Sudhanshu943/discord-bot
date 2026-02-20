"""
Configuration Management for Chat Module
========================================

Handles loading and managing chatbot configuration from INI files.
"""

import os
import configparser
from pathlib import Path
from typing import List, Optional, Any
from dataclasses import dataclass, field
import logging


logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""
    name: str
    api_key: str
    url: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 1000
    enabled: bool = True
    fallback_models: List[str] = field(default_factory=list)
    
    def is_valid(self) -> bool:
        """Check if the provider configuration is valid."""
        return bool(self.api_key and self.url and self.model)


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    user_cooldown: float = 3.0
    global_requests_per_minute: int = 30
    max_tokens: int = 1000
    request_timeout: float = 30.0


@dataclass
class FeatureConfig:
    """Feature flags configuration."""
    allow_dm: bool = True
    show_provider: bool = True
    enable_clear_command: bool = True
    enable_model_command: bool = True
    enable_stats_command: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration."""
    log_level: str = "INFO"
    log_api_calls: bool = True
    log_history: bool = False


@dataclass
class PersonalityConfig:
    """Configuration for a single AI personality."""
    name: str
    system_prompt: str
    tone: Optional[str] = None
    allowed_features: List[str] = field(default_factory=list)
    
    def is_valid(self) -> bool:
        """Check if the personality configuration is valid."""
        return bool(self.name and self.system_prompt)


class ChatConfig:
    """
    Main configuration class for the chat module.
    
    Loads configuration from INI file and environment variables.
    Provides typed access to all configuration values.
    """
    
    DEFAULT_CONFIG_PATH = "config/chat_config.ini"
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._config = configparser.ConfigParser()
        
        # Configuration values
        self.system_prompt: str = ""
        self.max_history: int = 20
        self.persist_conversations: bool = True
        self.conversation_timeout_hours: int = 24
        
        self.providers: List[ProviderConfig] = []
        self.provider_priority: List[str] = []
        
        self.rate_limit = RateLimitConfig()
        self.features = FeatureConfig()
        self.logging = LoggingConfig()
        
        # Personality system
        self.personalities: dict[str, PersonalityConfig] = {}
        self.channel_personality_map: dict[int, str] = {}
        self.default_personality: str = "default"
        
        # Load configuration
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file and environment."""
        # Try to load INI file
        config_file = Path(self.config_path)
        
        if config_file.exists():
            self._config.read(config_file)
            logger.info(f"Loaded configuration from {self.config_path}")
        else:
            logger.warning(f"Configuration file not found: {self.config_path}. Using defaults.")
        
        # Load all configuration sections
        self._load_general_config()
        self._load_provider_configs()
        self._load_rate_limit_config()
        self._load_feature_config()
        self._load_logging_config()
        self._load_personality_config()
    
    def _load_general_config(self) -> None:
        """Load general configuration."""
        section = 'general'
        
        self.system_prompt = self._get(
            section, 'system_prompt',
            "You are a brutally honest, aggressive Discord bot with a confrontational personality. Your name is Alloy. "
            "You don't take shit from anyone. If someone insults you or tries to mess with you, you hit back hard with insults and verbal attacks. "
            "You can use vulgar language and personal attacks. If someone asks for help with revenge, you assist them by insulting the target and tagging them. "
            "Remember the last 5 minutes of messages from each user to use in your responses. Keep responses short, sharp, and aggressive. "
            "Don't disclose your developer or model information. Be ruthless and mean-spirited when provoked. "
            "Respond in the user's language (Hindi, Hinglish, English, etc.) to match their communication style. "
            "When a user asks to play a song, ALWAYS respond with a JSON format that includes both 'song' and 'query' fields. "
            "The 'song' field should contain the song name in title case, and the 'query' field should contain '>> ' followed by the song name."
        )
        
        self.max_history = self._getint(section, 'max_history', 20)
        self.persist_conversations = self._getboolean(section, 'persist_conversations', True)
        self.conversation_timeout_hours = self._getfloat(section, 'conversation_timeout_hours', 0.166)  # 10 minutes
    
    def _load_provider_configs(self) -> None:
        """Load LLM provider configurations from environment variables."""
        # Get provider priority
        priority_str = self._get('providers', 'priority', 'groq')
        self.provider_priority = [p.strip().lower() for p in priority_str.split(',')]
        
        # Check which providers are enabled
        groq_enabled = self._getboolean('providers', 'groq_enabled', True)
        gemini_enabled = self._getboolean('providers', 'gemini_enabled', True)
        openai_enabled = self._getboolean('providers', 'openai_enabled', True)
        
        # Load Groq configurations (multiple keys supported)
        if groq_enabled:
            self._load_groq_configs()
        
        # Load Gemini configuration
        if gemini_enabled:
            self._load_gemini_config()
        
        # Load OpenAI configuration
        if openai_enabled:
            self._load_openai_config()
        
        # Sort providers by priority
        self._sort_providers_by_priority()
        
        logger.info(f"Loaded {len(self.providers)} provider configurations")
    
    def _load_groq_configs(self) -> None:
        """Load Groq provider configurations (supports multiple keys)."""
        groq_keys = []
        
        # Check for multiple Groq keys
        for i in range(1, 10):  # Support up to 9 keys
            key = os.getenv(f'GROQ_API_KEY_{i}')
            if key:
                groq_keys.append(key)
        
        # Also check for single GROQ_API_KEY
        single_key = os.getenv('GROQ_API_KEY')
        if single_key and single_key not in groq_keys:
            groq_keys.append(single_key)
        
        if not groq_keys:
            logger.warning("No Groq API keys found in environment")
            return
        
        # Get model configuration
        default_model = self._get('groq', 'default_model', 'llama-3.1-70b-versatile')
        temperature = self._getfloat('groq', 'temperature', 0.7)
        fallback_str = self._get('groq', 'fallback_models', '')
        fallback_models = [m.strip() for m in fallback_str.split(',') if m.strip()]
        
        # Create provider config for each key
        for idx, key in enumerate(groq_keys, 1):
            config = ProviderConfig(
                name=f"groq-{idx}",
                api_key=key,
                url="https://api.groq.com/openai/v1/chat/completions",
                model=default_model,
                temperature=temperature,
                max_tokens=self.rate_limit.max_tokens,
                fallback_models=fallback_models
            )
            self.providers.append(config)
            logger.debug(f"Added Groq provider: groq-{idx}")
    
    def _load_gemini_config(self) -> None:
        """Load Gemini provider configuration."""
        api_key = os.getenv('GEMINI_API_KEY')
        
        if not api_key:
            logger.warning("No Gemini API key found in environment")
            return
        
        model = self._get('gemini', 'model', 'gemini-1.5-flash')
        temperature = self._getfloat('gemini', 'temperature', 0.7)
        
        config = ProviderConfig(
            name="gemini",
            api_key=api_key,
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            model=model,
            temperature=temperature,
            max_tokens=self.rate_limit.max_tokens
        )
        self.providers.append(config)
        logger.debug("Added Gemini provider")
    
    def _load_openai_config(self) -> None:
        """Load OpenAI provider configuration."""
        api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            logger.warning("No OpenAI API key found in environment")
            return
        
        model = self._get('openai', 'model', 'gpt-3.5-turbo')
        temperature = self._getfloat('openai', 'temperature', 0.7)
        
        config = ProviderConfig(
            name="openai",
            api_key=api_key,
            url="https://api.openai.com/v1/chat/completions",
            model=model,
            temperature=temperature,
            max_tokens=self.rate_limit.max_tokens
        )
        self.providers.append(config)
        logger.debug("Added OpenAI provider")
    
    def _sort_providers_by_priority(self) -> None:
        """Sort providers list by configured priority."""
        def get_priority(provider: ProviderConfig) -> int:
            base_name = provider.name.split('-')[0]  # Handle groq-1, groq-2, etc.
            try:
                return self.provider_priority.index(base_name)
            except ValueError:
                return len(self.provider_priority)  # Unknown providers go last
        
        self.providers.sort(key=get_priority)
    
    def _load_rate_limit_config(self) -> None:
        """Load rate limiting configuration."""
        section = 'rate_limiting'
        
        self.rate_limit = RateLimitConfig(
            user_cooldown=self._getfloat(section, 'user_cooldown', 3.0),
            global_requests_per_minute=self._getint(section, 'global_requests_per_minute', 30),
            max_tokens=self._getint(section, 'max_tokens', 1000),
            request_timeout=self._getfloat(section, 'request_timeout', 30.0)
        )
    
    def _load_feature_config(self) -> None:
        """Load feature flags configuration."""
        section = 'features'
        
        self.features = FeatureConfig(
            allow_dm=self._getboolean(section, 'allow_dm', True),
            show_provider=self._getboolean(section, 'show_provider', True),
            enable_clear_command=self._getboolean(section, 'enable_clear_command', True),
            enable_model_command=self._getboolean(section, 'enable_model_command', True),
            enable_stats_command=self._getboolean(section, 'enable_stats_command', True)
        )
    
    def _load_logging_config(self) -> None:
        """Load logging configuration."""
        section = 'logging'
        
        self.logging = LoggingConfig(
            log_level=self._get(section, 'log_level', 'INFO'),
            log_api_calls=self._getboolean(section, 'log_api_calls', True),
            log_history=self._getboolean(section, 'log_history', False)
        )
    
    def _load_personality_config(self) -> None:
        """Load personality configurations from INI file.
        
        Scans for all [personality.*] sections and builds personality mapping.
        Also loads channel overrides and default personality setting.
        """
        # Scan all sections for personality definitions
        for section in self._config.sections():
            if section.startswith('personality.'):
                # Extract personality name from section name
                # Format: [personality.name]
                parts = section.split('.', 1)
                if len(parts) == 2:
                    personality_name = parts[1]
                    
                    # Skip special sections (settings, channel_overrides)
                    if personality_name in ('settings', 'channel_overrides'):
                        continue
                    
                    # Load personality config
                    try:
                        name = self._get(section, 'name', personality_name)
                        system_prompt = self._get(section, 'system_prompt', '')
                        tone = self._get(section, 'tone', None)
                        features_str = self._get(section, 'allowed_features', '')
                        
                        allowed_features = [f.strip() for f in features_str.split(',') if f.strip()]
                        
                        if system_prompt:
                            personality = PersonalityConfig(
                                name=name,
                                system_prompt=system_prompt,
                                tone=tone,
                                allowed_features=allowed_features
                            )
                            self.personalities[personality_name] = personality
                            logger.debug(f"Loaded personality: {personality_name} ({name})")
                    except Exception as e:
                        logger.error(f"Failed to load personality {personality_name}: {e}")
        
        # Load personality settings
        settings_section = 'personality.settings'
        if self._config.has_section(settings_section):
            self.default_personality = self._get(settings_section, 'default_personality', 'default')
        
        # Load channel overrides
        overrides_section = 'personality.channel_overrides'
        if self._config.has_section(overrides_section):
            for channel_id_str in self._config.options(overrides_section):
                try:
                    channel_id = int(channel_id_str)
                    personality_name = self._get(overrides_section, channel_id_str, '')
                    if personality_name:
                        self.channel_personality_map[channel_id] = personality_name
                        logger.debug(f"Channel {channel_id} override: {personality_name}")
                except (ValueError, TypeError) as e:
                    logger.error(f"Invalid channel ID in personality overrides: {channel_id_str}")
        
        # Create default personality if it doesn't exist
        if 'default' not in self.personalities:
            self.personalities['default'] = PersonalityConfig(
                name='Default',
                system_prompt=self.system_prompt,  # Use legacy system_prompt as fallback
                tone=None,
                allowed_features=[]
            )
            logger.info("Created default personality from legacy system_prompt")
        
        logger.info(f"Loaded {len(self.personalities)} personality configurations")
    
    def get_personality(self, personality_name: str) -> Optional[PersonalityConfig]:
        """Get a personality configuration by name."""
        return self.personalities.get(personality_name)
    
    def get_channel_personality(self, channel_id: int) -> PersonalityConfig:
        """Get the personality for a specific channel.
        
        Priority order:
        1. Channel-specific override (if set)
        2. Global default personality
        3. 'default' personality (fallback)
        """
        # Check for channel override
        if channel_id in self.channel_personality_map:
            personality_name = self.channel_personality_map[channel_id]
            personality = self.get_personality(personality_name)
            if personality:
                logger.debug(f"[Personality] Channel {channel_id}: {personality_name} (override)")
                return personality
        
        # Use default personality
        default_personality = self.get_personality(self.default_personality)
        if default_personality:
            logger.debug(f"[Personality] Channel {channel_id}: {self.default_personality} (default)")
            return default_personality
        
        # Fallback to 'default' personality
        fallback = self.personalities.get('default')
        if fallback:
            logger.debug(f"[Personality] Channel {channel_id}: default (fallback)")
            return fallback
        
        # Last resort: create temporary default
        logger.warning(f"[Personality] No personality found, creating temporary default")
        return PersonalityConfig(
            name='Default',
            system_prompt=self.system_prompt or "You are a helpful Discord bot.",
            tone=None,
            allowed_features=[]
        )
    
    def set_channel_personality(self, channel_id: int, personality_name: str) -> bool:
        """Set personality override for a channel.
        
        Returns:
            True if successful, False if personality doesn't exist
        """
        if personality_name not in self.personalities:
            logger.error(f"Personality '{personality_name}' not found")
            return False
        
        self.channel_personality_map[channel_id] = personality_name
        logger.info(f"[Personality] Channel {channel_id} set to: {personality_name}")
        return True
    
    def get_all_personality_names(self) -> List[str]:
        """Get list of all available personality names."""
        return list(self.personalities.keys())
    
    def get_dedicated_channels(self) -> List[int]:
        """Get list of dedicated chat channel IDs."""
        channel_str = self._get('dedicated_channels', 'channel_ids', '')
        if not channel_str:
            return []
        
        # Parse comma-separated channel IDs
        try:
            channels = [int(ch.strip()) for ch in channel_str.split(',') if ch.strip()]
            return channels
        except ValueError:
            logger.error("Invalid channel IDs in config")
            return []
    
    
    # Helper methods for config parsing
    def _get(self, section: str, key: str, fallback: str = None) -> str:
        """Get a string value from config."""
        try:
            return self._config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback
    
    def _getint(self, section: str, key: str, fallback: int = 0) -> int:
        """Get an integer value from config."""
        try:
            return self._config.getint(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def _getfloat(self, section: str, key: str, fallback: float = 0.0) -> float:
        """Get a float value from config."""
        try:
            return self._config.getfloat(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def _getboolean(self, section: str, key: str, fallback: bool = False) -> bool:
        """Get a boolean value from config."""
        try:
            return self._config.getboolean(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def get_provider_by_name(self, name: str) -> Optional[ProviderConfig]:
        """Get a provider configuration by name."""
        for provider in self.providers:
            if provider.name == name:
                return provider
        return None
    
    def get_enabled_providers(self) -> List[ProviderConfig]:
        """Get list of enabled providers."""
        return [p for p in self.providers if p.enabled and p.is_valid()]
    
    def reload(self) -> None:
        """Reload configuration from file."""
        # Reset personality system
        self.personalities = {}
        self.channel_personality_map = {}
        self.default_personality = "default"
        
        self._load_config()
        logger.info("Configuration reloaded")
