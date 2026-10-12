#!/bin/bash
#
# Linguard Backend Setup Script
# This script sets up the development environment for Linguard backend
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_ROOT/backend/.venv"

echo "🔧 Linguard Backend Setup"
echo "========================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✅ Python3 found: $(python3 --version)"
echo ""

# Create virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists at $VENV_DIR"
fi

echo ""

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "🔧 Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📦 Installing dependencies from requirements.txt..."
pip install -r "$PROJECT_ROOT/backend/requirements.txt"

# Install CLI
echo "📦 Installing Linguard CLI..."
cd "$PROJECT_ROOT/backend/src/linguard_cli"
pip install -e .

# Verify installation
echo ""
echo "✅ Verifying installation..."
python -c "import fastapi; import uvicorn; print('✅ Backend dependencies: OK')"

cd "$PROJECT_ROOT/backend/src/linguard_cli"
python -c "from linguard_cli.main import cli; print('✅ CLI: OK')"

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📚 Next steps:"
echo "   1. Create .env file in backend/ directory:"
echo "      DATABASE_URL=sqlite:///./linguard.db"
echo "      SECRET_KEY=your-secret-key-here"
echo ""
echo "   2. Activate virtual environment:"
echo "      source backend/.venv/bin/activate"
echo ""
echo "   3. Run backend:"
echo "      cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "   4. Use CLI:"
echo "      linguard --help"
echo ""

# Deactivate
deactivate
