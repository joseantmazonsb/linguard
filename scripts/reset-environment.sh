#!/bin/bash

# Linguard - Reset Environment Script
# This script removes all cache, build files, and dependencies to start fresh

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "================================================"
echo "Linguard - Reset Environment"
echo "================================================"
echo ""
echo "This will remove:"
echo "  - Backend: venv, __pycache__, .pytest_cache, .ruff_cache"
echo "  - Frontend: node_modules, dist, .vite"
echo "  - Docker: containers and volumes"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Ask for confirmation
read -p "Are you sure you want to reset the environment? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Reset cancelled."
    exit 0
fi

echo ""
echo -e "${BLUE}[1/4]${NC} Cleaning Backend..."
echo "-------------------------------------"

cd "$PROJECT_ROOT/backend"

# Remove virtual environment
if [ -d "venv" ]; then
    echo "Removing virtual environment..."
    rm -rf venv
    echo -e "${GREEN}✓${NC} Virtual environment removed"
else
    echo -e "${YELLOW}⚠${NC} No virtual environment found"
fi

# Remove Python cache files
echo "Removing Python cache files..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
echo -e "${GREEN}✓${NC} Python cache files removed"

# Remove .env (optional - commented out by default)
# if [ -f ".env" ]; then
#     echo "Removing .env file..."
#     rm .env
#     echo -e "${GREEN}✓${NC} .env file removed"
# fi

echo ""
echo -e "${BLUE}[2/4]${NC} Cleaning Frontend..."
echo "-------------------------------------"

cd "$PROJECT_ROOT/frontend"

# Remove node_modules
if [ -d "node_modules" ]; then
    echo "Removing node_modules (this may take a while)..."
    rm -rf node_modules
    echo -e "${GREEN}✓${NC} node_modules removed"
else
    echo -e "${YELLOW}⚠${NC} No node_modules found"
fi

# Remove build artifacts
if [ -d "dist" ]; then
    echo "Removing dist..."
    rm -rf dist
    echo -e "${GREEN}✓${NC} dist removed"
fi

if [ -d ".vite" ]; then
    echo "Removing .vite cache..."
    rm -rf .vite
    echo -e "${GREEN}✓${NC} .vite cache removed"
fi

# Remove pnpm cache
if [ -d "node_modules/.cache" ]; then
    rm -rf node_modules/.cache
fi

# Remove .env (optional - commented out by default)
# if [ -f ".env" ]; then
#     echo "Removing .env file..."
#     rm .env
#     echo -e "${GREEN}✓${NC} .env file removed"
# fi

echo ""
echo -e "${BLUE}[3/4]${NC} Cleaning Docker..."
echo "-------------------------------------"

cd "$PROJECT_ROOT"

# Check if docker compose is available
if docker compose version >/dev/null 2>&1; then
    # Stop and remove containers
    if [ -f "docker-compose.dev.yaml" ]; then
        echo "Stopping Docker containers..."
        docker compose -f docker-compose.dev.yaml down -v 2>/dev/null || true
        echo -e "${GREEN}✓${NC} Docker containers stopped and volumes removed"
    else
        echo -e "${YELLOW}⚠${NC} docker-compose.dev.yaml not found"
    fi
else
    echo -e "${YELLOW}⚠${NC} docker compose not found, skipping Docker cleanup"
fi

echo ""
echo -e "${BLUE}[4/4]${NC} Cleaning Root Directory..."
echo "-------------------------------------"

# Remove any root-level cache directories
if [ -d ".pytest_cache" ]; then
    rm -rf .pytest_cache
    echo -e "${GREEN}✓${NC} Root .pytest_cache removed"
fi

echo ""
echo -e "${GREEN}✓✓✓${NC} Reset Complete!"
echo "================================================"
echo ""
echo "Your environment has been cleaned."
echo ""
echo "Next steps:"
echo "1. Run setup script to reinstall dependencies:"
echo "   ./scripts/setup-dependencies.sh"
echo "2. Or use VSCode task: 'Setup: Install All Dependencies'"
echo ""
echo "Clean slate achieved! 🧹"
