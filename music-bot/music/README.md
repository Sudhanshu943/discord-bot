# Music Bot Module

A modular, reliable music system for Discord bots using yt-dlp.

**No Lavalink required!** This module uses yt-dlp directly for music playback.

## Features

### 🎵 Multi-Platform Support
- **YouTube** - Videos, playlists, search
- **Spotify** - Tracks, albums, playlists
- **SoundCloud** - Tracks and sets
- **1000+ other sites** - Twitch, Twitter, TikTok, etc.

### 🔍 Smart Search
- Search by song name
- Direct URL support
- Auto-detect platform from URLs

### 🎛️ Full Playback Control
- Play, pause, resume, skip, stop
- Queue management
- Volume control
- Loop functionality
- Shuffle and clear queue

### 🖥️ Rich UI
- Beautiful embeds with track info
- Interactive control buttons

### 🛡️ Reliability
- No external server needed
- No Lavalink connection issues
- Works directly with yt-dlp

## Architecture

```
cogs/music/
├── __init__.py          # Package exports
├── music.py             # Main cog with commands
├── ui.py                # UI components (embeds, views)
├── exceptions.py        # Custom exceptions
└── logic/
    ├── __init__.py
    ├── player_manager.py    # Player management
    ├── track_handler.py     # Track operations
    └── search_manager.py    # Multi-platform search
```

## Commands

### Connection Commands
| Command | Description |
|---------|-------------|
| `/join` | Join your voice channel |
| `/leave` | Leave the voice channel |

### Playback Commands
| Command | Description |
|---------|-------------|
| `/play <query>` | Play a song from any platform |
| `/pause` | Pause playback |
| `/resume` | Resume playback |
| `/skip` | Skip current track |
| `/stop` | Stop and clear queue |

### Queue Commands
| Command | Description |
|---------|-------------|
| `/queue` | View the queue |
| `/nowplaying` | Show current track |
| `/remove <position>` | Remove track from queue |
| `/shuffle` | Shuffle the queue |
| `/clear` | Clear the queue |

### Other Commands
| Command | Description |
|---------|-------------|
| `/volume [level]` | Set or view volume (0-100) |
| `/loop` | Toggle loop |

## Setup

### 1. Install FFmpeg
FFmpeg is required for audio playback.

**Windows:**
```bash
winget install ffmpeg
```

Or download from: https://ffmpeg.org/download.html

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the Bot
```bash
python bot.py
```

**No Lavalink needed!** The bot works directly with yt-dlp.

## Requirements

- Python 3.8+
- FFmpeg (for audio playback)
- discord.py 2.3+
- yt-dlp

## Supported Platforms

yt-dlp supports 1000+ platforms including:
- YouTube
- Spotify
- SoundCloud
- Twitch
- Twitter/X
- TikTok
- Vimeo
- Bandcamp
- And many more!

## Troubleshooting

### Bot won't play music
- Make sure FFmpeg is installed and in PATH
- Check if the bot has voice permissions
- Try a different search term

### FFmpeg not found
- Install FFmpeg and add it to your system PATH
- On Windows: `winget install ffmpeg`

### No audio
- Check if the bot is connected to voice
- Make sure you're in the same voice channel
- Try adjusting volume with `/volume 50`

## License

This module is part of the Discord Multibot project.
