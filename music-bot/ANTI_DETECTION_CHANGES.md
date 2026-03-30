# Anti-Detection Changes Summary

## Overview

This document summarizes all the changes made to fix YouTube bot detection issues in the Discord music bot.

## Problem

The bot was experiencing:
- HTTP 429 (Too Many Requests) errors
- "Sign in to confirm you're not a bot" messages
- Failed YouTube extractions
- Rate limiting issues

## Solution

Implemented comprehensive anti-detection measures across multiple files.

## Files Modified

### 1. `music-bot/music/logic/player_manager.py`

#### Enhanced YDL_OPTS
```python
YDL_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'skip_download': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extractor_retries': 3,
    'fragment_retries': 3,
    'ignoreerrors': False,
    # Anti-detection measures
    'no_check_certificate': True,
    'prefer_insecure': True,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'referer': 'https://www.youtube.com/',
    'sleep_interval': 1,
    'max_sleep_interval': 5,
    'sleep_interval_requests': 1,
    'ratelimit': 1000000,  # 1MB/s
    'throttledratelimit': 100000,
    'geo_bypass': True,
    'geo_bypass_country': 'US',
}
```

#### Enhanced YDL_EXTRACTOR_ARGS
```python
YDL_EXTRACTOR_ARGS = {
    'youtube': {
        'player_client': ['android', 'ios', 'web', 'default'],  # Multiple clients
        'player_skip': ['configs', 'js'],
        'skip': ['hls'],
        'comment_sort': 'top',
        'max_comments': [0],  # Disable comment extraction
    }
}
```

#### Added User-Agent Rotation
```python
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
]

def get_random_user_agent() -> str:
    """Get a random user agent from the list"""
    import random
    return random.choice(USER_AGENTS)
```

#### Added Cookie Refresh Mechanism
```python
def refresh_cookies_if_needed():
    """Refresh cookies if they're older than 1 hour"""
    import time
    
    if not os.path.exists(COOKIE_FILE):
        return download_youtube_cookies()
    
    # Check file age
    file_age = time.time() - os.path.getmtime(COOKIE_FILE)
    if file_age > 3600:  # 1 hour
        logger.info("🔄 Cookies are old, refreshing...")
        return download_youtube_cookies()
    
    return True
```

#### Enhanced _try_extract with Retry Logic
```python
async def _try_extract(self, loop, url: str, fast: bool = False, max_retries: int = 3) -> Optional[str]:
    """Helper method to extract audio URL with error handling and retry logic"""
    
    for attempt in range(max_retries):
        try:
            # Refresh cookies if needed
            if attempt > 0:
                await loop.run_in_executor(None, refresh_cookies_if_needed)
            
            def _extract():
                opts = YDL_OPTS.copy()
                opts['extractor_args'] = YDL_EXTRACTOR_ARGS
                if fast:
                    opts['format'] = 'bestaudio/best'
                
                # Rotate user agent on retries
                if attempt > 0:
                    opts['user_agent'] = get_random_user_agent()
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, download=False)
            
            info = await loop.run_in_executor(self.executor, _extract)
            
            if not info:
                return None
            
            return self._get_audio_url(info)
            
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            
            # Check if it's a bot detection error
            if 'Sign in to confirm' in error_msg or '429' in error_msg:
                logger.warning(f"Bot detection triggered (attempt {attempt + 1}/{max_retries}): {error_msg}")
                
                if attempt < max_retries - 1:
                    # Exponential backoff: 2, 4, 8 seconds
                    wait_time = 2 ** (attempt + 1)
                    logger.info(f"⏳ Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"❌ Max retries reached for {url}")
                    return None
            else:
                logger.warning(f"Download error for {url}: {e}")
                return None
                
        except yt_dlp.utils.ExtractorError as e:
            logger.warning(f"Extractor error for {url}: {e}")
            return None
            
        except Exception as e:
            logger.error(f"Extraction error for {url}: {e}")
            return None
    
    return None
```

### 2. `music-bot/music/logic/search_manager.py`

#### Enhanced YDL_SEARCH_OPTS
```python
YDL_SEARCH_OPTS = {
    'format': 'bestaudio[acodec=opus]/bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extract_flat': False,
    'nocheckcertificate': True,
    'geo_bypass': True,
    'prefer_ffmpeg': True,
    'socket_timeout': 10,
    'retries': 3,
    'fragment_retries': 3,
    'skip_unavailable_fragments': True,
    # Anti-detection measures
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'referer': 'https://www.youtube.com/',
    'sleep_interval': 1,
    'max_sleep_interval': 5,
    'sleep_interval_requests': 1,
    'ratelimit': 1000000,
    'throttledratelimit': 100000,
    'geo_bypass_country': 'US',
}
```

#### Added User-Agent Rotation
```python
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
]

def get_random_user_agent() -> str:
    """Get a random user agent from the list"""
    return random.choice(USER_AGENTS)
```

