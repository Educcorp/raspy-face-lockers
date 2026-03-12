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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/locker_system.log', mode='a'),
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

