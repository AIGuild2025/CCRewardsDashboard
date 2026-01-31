#!/bin/bash

# Color codes for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🛑 Stopping CC Rewards Dashboard${NC}\n"

# Change to project root directory
cd "$(dirname "$0")"

# Stop FastAPI server (if running)
echo -e "${YELLOW}Stopping FastAPI server...${NC}"
pkill -f "uvicorn app.main:app"

# Stop PostgreSQL
echo -e "${YELLOW}Stopping PostgreSQL database...${NC}"
docker-compose down

echo -e "\n${YELLOW}✅ All services stopped${NC}"
