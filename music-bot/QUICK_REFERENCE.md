# 🚀 Railway Deployment Quick Reference Card

## 📋 Pre-Deployment Checklist

- [ ] Get Discord Bot Token from [Discord Developer Portal](https://discord.com/developers)
- [ ] Enable "Message Content Intent" in bot settings
- [ ] GitHub account with code pushed
- [ ] Railway account at [railway.app](https://railway.app)
- [ ] Node.js installed (for Railway CLI)
- [ ] Git installed

---

## 🚀 Deployment Methods

### Method 1: One-Command Deploy (RECOMMENDED)
```bash
cd music-bot
bash deploy-railway.sh
# Follow interactive prompts
# Bot deploys automatically
```

### Method 2: Railway Dashboard
1. Go to https://railway.app
2. New Project → GitHub Repo
3. Select this repository
4. Set `DISCORD_TOKEN` env var
5. Deploy

### Method 3: Railway CLI
```bash
# Install
npm install -g @railway/cli

# Setup
railway login
cd music-bot
railway init

# Configure
railway variables set DISCORD_TOKEN "your-token"

# Deploy
railway up

# Monitor
railway logs -f
```

---

## ⚙️ Environment Variables

### On Railway Dashboard / CLI:

| Variable | Required | Example | Notes |
|----------|----------|---------|-------|
| `DISCORD_TOKEN` | ✅ Yes | `MzA...` | From Discord Developer |
| `PROXIES` | ❌ No | `proxy1:8080,proxy2:8080` | Optional, improves success |
| `LOG_LEVEL` | ❌ No | `INFO` or `DEBUG` | Default: INFO |
| `YDL_SOCKET_TIMEOUT` | ❌ No | `20` | Default: 20 seconds |

### Set via CLI:
```bash
railway variables set DISCORD_TOKEN "your-token"
railway variables set PROXIES "proxy1.com:8080"
railway variables set LOG_LEVEL "DEBUG"
```

---

## 🛠️ Common Commands

### Deploy & Monitor
```bash
# Deploy code
railway up

# View live logs
railway logs -f

# Check status
railway status

# Restart bot
railway restart

# Stop bot
railway stop

# Delete deployment
railway remove
```

### Environment Vars
```bash
# List all variables
railway variables list

# Set variable
railway variables set NAME "value"

# Remove variable
railway variables delete NAME

# View single variable
railway variables get NAME
```

### Console Access
```bash
# SSH into Railway container
railway shell

# Inside shell:
python music.py          # Test bot
python -c "import discord; print('OK')"  # Test imports
exit                     # Exit shell
```

---

## 📊 Monitoring & Debugging

### View Logs
```bash
# Live logs
railway logs -f

# Last 100 lines
railway logs -f --limit 100

# Grep logs
railway logs -f | grep ERROR
railway logs -f | grep "Music Cog"
```

### Expected Log Output
```
✅ Success:
[INFO] __main__: 🎵 Starting Music Bot...
[INFO] discord.client: logging in using static token
[INFO] discord.music: 🎵 Music Cog initialized (Fast & Simple)
[INFO] discord.music.search: 🔍 Search Service initialized
[INFO] __main__: ✅ Loaded 1 cogs successfully

⚠️ Warning (OK, will recover):
[WARNING] discord.music.search: Search timeout for: baby
[INFO] discord.music.search: ✅ Fallback successful

❌ Error (Needs attention):
[ERROR] discord.music: Extraction error
[ERROR] __main__: Failed to load extension
```

### Check Bot Health
```bash
# In Discord, send:
!status

# Bot should respond with:
# Currently Playing: None
# Queue: 0 songs
# Uptime: 2h 15m
```

---

## 🔒 Anti-Bot Detection Features

### Automatically Enabled
✅ User agent rotation (7 realistic browsers)
✅ Browser-like request headers
✅ Retry logic (3 attempts)
✅ Smart timeouts (15s search, 10s extraction)
✅ Fallback mechanisms

### Optional: Add Proxies
```bash
# Get proxies from:
# https://www.proxy-list.download/ (free)
# or Bright Data, Smartproxy, Oxylabs (paid)

# Set on Railway:
railway variables set PROXIES "proxy1.com:8080,proxy2.com:8080"

# Test proxy:
curl -x http://proxy1.com:8080 https://api.ipify.org
```

---

## ❌ Troubleshooting

### Bot Not Starting?
```bash
# 1. Check logs
railway logs -f

# 2. Verify token is set
railway variables list

# 3. Python version (should be 3.12)
railway run python --version

# 4. Check requirements installed
railway run pip list
```

### Searches Timing Out?
```bash
# 1. Increase timeout
railway variables set YDL_SOCKET_TIMEOUT 30

# 2. Add proxies
railway variables set PROXIES "proxy1.com:8080,proxy2.com:8080"

# 3. Restart
railway restart
```

### Music Won't Play?
```bash
# 1. Bot has voice permissions?
# 2. Bot connected to voice channel?
# 3. Try different song name
# 4. Check bot can hear: !status
```

### Out of Memory?
```bash
# Check memory
railway status

# If over 300MB:
# Option 1: Restart (clears cache)
railway restart

# Option 2: Upgrade Railway tier
# Option 3: Reduce queue size in code
```

---

## 📁 File Structure

```
Pre-Deployment Files Created:
✅ railway.toml              Railway config
✅ Procfile                  Process file
✅ docker-compose.yml        Docker setup
✅ .env.example              Environment template
✅ deploy-railway.sh         Auto-deploy script
✅ requirements.txt          Updated with proxy support

Anti-Bot Detection:
✅ music/services/anti_bot_detection.py  Core module

Documentation:
✅ RAILWAY_COMPLETE.md       Overview & quick start
✅ RAILWAY_DEPLOYMENT.md     Detailed guide
✅ ANTI_BOT_DETECTION_GUIDE.md  How anti-bot works
✅ INTEGRATION_EXAMPLE.md    Code examples
✅ DEPLOYMENT_SUMMARY.md     What was created
✅ THIS FILE                 Quick reference
```

---

## 🎯 Success Indicators

After deployment, you should see:

✅ Bot appears online in Discord
✅ !play command responds
✅ Music searches work (10-15s)
✅ Music plays without errors
✅ Queue system functional
✅ Logs show no ERROR messages
✅ Memory under 300MB
✅ Uptime counter increasing

---

## 💡 Tips & Tricks

### Speed Up First Deploy
```bash
# If cloning from GitHub is slow:
# Download ZIP and upload to Railway manually
# Or use: git clone --depth 1 (shallow clone)
```

### Test Locally Before Deploy
```bash
# Copy env
cp .env.example .env
# Edit .env with your token

# Run locally
python music.py

# Test commands in Discord
# Then: Ctrl+C to stop

# Deploy:
railway up
```

### Monitor Specific Errors
```bash
# Search errors
railway logs -f | grep -i "search"

# Extraction errors
railway logs -f | grep -i "extraction"

# Connection errors
railway logs -f | grep -i "connection"
```

### Batch Update Environment Variables
```bash
# Create a script to set multiple at once
cat << EOF | xargs -I {} railway variables set {}
DISCORD_TOKEN=xxx
LOG_LEVEL=INFO
YDL_SOCKET_TIMEOUT=20
EOF
```

---

## 🔗 Useful Links

| Resource | URL |
|----------|-----|
| Railway Dashboard | https://railway.app/dashboard |
| Discord Developer Portal | https://discord.com/developers/applications |
| yt-dlp Repository | https://github.com/yt-dlp/yt-dlp |
| Railway Documentation | https://docs.railway.app |
| Discord.py Documentation | https://discordpy.readthedocs.io |
| Bot Invite Link Pattern | `https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=8&scope=bot` |

---

## 🆘 Emergency Commands

### Restart Bot (Fix Most Issues)
```bash
railway restart
```

### View All Deployments
```bash
railway deployments
```

### Rollback to Previous
```bash
railway deployments list
railway deployments config DEPLOYMENT_ID
```

### Hard Reset
```bash
# Stop everything
railway stop

# Remove deployment
railway remove

# Deploy fresh
railway up
```

---

## 📊 Estimated Timeline

| Stage | Time | Action |
|-------|------|--------|
| Setup | 5 min | Set Discord token |
| Deploy | 2-3 min | Push to Railway |
| Startup | 1-2 min | Bot initializes |
| Ready | 0 min | Done! ✅ |
| **Total** | **8-10 min** | **From token to live** |

---

## 💬 Getting Help

### If Something Breaks:
1. Check logs: `railway logs -f`
2. Search documentation: `RAILWAY_DEPLOYMENT.md`
3. See troubleshooting: `ANTI_BOT_DETECTION_GUIDE.md`
4. Check examples: `INTEGRATION_EXAMPLE.md`

### Common Issues Already Covered:
- ✅ "Already playing audio" error → Fixed in queue system
- ✅ Search timeout errors → Anti-bot handles with fallback
- ✅ Bot permissions → See guide for voice channel setup
- ✅ Memory issues → Bot auto-manages cache
- ✅ YouTube blocks → Anti-bot detection prevents

---

**Ready? Start with: `bash deploy-railway.sh` or go to `RAILWAY_COMPLETE.md`** 🚀
