#!/bin/bash
# ── Smart Locker – Arranque automático en modo kiosco ────────────────────────
#
# Para activar el autoarranque en Raspberry Pi OS:
#
#   cp smart-locker.desktop ~/.config/autostart/smart-locker.desktop
#   chmod +x kiosk_autostart.sh
#
# Para instalar como servicio de systemd (arranque sin escritorio):
#
#   sudo cp smart-locker.service /etc/systemd/system/
#   sudo systemctl enable smart-locker.service
#   sudo systemctl start  smart-locker.service
# ─────────────────────────────────────────────────────────────────────────────

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Esperar a que el entorno gráfico X11 esté disponible
MAX_WAIT=30
WAITED=0
while [ -z "$DISPLAY" ] || ! xdpyinfo -display "$DISPLAY" > /dev/null 2>&1; do
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "[kiosk] ERROR: X11 no disponible tras ${MAX_WAIT}s"
        exit 1
    fi
    export DISPLAY=:0
    sleep 1
    WAITED=$((WAITED + 1))
done

echo "[kiosk] X11 listo en DISPLAY=$DISPLAY"

# Ocultar el cursor del ratón en modo kiosco (requiere: sudo apt install unclutter)
if command -v unclutter > /dev/null 2>&1; then
    unclutter -idle 0.1 -root &
fi

# Elegir intérprete Python:
# picamera2 requiere Python del sistema en RPi — intentar primero el del venv
PYTHON_VENV="$PROJECT_DIR/venv/bin/python3"
PYTHON_SYS="/usr/bin/python3"

# Verificar si el venv tiene picamera2 o si está en el sistema
if "$PYTHON_VENV" -c "import picamera2" 2>/dev/null; then
    PYTHON="$PYTHON_VENV"
    echo "[kiosk] Usando Python del venv (tiene picamera2)"
elif "$PYTHON_SYS" -c "import picamera2" 2>/dev/null; then
    PYTHON="$PYTHON_SYS"
    echo "[kiosk] Usando Python del sistema (picamera2 en sistema)"
elif [ -f "$PYTHON_VENV" ]; then
    PYTHON="$PYTHON_VENV"
    echo "[kiosk] Usando Python del venv (sin picamera2 — modo simulado)"
else
    PYTHON="$PYTHON_SYS"
    echo "[kiosk] Usando Python del sistema"
fi

# Asegurar que el sitio del sistema esté accesible para picamera2
export PYTHONPATH="/usr/lib/python3/dist-packages:$PYTHONPATH"

echo "[kiosk] Lanzando Smart Locker con $PYTHON"
exec "$PYTHON" "$PROJECT_DIR/main.py" --mode locker
