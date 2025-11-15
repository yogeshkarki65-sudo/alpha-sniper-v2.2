#!/bin/bash

# Alpha Sniper V2 - Quick Start Script
# For starting the bot on an already configured server

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Alpha Sniper V2 - Quick Start${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo -e "${YELLOW}Creating from example...${NC}"
    cp .env.example .env
    echo -e "${RED}⚠ IMPORTANT: Edit .env file before continuing!${NC}"
    echo -e "${YELLOW}Run: nano .env${NC}"
    exit 1
fi

# Verify critical config
echo -e "${YELLOW}Checking configuration...${NC}"
if grep -q "YOUR_BOT_TOKEN_HERE" .env; then
    echo -e "${RED}❌ Telegram bot token not configured!${NC}"
    echo -e "${YELLOW}Edit .env and set TELEGRAM_BOT_TOKEN${NC}"
    exit 1
fi

if grep -q "YOUR_CHAT_ID_HERE" .env; then
    echo -e "${RED}❌ Telegram chat ID not configured!${NC}"
    echo -e "${YELLOW}Edit .env and set TELEGRAM_CHAT_ID${NC}"
    exit 1
fi

MODE=$(grep "^MODE=" .env | cut -d= -f2)
echo -e "Trading Mode: ${BLUE}$MODE${NC}"

if [ "$MODE" = "LIVE" ]; then
    echo -e "${RED}⚠ WARNING: Running in LIVE mode!${NC}"
    echo -e "${YELLOW}Are you sure? (yes/no)${NC}"
    read -r response
    if [ "$response" != "yes" ]; then
        echo -e "${RED}Aborted. Switch to SIM mode in .env${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓${NC} Configuration OK"
echo ""

# Create directories if they don't exist
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p data logs backups
echo -e "${GREEN}✓${NC} Directories created"
echo ""

# Check if Docker is running
if ! docker ps &> /dev/null; then
    echo -e "${RED}❌ Docker is not running!${NC}"
    echo -e "${YELLOW}Start Docker and try again${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker is running"
echo ""

# Check if already running
if docker ps | grep -q alpha-sniper-v2; then
    echo -e "${YELLOW}Bot is already running!${NC}"
    echo -e "${YELLOW}Do you want to restart? (yes/no)${NC}"
    read -r response
    if [ "$response" = "yes" ]; then
        echo -e "${YELLOW}Stopping...${NC}"
        docker compose down
        sleep 2
    else
        echo -e "${GREEN}Keeping current instance running${NC}"
        exit 0
    fi
fi

# Build and start
echo -e "${YELLOW}Building Docker image...${NC}"
docker compose build

echo ""
echo -e "${YELLOW}Starting bot...${NC}"
docker compose up -d

echo ""
echo -e "${YELLOW}Waiting for bot to initialize...${NC}"
sleep 5

# Check if running
if docker ps | grep -q alpha-sniper-v2; then
    echo -e "${GREEN}✅ Bot started successfully!${NC}"
    echo ""

    # Show initial logs
    echo -e "${CYAN}Initial logs:${NC}"
    docker compose logs --tail=20
    echo ""

    echo -e "${BLUE}========================================${NC}"
    echo -e "${GREEN}Quick Start Complete!${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo -e "${YELLOW}Useful commands:${NC}"
    echo -e "  View logs:       ${CYAN}docker compose logs -f${NC}"
    echo -e "  Check status:    ${CYAN}./deployment/monitor.sh${NC}"
    echo -e "  View stats:      ${CYAN}./deployment/stats.sh${NC}"
    echo -e "  Stop bot:        ${CYAN}docker compose down${NC}"
    echo -e "  Check health:    ${CYAN}curl http://localhost:80/health${NC}"
    echo ""
    echo -e "${GREEN}Monitor your Telegram for alerts!${NC}"
else
    echo -e "${RED}❌ Failed to start bot!${NC}"
    echo -e "${YELLOW}Check logs:${NC}"
    docker compose logs --tail=50
    exit 1
fi
