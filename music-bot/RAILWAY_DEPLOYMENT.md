# 🚀 Railway Deployment Guide - Discord Music Bot with Anti-Bot Detection

## 📋 Prerequisites

1. Discord Bot Token
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application
   - Go to "Bot" section and create bot
   - Copy the token (keep it secret!)
   - Enable "Message Content Intent" under Privileged Gateway Intents

2. GitHub Repository
   - Push your code to GitHub (public or private)
   - Railway can clone from private repos too

3. Railway Account
   - Sign up at [railway.app](https://railway.app)
   - Connect your GitHub account

---

## 🔧 Step 1: Configure Environment Variables

### On Railway Dashboard:

1. Create a new Project
2. Add Environment Variables:

```
DISCORD_TOKEN=your_bot_token_here
PROXIES=                    # Optional: proxy1.com:port,proxy2.com:port
LOG_LEVEL=INFO
```

### Optional: Add Proxies (for even better bot detection avoidance)
If you want to add proxy support for extra safety:
```
PROXIES=proxy1.com:8080,proxy2.com:8080,proxy3.com:8080
```

---

## 🐳 Step 2: Deploy with Railway

### Option A: Deploy from GitHub (Recommended)

1. Go to Railway Dashboard → New Project
2. Select "GitHub Repo"
3. Authorize Railway to access your GitHub
4. Select this repository
5. Railway auto-detects `Dockerfile` (or uses `Procfile`)
6. Set environment variables (see Step 1)
7. Click "Deploy"

### Option B: Deploy using Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link project
railway link

# Deploy
railway up

# View logs
railway logs -f
```

---

## 🛡️ Anti-Bot Detection Features

The deployment includes several anti-detection measures:

### 1. User Agent Rotation ✅
- Rotates between 7 different realistic user agents
- Makes requests look like real browsers
- Includes Chrome, Firefox, and Safari

### 2. Request Headers ✅
```
Accept-Language: en-US,en;q=0.9
Accept-Encoding: gzip, deflate, br
DNT: 1
Referer: https://www.google.com/
```

### 3. Retry Logic ✅
- Automatic retries: 3 times for extraction, 3 for fragments
- Exponential backoff between retries
- Skips unavailable fragments gracefully

### 4. Socket Timeout ✅
- 20 seconds per request (prevents hanging)
- Fragment retries enabled
- HLS native streaming preferred

### 5. Proxy Support ✅ (Optional but Recommended)
- Rotate through multiple proxies
- Hide server IP address
- Distribute requests across different sources

```bash
# Example with proxies
PROXIES=proxy1.com:8080,proxy2.com:8080,proxy3.com:3128
```

---

## 📊 Monitoring & Logs

### View Live Logs
```bash
railway logs -f
```

### Check Bot Status
```bash
# From Discord
!status
```

### Common Log Patterns

✅ **Success:**
```
[INFO] discord.music: 🔍 Searching: adele rolling in the deep
[INFO] discord.music.search: ✅ Found 10 results for: adele rolling in the deep
[INFO] discord.music: ✅ Extracted: Adele - Rolling in the Deep (Official Audio)
```

⚠️ **Warning (Usually Recovers):**
```
[WARNING] discord.music.search: Search timeout for: baby
[INFO] discord.music.search: ✅ Fallback successful: Got 5 results for: baby
```

❌ **Error (Needs Attention):**
```
[ERROR] discord.music: Extraction error: Unavailable
```

---

## 🔄 What to Do If Bot Fails

### 1. YouTube Returns "Unavailable" Videos
This means YouTube blocked the search result (not the bot). Solutions:
- Try a different song
- Specify artist name: "!play artist name song title"
- Use direct YouTube URL

### 2. Requests Timeout Too Often
Enable proxies:
```
PROXIES=proxy1.com:8080,proxy2.com:8080
```

Get free proxies from:
- [Free Proxy List](https://www.proxy-list.download/)
- [ProxyIPv4](https://proxyipv4.com/)
- Paid providers: Rotating Residential Proxies (recommended)

### 3. Bot Goes Down
Railway auto-restarts on failure:
```
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 5
```

Manual restart:
1. Railway Dashboard → Deployments
2. Click "Restart"

---

## 💾 Storage & Memory

### Memory Usage
- Expected: 150-200MB (Railway free tier: 512MB)
- Monitor in Railway Dashboard → Resources

### Disk Usage
- Cookies: ~5KB
- Logs: Rotated automatically
- Cache: Cleared between restarts

### If Out of Memory
1. Restart bot
2. Upgrade to next tier
3. Reduce queue size: Edit `cog_simple.py`
   ```python
   deque(maxlen=50)  # Change 50 to smaller number
   ```

---

## 🌐 Domain & Networking

### Important: No Public URL Needed
This bot only connects to:
- Discord API (outbound)
- YouTube/ytmusic API (outbound)
- Proxy servers (if configured, outbound)

No inbound ports needed. Railway handles networking automatically.

---

## 📈 Performance Tips

### 1. Update Cookies Regularly
The bot auto-downloads YouTube cookies on startup.
If searches fail, cookies might be stale:
```bash
# Restart bot to refresh
railway logs -f  # Then look for "YouTube cookies updated"
```

### 2. Cache Search Results
The bot caches search results to reduce API calls:
```
First search: 10-15 seconds
Cached search (same query): <1 second
```

### 3. Optimize Queue
Keep queue size low:
- Default: 50 songs max
- Memory: ~1KB per song
- Recommended: Keep < 20 active songs

---

## 🆘 Troubleshooting

### Bot Not Starting
```bash
railway logs -f
```
Look for errors. Common issues:
- Invalid `DISCORD_TOKEN`
- Missing Python dependencies
- Port already in use (unlikely on Railway)

### Commands Not Working
```
1. Check bot has permissions in server
2. Verify bot prefix (!play, not just "play")
3. Ensure bot is in voice channel first
```

### Music Won't Play
```
1. Verify bot is connected to voice
2. Check FFmpeg installed (included in Docker)
3. Try different song
4. Check bot has "Connect" and "Speak" permissions
```

### Frequent Timeouts
```
1. Enable proxies (see Step 1)
2. Increase timeout in code: YDL_SOCKET_TIMEOUT=30
3. Restart bot
4. Check internet connection on Railway (rare)
```

---

## 🔐 Security Best Practices

1. ✅ Keep `DISCORD_TOKEN` in Railway secrets (never in code)
2. ✅ Use HTTPS for proxies if available
3. ✅ Rotate tokens periodically
4. ✅ Don't share `.env` file
5. ✅ Use private GitHub repo option

---

## 📞 Support Resources

1. **Discord.py Docs**: https://discordpy.readthedocs.io/
2. **yt-dlp Docs**: https://github.com/yt-dlp/yt-dlp
3. **Railway Docs**: https://docs.railway.app/
4. **Railway Community**: https://railway.app/community

---

## 🚀 Quick Start Summary

```bash
# 1. Clone repo
git clone https://github.com/YOUR_USERNAME/discord_multi-bot.git
cd discord_multi-bot/music-bot

# 2. Copy environment template
cp .env.example .env
# Edit .env with your DISCORD_TOKEN

# 3. Test locally (optional)
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python music.py

# 4. Push to GitHub
git add .
git commit -m "Deploy to Railway"
git push

# 5. Deploy on Railway Dashboard
# New Project → GitHub Repo → Set DISCORD_TOKEN → Deploy
```

---

## ✅ Deployment Complete!

Your bot is now live on Railway! 🎉

Commands available:
- `!play <song>` - Play music
- `!pause` - Pause
- `!resume` - Resume
- `!skip` - Skip song
- `!queue` - Show queue
- `!stop` - Stop and disconnect
- `!volume <0-100>` - Set volume
- `!status` - Show status

Enjoy! 🎵
