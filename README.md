# MultiBot

A feature-rich Discord bot with music playback, moderation tools, and server management capabilities.

## Features

### 🎵 Music
- **Ultra-fast playback** using yt-dlp (no Lavalink required)
- YouTube and YouTube Music support
- Play, pause, skip, queue management
- Volume control with interactive slider
- YouTube Mix playlists
- Background pre-loading for instant playback

### 🛡️ Moderation
- Kick members from the server
- Ban/unban members
- Role management (create/delete roles)

### 💬 Chat & Fun
- Magic 8ball command
- Hybrid commands (work as both `!command` and `/command`)

### ⚙️ General
- Slash commands support
- Comprehensive error handling
- File logging with rotation

## Requirements

- Python 3.10+
- FFmpeg (for audio playback)
- Discord bot token

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Sudhanshu943/discord-bot.git
   cd discord_multibot
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install FFmpeg**
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) or use `winget install ffmpeg`
   - **Linux**: `sudo apt install ffmpeg`
   - **Mac**: `brew install ffmpeg`

5. **Configure environment variables**
   ```bash
   # Create .env file with:
   DISCORD_TOKEN=your_bot_token_here
   ```

6. **Run the bot**
   ```bash
   python bot.py
   ```

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DISCORD_TOKEN` | Your Discord bot token |

### Bot Permissions

Invite the bot with these permissions:
- `Manage Roles`
- `Kick Members`
- `Ban Members`
- `Move Members` (for music)
- `Connect` (for music)
- `Speak` (for music)
- `Send Messages`
- `Use Slash Commands`

## Command Prefix

Default prefix: `!`

## Project Structure

```
discord_multibot/
├── bot.py              # Main entry point
├── requirements.txt    # Python dependencies
├── .env               # Environment variables (create this)
├── .gitignore         # Git ignore rules
├── cogs/              # Command modules
│   ├── chat.py       # Fun commands
│   ├── error_handler.py  # Error handling
│   ├── help.py       # Help command
│   ├── management.py # Role management
│   ├── moderation.py # Moderation commands
│   └── music/        # Music module
│       ├── music.py      # Main music cog
│       ├── ui.py         # UI components
│       ├── exceptions.py # Custom exceptions
│       └── logic/        # Core music logic
│           ├── player_manager.py
│           └── search_manager.py
├── data/              # Data storage
└── utils/             # Utility functions
```

## License

MIT License
