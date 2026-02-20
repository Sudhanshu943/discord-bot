# AI Personality System Implementation

## Overview

This document describes the multi-personality system implementation for the Discord AI Chat bot. The system allows you to define multiple AI personalities with different system prompts, tones, and features, selectable globally or per-channel.

## Architecture

### Components

#### 1. **PersonalityConfig Dataclass** (`cogs/chat/core/config.py`)

```python
@dataclass
class PersonalityConfig:
    """Configuration for a single AI personality."""
    name: str
    system_prompt: str
    tone: Optional[str] = None
    allowed_features: List[str] = field(default_factory=list)
```

- **name**: Display name for the personality
- **system_prompt**: The actual system prompt injected into AI responses
- **tone**: Optional description of the personality's tone
- **allowed_features**: Optional list of enabled features (for future expansion)

#### 2. **Extended ChatConfig** (`cogs/chat/core/config.py`)

Added methods:
- `_load_personality_config()` - Parses all `[personality.*]` sections
- `get_personality(name)` - Retrieves a specific personality
- `get_channel_personality(channel_id)` - Gets personality for a channel (with priority logic)
- `set_channel_personality(channel_id, personality_name)` - Sets channel override
- `get_all_personality_names()` - Lists all available personalities

Attributes:
- `personalities: Dict[str, PersonalityConfig]` - All loaded personalities
- `channel_personality_map: Dict[int, str]` - Channel-to-personality mappings
- `default_personality: str` - Default personality name

#### 3. **Updated ChatService** (`cogs/chat/services/chat_service.py`)

The `process_message()` method now:
1. Determines the selected personality based on channel
2. Logs the personality being used
3. Passes the personality to the provider router

```python
selected_personality = self.config.get_channel_personality(channel_id)
logger.info(f"[Personality] Using: {selected_personality.name} for channel {channel_id}")
```

#### 4. **Updated ProviderRouter** (`cogs/chat/services/provider_router.py`)

- `route_request()` accepts optional `personality` parameter
- `_build_system_prompt()` uses the personality's system_prompt instead of hardcoded value

```python
def _build_system_prompt(self, personality=None) -> str:
    if personality and hasattr(personality, 'system_prompt'):
        return personality.system_prompt
    # ... fallback logic ...
```

#### 5. **New Command: /setpersonality** (`cogs/chat/cogs/chat_cog.py`)

Slash command to manage channel personalities:

```
/setpersonality              - Shows all available personalities
/setpersonality <name>       - Sets personality for current channel
```