#### Enhanced _extract_youtube_mix with Retry Logic
```python
async def _extract_youtube_mix(
    self,
    url: str,
    limit: int = 25,
    max_retries: int = 3
) -> Tuple[List[dict], Platform, bool]:
    """Extract YouTube Mix/Radio (dynamic playlists) with retry logic"""
    loop = asyncio.get_event_loop()
    
    for attempt in range(max_retries):
        try:
            def _extract():
                opts = YDL_SEARCH_OPTS.copy()
                opts['playlistend'] = limit
                opts['extract_flat'] = 'in_playlist'
                opts['ignoreerrors'] = True
                opts['yes_playlist'] = True
                
                # Rotate user agent on retries
                if attempt > 0:
                    opts['user_agent'] = get_random_user_agent()
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, download=False)
            
            logger.info(f"⚡ Extracting YouTube Mix (max {limit} tracks)...")
            info = await loop.run_in_executor(self.executor, _extract)
            
            # ... rest of extraction logic ...
            
        except Exception as e:
            error_msg = str(e)
            
            # Check if it's a bot detection error
            if 'Sign in to confirm' in error_msg or '429' in error_msg:
                logger.warning(f"Bot detection triggered (attempt {attempt + 1}/{max_retries}): {error_msg}")
                
                if attempt < max_retries - 1:
                    # Exponential backoff: 2, 4, 8 seconds
                    wait_time = 2 ** (attempt + 1)
                    logger.info(f"⏳ Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"❌ Max retries reached for mix extraction")
                    return [], Platform.YOUTUBE, False
            else:
                logger.error(f"Mix extraction error: {e}")
                return [], Platform.YOUTUBE, False
    
    return [], Platform.YOUTUBE, False
```

#### Enhanced _extract_via_ytdlp with Retry Logic
Similar retry logic added to `_extract_via_ytdlp` method.

### 3. `music-bot/COOKIE_SETUP.md` (New File)

Created comprehensive documentation for cookie setup including:
- Why cookies are needed
- Setup methods (URL and manual)
- Cookie format requirements
- Security considerations
- Best practices
- Troubleshooting guide
- Alternative solutions

### 4. `music-bot/README.md` (Updated)

Updated README with:
- New features list including anti-detection measures
- Enhanced troubleshooting section
- Reference to cookie setup documentation
- Information about bot detection issues

## Key Features

### 1. Anti-Detection Measures
- **User-Agent Rotation**: Randomly selects from 5 different browser user agents
- **Rate Limiting**: Limits download speed to avoid triggering YouTube's limits
- **Sleep Intervals**: Adds delays between requests (1-5 seconds)
- **Geo Bypass**: Attempts to bypass regional restrictions
- **Multiple Player Clients**: Tries different YouTube player clients (android, ios, web, default)

### 2. Retry Logic
- **Exponential Backoff**: Waits 2s, 4s, 8s between retries
- **Maximum 3 Retries**: Automatically retries failed extractions
- **Bot Detection Detection**: Identifies bot detection errors and handles them specially
- **User-Agent Rotation on Retry**: Changes user agent on each retry attempt

### 3. Cookie Management
- **Auto-Download**: Downloads cookies from configured URL on startup
- **Auto-Refresh**: Refreshes cookies older than 1 hour
- **Multiple Formats**: Supports both URL-based and manual cookie files
- **Error Handling**: Gracefully handles cookie download failures

### 4. Enhanced Error Handling
- **Specific Error Detection**: Identifies bot detection vs. other errors
- **Detailed Logging**: Provides clear error messages and retry information
- **Graceful Degradation**: Falls back to alternative methods when possible

## Testing

Both modified files have been verified to compile without syntax errors:
- ✅ `music-bot/music/logic/player_manager.py`
- ✅ `music-bot/music/logic/search_manager.py`

## Usage

### Basic Setup
1. The bot will automatically use anti-detection measures
2. No additional configuration required for basic operation

### With Cookies (Recommended)
1. Export YouTube cookies from your browser
2. Upload to a URL-accessible location
3. Set `YOUTUBE_COOKIE_URL` in `.env`
4. Restart the bot

See [COOKIE_SETUP.md](COOKIE_SETUP.md) for detailed instructions.

## Expected Behavior

### Before Changes
```
ERROR: [youtube] liTfD88dbCo: Sign in to confirm you're not a bot
ERROR: [youtube] 6QYcd7RggNU: Sign in to confirm you're not a bot
ERROR: [youtube] Il-an3K9pjg: Sign in to confirm you're not a bot
```

### After Changes
```
INFO: ⏳ Extracting: Ed Sheeran - Shape of You (Lyrics)
INFO: ✅ YouTube cookies enabled
INFO: ✓ Extraction successful
INFO: ⏳ Extracting: Charlie Puth - Attention (Lyrics)
INFO: ✓ Extraction successful
```

## Maintenance

### Regular Tasks
1. **Update Cookies**: Re-export cookies every few days
2. **Monitor Logs**: Check `music-bot.log` for errors
3. **Update yt-dlp**: Keep yt-dlp updated to latest version

### Troubleshooting
1. Check cookie expiration
2. Verify cookie URL accessibility
3. Review logs for specific error messages
4. Test with simple YouTube searches

## References

- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp)
- [YouTube Cookie FAQ](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)
- [Exporting YouTube Cookies](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)
