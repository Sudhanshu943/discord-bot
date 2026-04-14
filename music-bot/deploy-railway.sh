#!/bin/bash
# 🚀 Railway Deployment Helper Script
# Makes it easy to deploy to Railway without manual steps

set -e  # Exit on error

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}🚀 Railway Deployment Setup${NC}"
echo -e "${BLUE}================================${NC}\n"

# 1. Check if Railway CLI is installed
echo -e "${YELLOW}1️⃣  Checking Railway CLI...${NC}"
if ! command -v railway &> /dev/null; then
    echo -e "${RED}❌ Railway CLI not found. Installing...${NC}"
    npm install -g @railway/cli
fi
echo -e "${GREEN}✅ Railway CLI ready${NC}\n"

# 2. Check Git
echo -e "${YELLOW}2️⃣  Checking Git...${NC}"
if ! command -v git &> /dev/null; then
    echo -e "${RED}❌ Git not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Git ready${NC}\n"

# 3. Setup environment
echo -e "${YELLOW}3️⃣  Setting up environment...${NC}"
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}✅ Created .env from template${NC}"
    else
        echo -e "${RED}❌ .env.example not found${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ .env already exists${NC}"
fi

# 4. Prompt for Discord Token
echo -e "\n${YELLOW}4️⃣  Discord Token${NC}"
echo "Get your token from: https://discord.com/developers/applications"
read -p "Enter your Discord Bot Token: " DISCORD_TOKEN

if [ -z "$DISCORD_TOKEN" ]; then
    echo -e "${RED}❌ Token cannot be empty${NC}"
    exit 1
fi

# 5. Optional: Proxies
echo -e "\n${YELLOW}5️⃣  Proxies (Optional)${NC}"
echo "For best results against bot detection, add proxies"
echo "Format: proxy1.com:8080,proxy2.com:8080"
read -p "Enter proxies (or press Enter to skip): " PROXIES

# 6. Update .env file
echo -e "\n${YELLOW}6️⃣  Updating .env file...${NC}"
# Use sed to update .env (cross-platform)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s|DISCORD_TOKEN=.*|DISCORD_TOKEN=$DISCORD_TOKEN|" .env
    if [ ! -z "$PROXIES" ]; then
        sed -i '' "s|PROXIES=.*|PROXIES=$PROXIES|" .env
    fi
else
    # Linux
    sed -i "s|DISCORD_TOKEN=.*|DISCORD_TOKEN=$DISCORD_TOKEN|" .env
    if [ ! -z "$PROXIES" ]; then
        sed -i "s|PROXIES=.*|PROXIES=$PROXIES|" .env
    fi
fi
echo -e "${GREEN}✅ .env updated${NC}"

# 7. Test locally (optional)
echo -e "\n${YELLOW}7️⃣  Test locally? (y/n)${NC}"
read -p "Run bot locally before deploying? " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Starting bot locally...${NC}"
    python music.py &
    PID=$!
    echo -e "${GREEN}✅ Bot started (PID: $PID)${NC}"
    echo "Press Enter to continue..."
    read
    kill $PID 2>/dev/null || true
    echo -e "${GREEN}✅ Bot stopped${NC}"
fi

# 8. Git setup
echo -e "\n${YELLOW}8️⃣  Git setup...${NC}"
git add -A
git commit -m "🚀 Deploy to Railway with anti-bot detection" || true
echo -e "${GREEN}✅ Changes committed${NC}"

# 9. Railway login
echo -e "\n${YELLOW}9️⃣  Railway login...${NC}"
railway login

# 10. Railway project
echo -e "\n${YELLOW}🔟 Creating/linking Railway project...${NC}"
echo "Choose one:"
echo "1. Create new project"
echo "2. Link existing project"
read -p "Enter choice (1 or 2): " choice

if [ "$choice" = "1" ]; then
    railway init
elif [ "$choice" = "2" ]; then
    railway link
else
    echo -e "${RED}❌ Invalid choice${NC}"
    exit 1
fi

# 11. Set environment variables on Railway
echo -e "\n${YELLOW}Setting environment variables on Railway...${NC}"
railway variables set DISCORD_TOKEN "$DISCORD_TOKEN"
if [ ! -z "$PROXIES" ]; then
    railway variables set PROXIES "$PROXIES"
fi
railway variables set LOG_LEVEL "INFO"
echo -e "${GREEN}✅ Environment variables set${NC}"

# 12. Deploy
echo -e "\n${YELLOW}🚀 Deploying to Railway...${NC}"
railway up

echo -e "\n${GREEN}================================${NC}"
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo -e "${GREEN}================================${NC}"
echo -e "\nYour bot is now live on Railway! 🎉"
echo -e "\nUseful commands:"
echo -e "  ${BLUE}railway logs -f${NC}      # View live logs"
echo -e "  ${BLUE}railway status${NC}       # Check status"
echo -e "  ${BLUE}railway restart${NC}      # Restart bot"
echo -e "\nNext steps:"
echo -e "  1. Invite bot to Discord server"
echo -e "  2. Test commands: !play <song>"
echo -e "  3. Monitor logs for any issues"
