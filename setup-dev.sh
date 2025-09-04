#!/bin/bash
# One-time setup for development environment

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Setting up Erik Image Manager Development Environment${NC}"
echo "========================================================="

# Create virtual environment if it doesn't exist
if [ ! -d "dev-venv" ]; then
    echo -e "${GREEN}📦 Creating Python virtual environment...${NC}"
    python3 -m venv dev-venv
fi

# Install/update dependencies
echo -e "${GREEN}📚 Installing dependencies...${NC}"
./dev-venv/bin/pip install --upgrade pip
./dev-venv/bin/pip install -r requirements-image-manager.txt

# Make sure directories exist
source dev-config.env
mkdir -p "$ERIK_IMAGES_FOLDER"
mkdir -p "$MESH_FOLDER"
mkdir -p "$(dirname $FRIGATE_CONFIG_PATH)"

echo ""
echo -e "${GREEN}✅ Development environment ready!${NC}"
echo ""
echo "Usage:"
echo "  ./run-dev.sh    # Start development server"
echo "  ./setup-dev.sh  # Re-run this setup if needed"
echo ""
echo "Development server will run on: http://localhost:9001"
echo "Production container runs on:   http://localhost:9000"