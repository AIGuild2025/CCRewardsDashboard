#!/usr/bin/env bash
# Quick setup script for development

set -e

echo "🚀 Credit Card Intelligence Platform - Setup"
echo "================================================"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "✓ Virtual environment ready"

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
playwright install chromium

# Create environment file
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file..."
    cp .env.example .env
    echo "⚠️  IMPORTANT: Edit .env with your configuration"
fi

# Create cache directories
mkdir -p cache/fingerprints logs screenshots

# Run tests
echo "🧪 Running tests..."
pytest tests/ -q || true

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your configuration"
echo "  2. Run: python scheduler/run_pipeline.py --bank Chase"
echo ""
echo "For more info, see README.md and GETTING_STARTED.md"
