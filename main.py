"""
Entry point del Smart Locker System.

Uso:
    python main.py --mode admin    →  Panel de administración (escritorio)
    python main.py --mode locker   →  Pantalla física del locker (800×480 px)
"""

import argparse
import sys
import os
import logging
import io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Garantiza que exista el directorio de logs antes de crear FileHandler.
os.makedirs('logs', exist_ok=True)

# En Windows la consola usa cp1252 por defecto y no puede mostrar emojis Unicode.
# Forzar UTF-8 en stdout para evitar UnicodeEncodeError.
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/locker_system.log', mode='a', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Pre-load camera dependencies to avoid GUI threading issues
def _preload_camera() -> None:
    """Pre-cargar dependencias de cámara antes de iniciar la GUI."""
    logger.info("Pre-cargando dependencias de cámara...")
    try:
        # Intentar cargar picamera2 del sistema
        import importlib.util
        spec = importlib.util.find_spec("picamera2")
        if spec is not None:
            logger.info("✓ picamera2 disponible en el sistema")
    except Exception as e:
        logger.warning(f"Advertencia al pre-cargar: {e}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smart Locker System")
    parser.add_argument(
        "--mode",
        choices=["admin", "locker"],
        required=True,
        help="Modo de ejecución: 'admin' o 'locker'",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger.info(f"Starting app in {args.mode} mode...")
    
    # Pre-cargar dependencias de cámara
    _preload_camera()

    if args.mode == "locker":
        from ui.app import LockerApp
        LockerApp().mainloop()

    elif args.mode == "admin":
        from ui.admin_app import AdminApp
        AdminApp().mainloop()


if __name__ == "__main__":
    main()

