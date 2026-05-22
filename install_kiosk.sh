#!/bin/bash
# ── Smart Locker – Instalador de modo kiosco ──────────────────────────────────
#
# Uso:  bash install_kiosk.sh
#
# Qué hace:
#   1. Hace ejecutables los scripts de arranque
#   2. Instala el autostart en ~/.config/autostart/ (Labwc / LXDE)
#   3. Instala la entrada en ~/.config/labwc/autostart (Labwc/Wayland, RPi Bookworm)
#   4. Instala el servicio systemd (como respaldo)
#   5. Verifica que el auto-login esté habilitado
# ─────────────────────────────────────────────────────────────────────────────

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_HOME="$HOME"
AUTOSTART_DIR="$USER_HOME/.config/autostart"
LABWC_DIR="$USER_HOME/.config/labwc"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC}  $1"; }
err()  { echo -e "${RED}✗${NC} $1"; }

echo ""
echo "════════════════════════════════════════════"
echo "   Smart Locker – Instalación modo kiosco"
echo "════════════════════════════════════════════"
echo "Directorio del proyecto: $PROJECT_DIR"
echo ""

# ── 1. Permisos de ejecución ──────────────────────────────────────────────────
chmod +x "$PROJECT_DIR/kiosk_autostart.sh"
ok "kiosk_autostart.sh es ejecutable"

mkdir -p "$PROJECT_DIR/logs"
ok "Directorio de logs creado"

# ── 2. XDG autostart (.desktop) ── funciona con LXDE y Labwc ─────────────────
mkdir -p "$AUTOSTART_DIR"

DESKTOP_FILE="$AUTOSTART_DIR/smart-locker.desktop"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=Smart Locker
Comment=Sistema de lockers con reconocimiento facial
Exec=$PROJECT_DIR/kiosk_autostart.sh
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=3
Hidden=false
NoDisplay=false
EOF

ok "XDG autostart instalado → $DESKTOP_FILE"

# ── 3. Labwc autostart (Wayland, RPi OS Bookworm) ────────────────────────────
mkdir -p "$LABWC_DIR"
LABWC_AUTOSTART="$LABWC_DIR/autostart"

# Eliminar entrada anterior si existe, luego agregar
if [ -f "$LABWC_AUTOSTART" ]; then
    sed -i '/smart-locker\|kiosk_autostart/d' "$LABWC_AUTOSTART"
fi

echo "$PROJECT_DIR/kiosk_autostart.sh &" >> "$LABWC_AUTOSTART"
ok "Labwc autostart instalado → $LABWC_AUTOSTART"

# ── 4. Systemd service (como respaldo adicional) ──────────────────────────────
SERVICE_SRC="$PROJECT_DIR/smart-locker.service"
SERVICE_DST="/etc/systemd/system/smart-locker.service"

if [ -f "$SERVICE_SRC" ]; then
    # Actualizar rutas en el .service con el directorio actual
    sed "s|/home/raspi/Documents/GitHub/raspy-face-lockers|$PROJECT_DIR|g" \
        "$SERVICE_SRC" > /tmp/smart-locker.service

    if sudo cp /tmp/smart-locker.service "$SERVICE_DST" 2>/dev/null; then
        sudo systemctl daemon-reload 2>/dev/null
        ok "Servicio systemd instalado (no habilitado — los métodos anteriores son suficientes)"
        echo "   Para usarlo: sudo systemctl enable --now smart-locker.service"
    else
        warn "No se pudo instalar el servicio systemd (sin sudo). Se usará solo el autostart."
    fi
fi

# ── 5. Verificar auto-login ──────────────────────────────────────────────────
CURRENT_USER="$(whoami)"
LIGHTDM_CONF="/etc/lightdm/lightdm.conf"

if grep -q "autologin-user=$CURRENT_USER" "$LIGHTDM_CONF" 2>/dev/null; then
    ok "Auto-login ya configurado para '$CURRENT_USER'"
else
    warn "Auto-login NO detectado para '$CURRENT_USER'."
    echo "   Ejecuta: sudo raspi-config"
    echo "   → System Options → Boot / Auto Login → Desktop Autologin"
fi

# ── Resumen ──────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════"
echo "   Instalación completada"
echo "════════════════════════════════════════════"
echo ""
echo "Métodos de autoarranque instalados:"
echo "  • XDG autostart:  $DESKTOP_FILE"
echo "  • Labwc autostart: $LABWC_AUTOSTART"
echo ""
echo "Para que surta efecto: reinicia la Raspberry Pi"
echo "  sudo reboot"
echo ""
echo "Para desinstalar el autoarranque:"
echo "  rm $DESKTOP_FILE"
echo "  sed -i '/kiosk_autostart/d' $LABWC_AUTOSTART"
echo ""
echo "Logs de arranque:"
echo "  tail -f $PROJECT_DIR/logs/kiosk_startup.log"
echo ""
