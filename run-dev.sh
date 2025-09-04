#!/bin/bash
# Development server runner for Erik Image Manager

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Erik Image Manager Development Server${NC}"
echo "=================================================="

# Check if virtual environment exists
if [ ! -d "dev-venv" ]; then
    echo -e "${RED}❌ Virtual environment not found. Please run setup first.${NC}"
    exit 1
fi

# Check if requirements are installed
if ! ./dev-venv/bin/python -c "import flask, numpy, matplotlib, trimesh" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Installing/updating dependencies...${NC}"
    ./dev-venv/bin/pip install -r requirements-image-manager.txt
fi

# Source environment configuration
if [ -f "dev-config.env" ]; then
    echo -e "${GREEN}📝 Loading development configuration...${NC}"
    source dev-config.env
else
    echo -e "${RED}❌ dev-config.env not found${NC}"
    exit 1
fi

# Create directories if they don't exist
mkdir -p "$ERIK_IMAGES_FOLDER"
mkdir -p "$MESH_FOLDER"
mkdir -p "$(dirname $FRIGATE_CONFIG_PATH)"

echo -e "${GREEN}🔧 Configuration:${NC}"
echo "   • Erik Images: $ERIK_IMAGES_FOLDER"
echo "   • Meshes: $MESH_FOLDER"
echo "   • Frigate Config: $FRIGATE_CONFIG_PATH"
echo "   • Development URL: http://localhost:$DEV_PORT"
echo ""

# Check if production container is running on same port
if netstat -tuln 2>/dev/null | grep -q ":9000 "; then
    echo -e "${YELLOW}⚠️  Production container detected on port 9000${NC}"
    echo -e "${YELLOW}   Development server will run on port $DEV_PORT${NC}"
    echo ""
fi

# Start development server
echo -e "${GREEN}🌟 Starting Flask development server...${NC}"
echo "   Press Ctrl+C to stop"
echo ""

# Activate venv and run
source dev-venv/bin/activate
python run.py --dev --port $DEV_PORT --host $DEV_HOST