#!/bin/bash

# Linguard - Setup Dependencies Script
# This script installs all dependencies for backend and frontend

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "======================================"
echo "Linguard - Setup Dependencies"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Backend Setup
echo -e "${BLUE}[1/4]${NC} Setting up Backend..."
echo "-------------------------------------"

cd "$PROJECT_ROOT/backend"

# Check Python version
if ! command_exists python3; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    echo "Please install Python 3.11+ and try again"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}✓${NC} Found Python $PYTHON_VERSION"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    echo -e "${GREEN}✓${NC} Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install uv in the virtual environment
echo "Installing uv package manager..."
pip install --upgrade pip > /dev/null 2>&1
pip install uv > /dev/null 2>&1
echo -e "${GREEN}✓${NC} uv installed"

# Install dependencies using uv
echo "Installing Python dependencies with uv..."
uv pip install -r requirements.txt > /dev/null 2>&1
echo -e "${GREEN}✓${NC} Python dependencies installed"

# Copy .env.dev to .env if .env doesn't exist
if [ ! -f ".env" ]; then
    if [ -f ".env.dev" ]; then
        cp .env.dev .env
        echo -e "${GREEN}✓${NC} Created .env from .env.dev"
    else
        echo -e "${YELLOW}⚠${NC} Warning: .env.dev not found, skipping .env creation"
    fi
else
    echo -e "${GREEN}✓${NC} .env already exists"
fi

echo ""

# Frontend Setup
echo -e "${BLUE}[2/4]${NC} Setting up Frontend..."
echo "-------------------------------------"

cd "$PROJECT_ROOT/frontend"

# Check Node.js version
if ! command_exists node; then
    echo -e "${RED}Error: Node.js is not installed${NC}"
    echo "Please install Node.js 18+ and try again"
    exit 1
fi

NODE_VERSION=$(node --version)
echo -e "${GREEN}✓${NC} Found Node.js $NODE_VERSION"

# Check npm version
if ! command_exists pnpm; then
    echo -e "${YELLOW}⚠${NC} pnpm not found, installing globally..."
    npm install -g pnpm > /dev/null 2>&1
    echo -e "${GREEN}✓${NC} pnpm installed"
fi

PNPM_VERSION=$(pnpm --version)
echo -e "${GREEN}✓${NC} Found pnpm $PNPM_VERSION"

# Install dependencies
echo "Installing dependencies with pnpm..."
pnpm install > /dev/null 2>&1
echo -e "${GREEN}✓${NC} Dependencies installed"

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "VITE_API_URL=http://localhost:8000" > .env
    echo -e "${GREEN}✓${NC} Created frontend .env"
else
    echo -e "${GREEN}✓${NC} .env already exists"
fi

echo ""

# Docker Check
echo -e "${BLUE}[3/4]${NC} Checking Docker..."
echo "-------------------------------------"

if ! command_exists docker; then
    echo -e "${YELLOW}⚠${NC} Warning: Docker is not installed or not running"
    echo "You will need Docker to run PostgreSQL"
    echo "Install Docker Desktop: https://www.docker.com/products/docker-desktop"
else
    DOCKER_VERSION=$(docker --version)
    echo -e "${GREEN}✓${NC} Found $DOCKER_VERSION"
    
    # Check if docker daemon is running
    if docker info >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Docker daemon is running"
    else
        echo -e "${YELLOW}⚠${NC} Warning: Docker daemon is not running"
        echo "Please start Docker Desktop"
    fi
fi

if ! docker compose version >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠${NC} Warning: docker compose is not available"
else
    COMPOSE_VERSION=$(docker compose version)
    echo -e "${GREEN}✓${NC} Found $COMPOSE_VERSION"
fi

echo ""

# Summary
echo -e "${BLUE}[4/4]${NC} Setup Complete!"
echo "======================================"
echo ""
echo -e "${GREEN}✓${NC} Backend dependencies installed"
echo -e "${GREEN}✓${NC} Frontend dependencies installed"
echo -e "${GREEN}✓${NC} Environment files configured"
echo ""
echo "Next steps:"
echo "1. Start debugging in VS Code (Press F5 → Select 'fullstack')"
echo "2. Or manually start services:"
echo "   - Backend:  cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo "   - Frontend: cd frontend && pnpm run dev"
echo "   - Docker:   docker compose -f docker-compose.dev.yaml up -d"
echo ""
echo "Happy coding! 🚀"
