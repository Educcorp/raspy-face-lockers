#!/bin/bash
# ── Smart Locker – Script de arranque en modo kiosco ─────────────────────────
#
# Compatible con:
#   • Raspberry Pi OS Bookworm con Labwc (Wayland) + XWayland  ← caso actual
#   • Raspberry Pi OS Bullseye con LXDE (X11 puro)
#
# El script garantiza que el entorno gráfico esté listo antes de lanzar
# la aplicación Tkinter (que necesita DISPLAY=:0 vía XWayland).
# ─────────────────────────────────────────────────────────────────────────────

set -e

# Evitar doble arranque si el compositor o autostart lo dispara 2 veces.
exec 9>/tmp/smart-locker.lock
if ! flock -n 9; then
    echo "Otra instancia ya esta en ejecucion. Saliendo."
    exit 0
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$PROJECT_DIR/logs/kiosk_startup.log"
mkdir -p "$PROJECT_DIR/logs"

exec >> "$LOG" 2>&1
echo "=== $(date) — Arranque kiosco ==="
echo "SESSION_TYPE=$XDG_SESSION_TYPE  DISPLAY=$DISPLAY  WAYLAND=$WAYLAND_DISPLAY"

# ── 1. Variables de entorno para XWayland / X11 ───────────────────────────────
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

# Tkinter necesita X11. En sesiones Wayland usa XWayland.
# GDK_BACKEND=x11 garantiza que GTK (usado internamente por algunas deps) tampoco
# intente conectarse a Wayland directamente.
export GDK_BACKEND=x11
export QT_QPA_PLATFORM=xcb

# ── 2. Esperar a que Wayland esté completamente listo ────────────────────────
# En RPi OS Bookworm con Labwc, XWayland se inicia on-demand cuando el primer
# cliente X11 se conecta. Esperamos primero a que el socket Wayland exista.
echo "Esperando sesión Wayland ($WAYLAND_DISPLAY) ..."
MAX_WAIT=30
for i in $(seq 1 $MAX_WAIT); do
    if [ -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]; then
        echo "Wayland listo tras ${i}s"
        break
    fi
    if [ $i -eq $MAX_WAIT ]; then
        echo "ERROR: Wayland no disponible tras ${MAX_WAIT}s — abortando"
        exit 1
    fi
    sleep 1
done

# Pausa adicional para que Labwc termine de inicializarse y levante XWayland
sleep 3

# ── 3. Esperar a que XWayland (DISPLAY=:0) esté disponible ───────────────────
echo "Esperando XWayland en DISPLAY=$DISPLAY ..."
MAX_WAIT=30
for i in $(seq 1 $MAX_WAIT); do
    if xdpyinfo -display "$DISPLAY" > /dev/null 2>&1; then
        echo "XWayland listo tras ${i}s"
        break
    fi
    if [ $i -eq $MAX_WAIT ]; then
        # XWayland puede necesitar que un cliente X11 lo despierte — intentar con xset
        DISPLAY="$DISPLAY" xset q > /dev/null 2>&1 || true
        sleep 2
        if ! xdpyinfo -display "$DISPLAY" > /dev/null 2>&1; then
            echo "ERROR: XWayland no disponible tras ${MAX_WAIT}s"
            exit 1
        fi
    fi
    sleep 1
done

# ── 3. Ocultar cursor (mejora la experiencia kiosco táctil) ──────────────────
if command -v unclutter > /dev/null 2>&1; then
    unclutter -idle 0.5 -root &
    echo "unclutter iniciado"
fi

# ── 4. Elegir Python: priorizar el del sistema para picamera2 ───────────────
VENV_PY="$PROJECT_DIR/venv/bin/python3"
SYS_PY="/usr/bin/python3"

if "$SYS_PY" -c "import picamera2" 2>/dev/null; then
    PYTHON="$SYS_PY"
    echo "Python: sistema (con picamera2)"
elif [ -f "$VENV_PY" ] && "$VENV_PY" -c "import picamera2" 2>/dev/null; then
    PYTHON="$VENV_PY"
    echo "Python: venv (con picamera2)"
elif [ -f "$VENV_PY" ]; then
    PYTHON="$VENV_PY"
    echo "Python: venv (sin picamera2 — modo simulado)"
else
    PYTHON="$SYS_PY"
    echo "Python: sistema"
fi

# Asegurar acceso a paquetes del sistema (picamera2 vive en site-packages del sistema)
export PYTHONPATH="/usr/lib/python3/dist-packages:${PYTHONPATH:-}"

# Esperar a que el dispositivo de camara aparezca tras el boot
CAMERA_DEV="/dev/video0"
if [ ! -e "$CAMERA_DEV" ]; then
    echo "Esperando dispositivo de camara ($CAMERA_DEV) ..."
    for i in $(seq 1 12); do
        if [ -e "$CAMERA_DEV" ]; then
            echo "Camara disponible tras ${i}s"
            break
        fi
        sleep 1
    done
fi

# ── 5. Lanzar el sistema ─────────────────────────────────────────────────────
echo "Lanzando: $PYTHON $PROJECT_DIR/main.py --mode locker"
cd "$PROJECT_DIR"
exec "$PYTHON" main.py --mode locker