Features:
- Validates personality exists before setting
- Shows current personality and personality details
- Channel-specific override (doesn't affect other channels)
- Embeds for clean Discord UI

## Configuration

### Priority Order

When determining which personality to use:

1. **Channel Override** - If set in `[personality.channel_overrides]`
2. **Global Default** - From `[personality.settings] default_personality`
3. **Fallback** - The `default` personality (always present)

### Configuration Structure

```ini
# Define personalities
[personality.NAME]
name = Display Name
system_prompt = The actual system prompt used by the AI
tone = Optional tone description
allowed_features = feature1, feature2, feature3

# Configure defaults
[personality.settings]
default_personality = default

# Set per-channel overrides
[personality.channel_overrides]
CHANNEL_ID = personality_name
```

### Example Configuration

```ini
[personality.default]
name = Default
system_prompt = You are a helpful and balanced AI assistant...
tone = Neutral and helpful
allowed_features = chat, memory

[personality.aggressive]
name = Aggressive
system_prompt = You are brutally honest, sarcastic and confrontational...
tone = Aggressive, sarcastic
allowed_features = chat, memory

[personality.professional]
name = Professional
system_prompt = You respond formally, precisely, and concisely...
tone = Formal, professional
allowed_features = chat, memory, search

[personality.settings]
default_personality = default

[personality.channel_overrides]
1471996064054644930 = aggressive
1471953374772461568 = professional
```

## Usage

### For Users

1. **List personalities**: Use `/setpersonality` (no arguments)
   - Shows all available personalities
   - Shows current personality for the channel

2. **Change personality**: Use `/setpersonality aggressive`
   - Sets the personality for the current channel only
   - Shows confirmation with personality details

### For Administrators

1. **Define personalities** in `config/chat_config.ini`
   - Add `[personality.yourname]` section
   - Define `name`, `system_prompt`, and optional `tone`/`allowed_features`

2. **Set global default**:
   ```ini
   [personality.settings]
   default_personality = yourname
   ```

3. **Set channel overrides**:
   ```ini
   [personality.channel_overrides]
   YOUR_CHANNEL_ID = yourname
   ```

## Key Features

### ✅ Backward Compatibility
- If no personality system is configured, uses legacy `[general] system_prompt`
- Automatically creates a `default` personality from legacy setting
- Existing bots continue working without changes

### ✅ Clean Architecture
- Logic isolated in config layer and services
- ChatCog only triggers personality selection
- No hardcoded personalities or system prompts
- All configuration via INI file

### ✅ Logging
- Every message logs which personality is being used
- Format: `[Personality] Using: <name> for channel <id>`
- Channel-specific overrides clearly indicated

### ✅ Per-Channel Isolation
- Each channel can have its own personality
- Overrides are stored in memory (in-memory only)
- No persistence of overrides (reset on bot restart)

### ✅ Complete Personality Details
- Name and system_prompt (required)
- Tone (optional - for documentation)
- Allowed features (optional - for future expansion)

## File Changes

### Modified Files

1. **[cogs/chat/core/config.py](cogs/chat/core/config.py)**
   - Added `PersonalityConfig` dataclass
   - Added personality loading methods
   - Added personality management methods

2. **[cogs/chat/services/chat_service.py](cogs/chat/services/chat_service.py)**
   - Personality selection logic in `process_message()`
   - Pass personality to provider router

3. **[cogs/chat/services/provider_router.py](cogs/chat/services/provider_router.py)**
   - Accept personality parameter in `route_request()`
   - Use personality's system_prompt in `_build_system_prompt()`

4. **[cogs/chat/cogs/chat_cog.py](cogs/chat/cogs/chat_cog.py)**
   - New `/setpersonality` command
   - Updated `/chathelp` to include personality info

5. **[config/chat_config.ini](config/chat_config.ini)**
   - Added personality definitions (default, aggressive, professional, friendly, wise)
   - Added personality settings and channel overrides sections

6. **[config/chat_config.example.ini](config/chat_config.example.ini)**
   - Updated with complete personality system examples
   - Comprehensive documentation and examples

## Future Enhancements

1. **Persistent Channel Overrides**
   - Store overrides in JSON file or database
   - Survive bot restarts

2. **User-Level Personalities**
   - Store per-user personality preferences
   - Override channel and global defaults

3. **Dynamic Personality Creation**
   - Commands to create/edit personalities at runtime
   - Save to config file or database

4. **Personality Inheritance**
   - Create personalities based on other personalities
   - Override only specific aspects

5. **Feature-Based Access Control**
   - Use `allowed_features` to enable/disable specific features per personality

6. **Personality Metrics**
   - Track which personalities are used most
   - Analyze personality popularity

## Logging Examples

When a message is processed, you'll see logs like:

```
[Personality] Using: aggressive (channel override)
[Personality] Using: default (default)
[Personality] Channel 123456789012345678: professional (override)
Loaded 6 personality configurations
```

## Migration Guide

### For Existing Bots

No changes required! The system:
1. Reads your existing `[general] system_prompt`
2. Automatically creates a `default` personality from it
3. Uses that as the fallback

### To Enable Full System

1. Copy new `chat_config.example.ini` personalities to your `chat_config.ini`
2. Customize system prompts as needed
3. Set your preferred default personality
4. Add any channel overrides you want
5. Restart the bot

The system will automatically load all configured personalities.

## Testing

```python
# Test personality loading
config = ChatConfig()
assert 'default' in config.personalities
assert 'aggressive' in config.personalities

# Test channel personality selection
personality = config.get_channel_personality(123456789012345678)
assert personality.name == "Default"

# Test channel override
config.set_channel_personality(123456789012345678, 'aggressive')
personality = config.get_channel_personality(123456789012345678)
assert personality.name == "Aggressive"
```

## No Breaking Changes

✅ All existing features continue to work unchanged
✅ Music integration unaffected
✅ Memory system unaffected
✅ Rate limiting unaffected
✅ Provider routing unaffected
✅ Commands unaffected

The personality system is entirely backward compatible and additive.
