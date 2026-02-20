# Quick Reference: Personality System

## Commands

### /setpersonality
Show all available personalities and current channel personality.

```
/setpersonality
```

### /setpersonality <name>
Set the personality for the current channel.

```
/setpersonality aggressive
/setpersonality professional
/setpersonality friendly
```

## Configuration

Add to `config/chat_config.ini`:

```ini
# Define a personality
[personality.myname]
name = My Personality
system_prompt = Your system prompt here
tone = Optional tone
allowed_features = chat, memory

# Set as default
[personality.settings]
default_personality = myname

# Override specific channel
[personality.channel_overrides]
YOUR_CHANNEL_ID = myname
```

## Pre-Configured Personalities

### default
The original aggressive personality. System prompt uses the legacy setting.

### aggressive
Brutally honest, sarcastic, confrontational. Uses insults and personal attacks.

### professional
Formal, precise, respectful. Business-appropriate tone.

### friendly
Warm, helpful, casual, supportive. Encouraging and engaging.

### wise
Thoughtful, philosophical, introspective. Deep and meaningful responses.

## How It Works

1. When a message is received, the system checks:
   - Is there a channel override? → Use it
   - Is there a global default? → Use it
   - Otherwise → Use `default` personality

2. The personality's system prompt is injected into the AI request

3. The AI responds according to that personality

## Examples

### Set aggressive personality for support channel
```ini
[personality.channel_overrides]
1234567890123456789 = aggressive
```

### Set professional personality for work channel
```ini
[personality.channel_overrides]
9876543210987654321 = professional
```

### Create custom personality
```ini
[personality.helpful]
name = Helpful Assistant
system_prompt = You are incredibly helpful, never rude, always supportive. Provide detailed assistance.
tone = Helpful, patient, kind
allowed_features = chat, memory, search
```

## Logging

Check your bot logs for personality selection:

```
[Personality] Using: aggressive (channel override)
[Personality] Using: professional (override)
[Personality] Using: default (default)
```

## Files

- `config/chat_config.ini` - Configure personalities
- `config/chat_config.example.ini` - Examples and templates
- `cogs/chat/core/config.py` - Personality loading logic
- `cogs/chat/cogs/chat_cog.py` - /setpersonality command

## Troubleshooting

### Personality not found?
- Check spelling in configuration
- Run `/setpersonality` to see available personalities

### Channel override not working?
- Make sure channel ID is correct
- Restart bot (overrides are in-memory only)
- Check logs for `[Personality]` lines

### System prompts not changing?
- Verify personality is defined in config
- Check that system_prompt field has content
- Restart bot after config changes

### Want to persist overrides?
- Currently, overrides reset on bot restart
- To persist, edit `config/chat_config.ini` directly
- In future: persistent storage planned
