"""GPIO inputs for door limit switches (KW11-3Z)."""

from __future__ import annotations

import logging
import threading

from config import DOOR_SWITCH_CONFIG

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
except Exception:  # pragma: no cover - dev env
    GPIO = None


class DoorSwitchController:
    """Manage door limit switch GPIO inputs with pull-down."""

    def __init__(self) -> None:
        self._pins: dict[int, int] = {
            int(k): int(v) for k, v in DOOR_SWITCH_CONFIG.get("pins", {}).items()
        }
        self._setup_done = False
        self._setup_lock = threading.Lock()
        self._available = GPIO is not None

    def is_available(self) -> bool:
        return self._available

    def ensure_setup(self) -> bool:
        return self._ensure_setup()

    def _ensure_setup(self) -> bool:
        if self._setup_done:
            return True

        if not self._available:
            return False

        with self._setup_lock:
            if self._setup_done:
                return True
            try:
                GPIO.setwarnings(False)
                GPIO.setmode(GPIO.BCM)
                for locker_id, pin in self._pins.items():
                    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                    logger.info("GPIO switch init: Locker %s -> BCM %s", locker_id, pin)
                self._setup_done = True
                return True
            except Exception as exc:
                logger.warning("No se pudo inicializar switches: %s", exc)
                self._available = False
                return False

    def read_state(self, locker_id: int) -> bool | None:
        """Return True if door is closed (HIGH), False if open (LOW), None if unavailable."""
        if not self._ensure_setup():
            return None

        pin = self._pins.get(int(locker_id))
        if pin is None:
            logger.warning("Switch read: locker_id=%s sin pin asignado", locker_id)
            return None

        try:
            return bool(GPIO.input(pin))
        except Exception as exc:
            logger.warning("Error leyendo switch pin=%s: %s", pin, exc)
            return None


_controller_instance: DoorSwitchController | None = None


def get_door_switch_controller() -> DoorSwitchController:
    """Singleton for door switch controller."""
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = DoorSwitchController()
    return _controller_instance
