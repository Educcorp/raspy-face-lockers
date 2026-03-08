#!/bin/bash
# Convenience script to run Smart Locker with proper Python environment
# 
# On Raspberry Pi, picamera2 is installed in system Python and
# not easily installable via pip. This script ensures proper access.

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if we should use system Python or venv
USE_SYSTEM_PYTHON=false

if [ "$1" == "--system" ]; then
    USE_SYSTEM_PYTHON=true
    shift
fi

# Check if venv exists
if [ -d "venv" ] && [ "$USE_SYSTEM_PYTHON" != "true" ]; then
    echo -e "${BLUE}Usando virtual environment...${NC}"
    source venv/bin/activate
elif [ -d "venv" ] && python3 -c "import picamera2" 2>/dev/null; then
    echo -e "${BLUE}Sistema Python detectado con picamera2${NC}"
    USE_SYSTEM_PYTHON=false
else
    if [ -d "venv" ]; then
        echo -e "${YELLOW}Advertencia: usando Python del sistema (venv no tiene picamera2)${NC}"
    fi
    USE_SYSTEM_PYTHON=true
fi

# Ensure DISPLAY is set (for headless systems with X11)
if [ -z "$DISPLAY" ] && [ -e /tmp/.X11-unix/0 ]; then
    export DISPLAY=:0
fi

echo -e "${GREEN}Iniciando Smart Locker System...${NC}"
echo "Modo: ${1:-locker}"
echo ""

if [ $# -eq 0 ]; then
    echo -e "${BLUE}Uso: ./run.sh [--mode locker|admin] [--system]${NC}"
    echo ""
    echo "Ejemplos:"
    echo "  ./run.sh --mode locker    # Pantalla física (por defecto)"
    echo "  ./run.sh --mode admin     # Panel de administración"
    echo "  ./run.sh --system         # Usar Python del sistema"
    echo ""
    python3 main.py --mode locker
else
    python3 main.py "$@"
fi
