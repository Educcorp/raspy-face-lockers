"""
Entry point del Smart Locker System.

Uso:
    python main.py --mode admin    →  Panel de administración (escritorio)
    python main.py --mode locker   →  Pantalla física del locker (800×480 px)
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


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

    if args.mode == "locker":
        from ui.app import LockerApp
        LockerApp().mainloop()

    elif args.mode == "admin":
        # TODO: implementar AdminApp
        from ui.app import LockerApp   # placeholder hasta tener AdminApp
        LockerApp().mainloop()


if __name__ == "__main__":
    main()

