# YouTube Cookie Setup Guide

## Overview

This guide explains how to set up YouTube cookies for the Discord music bot to bypass YouTube's bot detection measures.

## Why Cookies Are Needed

YouTube has implemented strict anti-bot measures that can block automated downloads. The bot may encounter:
- HTTP 429 (Too Many Requests) errors
- "Sign in to confirm you're not a bot" messages
- Rate limiting

Using authenticated cookies helps bypass these restrictions.

## Setup Methods

### Method 1: Using Cookie URL (Recommended)

1. **Export cookies from your browser:**
   - Install a browser extension like "Get cookies.txt LOCALLY" (Chrome/Firefox)
   - Log into YouTube in your browser
   - Export cookies to a `cookies.txt` file

2. **Upload cookies to a hosting service:**
   - Upload the `cookies.txt` file to a GitHub Gist, Pastebin, or any URL-accessible location
   - Make sure the URL is publicly accessible

3. **Configure the bot:**
   - Edit `music-bot/.env` file
   - Add or update the cookie URL:
   ```
   YOUTUBE_COOKIE_URL=https://gist.githubusercontent.com/yourusername/yourgist/raw/cookies.txt
   ```

4. **Restart the bot:**
   - The bot will automatically download and use the cookies

### Method 2: Manual Cookie File

1. **Export cookies from your browser:**
   - Use a browser extension to export cookies
   - Save as `cookies.txt` in Netscape format

2. **Place the file:**
   - Copy `cookies.txt` to the `music-bot/` directory
   - The bot will automatically detect and use it

3. **Restart the bot**

## Cookie Format

The `cookies.txt` file must be in Netscape format:

```
# Netscape HTTP Cookie File
.youtube.com	TRUE	/	FALSE	0	COOKIE_NAME	COOKIE_VALUE
```

## Important Notes

### Cookie Expiration
- YouTube cookies typically expire after a few hours to a few days
- The bot automatically refreshes cookies older than 1 hour
- You may need to re-export cookies periodically

### Security Considerations
- **Never share your cookies publicly** - they contain your authentication
- Use a dedicated YouTube account for the bot
- Don't use your personal Google account cookies
- Consider using a separate browser profile for bot cookies

### Best Practices
1. **Use a dedicated account:** Create a separate YouTube/Google account for the bot
2. **Regular updates:** Update cookies every few days
3. **Monitor logs:** Check `music-bot.log` for cookie-related errors
4. **Test first:** Test with a simple search before using in production

## Troubleshooting

### "Sign in to confirm you're not a bot" Error
- Cookies are expired or invalid
- Re-export cookies from your browser
- Make sure you're logged into YouTube when exporting

### HTTP 429 Errors
- Too many requests in a short time
- The bot has built-in retry logic with exponential backoff
- Consider reducing the number of concurrent requests

### Cookie Download Fails
- Check if the cookie URL is accessible
- Verify the URL in `.env` is correct
- Check network connectivity

### Bot Still Gets Blocked
- Try using a different YouTube account
- Use a VPN or proxy
- Reduce request frequency
- Consider using YouTube Music API instead

## Advanced Configuration

### Custom User Agents
The bot rotates between multiple user agents to avoid detection:
- Chrome (Windows)
- Chrome (Mac)
- Firefox (Windows)
- Safari (Mac)

### Rate Limiting
The bot includes built-in rate limiting:
- 1 MB/s download rate limit
- 100 KB/s throttled rate limit
- 1-5 second sleep intervals between requests

### Retry Logic
- Automatic retry on bot detection (up to 3 attempts)
- Exponential backoff: 2s, 4s, 8s delays
- User agent rotation on retries

## Alternative Solutions

If cookies don't work, consider:

1. **YouTube Music API:** Use `ytmusicapi` for better compatibility
2. **Proxy Rotation:** Use rotating proxies to avoid IP-based blocking
3. **Reduced Request Rate:** Lower the frequency of requests
4. **Different Platform:** Use alternative music sources (Spotify, SoundCloud)

## Support

For issues or questions:
1. Check the logs in `music-bot.log`
2. Verify cookie format and expiration
3. Test with a simple YouTube search
4. Review YouTube's terms of service

## References

- [yt-dlp Cookie Documentation](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)
- [Exporting YouTube Cookies](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)
- [Browser Cookie Extensions](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
