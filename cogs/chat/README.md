# Chat Module - Discord AI Chatbot System

A robust, scalable, and production-ready AI chatbot system for Discord bots.

## Features

### 🤖 Multiple LLM Provider Support
- **Groq** - Fast inference with Llama and Mixtral models
- **Google Gemini** - Google's advanced language model
- **OpenAI** - GPT-3.5 and GPT-4 models
- Automatic fallback between providers
- Multiple API keys per provider for load balancing

### 💬 Conversation Management
- Per-user conversation history
- Configurable history length
- Automatic conversation timeout
- Persistent storage (survives restarts)
- Context retention for natural conversations

### ⚡ Rate Limiting
- Per-user cooldown
- Global rate limiting
- Configurable limits
- Automatic cleanup of old entries

### 🛡️ Error Handling
- Comprehensive exception handling
- Graceful fallback on provider failures
- Health tracking for providers
- Detailed logging

### 📊 Statistics & Monitoring
- Usage statistics
- Provider health monitoring
- Per-user statistics
- Admin commands for management

## Installation

1. Ensure you have the required dependencies:
```bash
pip install discord.py aiohttp
```

2. Add your API keys to the `.env` file:
```env
GROQ_API_KEY_1=your_groq_key
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
```

3. Configure the chatbot in `config/chat_config.ini`

## Usage

### Commands

| Command | Description |
|---------|-------------|
| `/ask <question>` | Ask the AI a question |
| `/chat <message>` | Chat with the AI (alias for /ask) |
| `/clear` | Clear your conversation history |
| `/setprovider <provider>` | Set your preferred AI provider |
| `/providers` | List available AI providers |
| `/chatstats` | View global chat statistics |
| `/mystats` | View your personal statistics |

### Natural Conversation

You can also chat naturally by:
- **Mentioning the bot**: `@BotName hello!`
- **Replying to the bot's messages**

### Admin Commands

| Command | Description |
|---------|-------------|
| `/chatadmin reload` | Reload configuration |
| `/chatadmin resetuser <user_id>` | Reset a user's data |
| `/chatadmin resetall` | Reset all data |
| `/chatadmin cleanup` | Force cleanup of expired conversations |

## Configuration

### General Settings (`config/chat_config.ini`)

```ini
[general]
# System prompt for the AI
system_prompt = You are a helpful Discord bot assistant.

# Maximum messages to remember per user
max_history = 20

# Hours before conversation expires
conversation_timeout_hours = 24

# Save conversations to disk
persist_conversations = true
```

### Rate Limiting

```ini
[rate_limiting]
# Seconds between user messages
user_cooldown = 3

# Max requests per minute globally
global_requests_per_minute = 30

# Request timeout in seconds
request_timeout = 30
```

### Provider Priority

```ini
[providers]
# Order of providers to try
priority = groq, gemini, openai

# Enable/disable providers
groq_enabled = true
gemini_enabled = true
openai_enabled = true
```

## Architecture

```
cogs/chat/
├── __init__.py      # Module exports
├── chat.py          # Main Discord cog
├── config.py        # Configuration management
├── context.py       # Conversation context manager
├── exceptions.py    # Custom exceptions
├── providers.py     # LLM provider abstraction
├── rate_limiter.py  # Rate limiting system
└── README.md        # This file
```

### Key Components

#### `ChatConfig`
Loads and manages configuration from INI files and environment variables.

#### `ConversationManager`
Handles per-user conversation history with persistence support.

#### `RateLimiter`
Implements user cooldowns and global rate limiting.

#### `LLMProviderManager`
Manages multiple LLM providers with automatic fallback and health tracking.

#### `AIChat`
The main Discord cog that ties everything together.

## API Reference

### Exceptions

```python
from cogs.chat.exceptions import (
    ChatException,       # Base exception
    ProviderException,   # Provider-specific errors
    RateLimitException,  # Rate limit exceeded
    ConfigurationException,  # Config errors
    TimeoutException,    # Request timeout
    AuthenticationException  # API auth failures
)
```

### Example Usage

```python
from cogs.chat import AIChat

# In your bot setup
await bot.add_cog(AIChat(bot))
```

## Best Practices

1. **API Keys**: Use multiple API keys for load balancing and redundancy
2. **Rate Limiting**: Configure appropriate cooldowns to avoid API abuse
3. **Persistence**: Enable conversation persistence for better user experience
4. **Monitoring**: Use `/chatstats` to monitor usage and provider health
5. **Logging**: Set appropriate log levels in configuration

## Troubleshooting

### Bot not responding to messages
- Check if API keys are valid
- Verify rate limits aren't exceeded
- Check bot logs for errors

### Provider errors
- Use `/providers` to check provider health
- Check API key validity
- Review logs for specific error messages

### High memory usage
- Reduce `max_history` in configuration
- Lower `conversation_timeout_hours`
- Run `/chatadmin cleanup` to clear old conversations

## License

This module is part of the Discord Multibot project.
