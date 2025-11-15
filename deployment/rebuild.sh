#!/bin/bash

# Quick rebuild script - use after code changes

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Rebuilding Alpha Sniper V2${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${YELLOW}Stopping container...${NC}"
docker compose down

echo -e "${YELLOW}Rebuilding image...${NC}"
docker compose build --no-cache

echo -e "${YELLOW}Starting container...${NC}"
docker compose up -d

echo ""
echo -e "${GREEN}✅ Rebuild complete!${NC}"
echo ""
echo -e "View logs: ${BLUE}docker compose logs -f${NC}"
echo -e "Check status: ${BLUE}./deployment/monitor.sh${NC}"
