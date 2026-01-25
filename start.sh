#!/bin/bash

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting CC Rewards Dashboard${NC}\n"

# Change to project root directory
cd "$(dirname "$0")"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found at venv${NC}"
    exit 1
fi

# Activate virtual environment
echo -e "${YELLOW}📦 Activating virtual environment...${NC}"
source venv/bin/activate

# Start PostgreSQL with Docker Compose
echo -e "${YELLOW}🐘 Starting PostgreSQL database...${NC}"
docker-compose up -d

# Wait for PostgreSQL to be ready
echo -e "${YELLOW}⏳ Waiting for database to be ready...${NC}"
until docker exec cc_rewards_db pg_isready -U cc_user -d cc_rewards > /dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo -e "\n${GREEN}✅ Database is ready${NC}\n"

# Run migrations
echo -e "${YELLOW}🔄 Running database migrations...${NC}"
alembic upgrade head

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Migration failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Migrations completed${NC}\n"

# Start FastAPI server
echo -e "${GREEN}🌐 Starting FastAPI server on http://localhost:8000${NC}"
echo -e "${GREEN}📚 API Documentation: http://localhost:8000/docs${NC}\n"

export PYTHONPATH="${PWD}/src"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
