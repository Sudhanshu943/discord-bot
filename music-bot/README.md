# 🎵 Standalone Music Bot

A dedicated Discord bot for music playback using yt-dlp. No Lavalink required!

## Features

- ✅ **Ultra-fast playback** with pre-extraction
- ✅ **YouTube Music support** with fallback to regular YouTube
- ✅ **Multi-platform support** (YouTube, Spotify, SoundCloud, and 1000+ platforms)
- ✅ **Background pre-loading** for instant playback
- ✅ **Low latency optimizations** with FFmpeg
- ✅ **Opus codec preference** for best Discord audio quality
- ✅ **YouTube cookies support** for age-restricted content
- ✅ **Playlist support** with streaming loading
- ✅ **Volume control** with persistent settings
- ✅ **Loop mode** for continuous playback
- ✅ **Liked songs** storage per user
- ✅ **Anti-detection measures** to bypass YouTube bot detection
- ✅ **Automatic retry logic** with exponential backoff
- ✅ **User-agent rotation** for better compatibility

## Commands

### Music Playback
- `!play <song/url>` - Play a song or add to queue
- `!pause` - Pause current playback
- `!resume` - Resume playback
- `!skip` - Skip current song
- `!stop` - Stop playback and clear queue
- `!queue` - Show current queue
- `!nowplaying` - Show current song info

### Volume & Settings
- `!volume <0-100>` - Set playback volume
- `!loop` - Toggle loop mode
- `!shuffle` - Shuffle the queue

### Liked Songs
- `!like` - Add current song to liked songs
- `!liked` - Show your liked songs
- `!playliked` - Play your liked songs

### Utility
- `!musichelp` - Show available music commands
- `!join` - Join your voice channel
- `!leave` - Leave voice channel
- `!ping` - Check bot latency

## Setup

### Prerequisites
- Python 3.8 or higher
- FFmpeg installed and in PATH
- Discord Bot Token

### Installation

1. **Clone or copy this directory**
   ```bash
   cd music-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   - Edit `.env` file
   - Add your Discord bot token:
     ```
     DISCORD_TOKEN=your_bot_token_here
     ```

4. **Run the bot**
   ```bash
   python bot.py
   ```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DISCORD_TOKEN` | Your Discord bot token | Yes |
| `YOUTUBE_COOKIE_URL` | URL to YouTube cookies file | No |

### YouTube Cookies (Optional)

For age-restricted content or better YouTube Music support:

1. Export your YouTube cookies to a file
2. Upload the cookies file to a gist or web server
3. Set `YOUTUBE_COOKIE_URL` in `.env`

## Architecture

```
music-bot/
├── bot.py                 # Main bot entry point
├── requirements.txt       # Python dependencies
├── .env                  # Environment configuration
├── music/                # Music cog directory
│   ├── __init__.py       # Cog loader
│   ├── cog.py            # Main music commands
│   ├── ui.py             # UI components (embeds, views)
│   ├── exceptions.py     # Custom exceptions
│   └── logic/            # Core logic
│       ├── player_manager.py   # Player and queue management
│       ├── search_manager.py   # Multi-platform search
│       └── liked_songs.py      # Liked songs storage
└── playlists/            # User playlists storage
```

## Troubleshooting

### Voice Connection Issues

If you see "davey library needed in order to use voice":
```bash
pip install -r requirements.txt
```

The `discord.py[voice]` package includes all required voice dependencies.

### FFmpeg Not Found

Make sure FFmpeg is installed and in your system PATH:
- **Windows**: Download from https://ffmpeg.org/download.html
- **Linux**: `sudo apt install ffmpeg`
- **macOS**: `brew install ffmpeg`

### YouTube Extraction Errors

If YouTube extraction fails:
1. Update yt-dlp: `pip install --upgrade yt-dlp`
2. Configure YouTube cookies (see [COOKIE_SETUP.md](COOKIE_SETUP.md))
3. Check if the video is available in your region

### Bot Detection Issues

If you see "Sign in to confirm you're not a bot" or HTTP 429 errors:
1. **Set up YouTube cookies** - See [COOKIE_SETUP.md](COOKIE_SETUP.md) for detailed instructions
2. **Use a dedicated account** - Create a separate YouTube account for the bot
3. **Update cookies regularly** - Cookies expire after a few hours/days
4. **Check logs** - Review `music-bot.log` for detailed error messages

The bot includes built-in anti-detection measures:
- Automatic retry with exponential backoff (2s, 4s, 8s delays)
- User-agent rotation across multiple browsers
- Rate limiting to avoid triggering YouTube's limits
- Cookie auto-refresh every hour

## License

This project is part of the Discord Multi-Bot system.

## Support

For issues or questions, please refer to the main project documentation.
