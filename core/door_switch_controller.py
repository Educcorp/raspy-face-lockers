"""GPIO inputs for door limit switches (KW11-3Z)."""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time

from config import DOOR_SWITCH_CONFIG

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
except Exception:  # pragma: no cover - dev env
    GPIO = None


# RPi.GPIO 0.7.x no soporta la Raspberry Pi 5 ("Cannot determine SOC peripheral
# base address"); ahí se leen los sensores con `pinctrl`, igual que los relés.
_PINCTRL_CACHE_TTL_S = 0.1


class DoorSwitchController:
    """Manage door limit switch GPIO inputs with pull-down."""

    def __init__(self) -> None:
        self._pins: dict[int, int] = {
            int(k): int(v) for k, v in DOOR_SWITCH_CONFIG.get("pins", {}).items()
        }
        self._setup_done = False
        self._setup_lock = threading.Lock()
        self._available = GPIO is not None
        self._pinctrl_bin = shutil.which("pinctrl")
        self._backend = "none"
        self._pinctrl_levels: dict[int, bool] = {}
        self._pinctrl_read_ts = 0.0
        self._pinctrl_lock = threading.Lock()
        if not self._available and self._pinctrl_bin:
            self._available = True  # se resolverá en _ensure_setup

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

            if GPIO is not None:
                try:
                    GPIO.setwarnings(False)
                    GPIO.setmode(GPIO.BCM)
                    for locker_id, pin in self._pins.items():
                        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                        logger.info("GPIO switch init: Locker %s -> BCM %s", locker_id, pin)
                    self._setup_done = True
                    self._backend = "rpi_gpio"
                    return True
                except Exception as exc:
                    logger.warning("RPi.GPIO no usable para switches: %s", exc)

            if self._pinctrl_bin and self._setup_pinctrl():
                self._setup_done = True
                self._backend = "pinctrl"
                logger.info("GPIO switches inicializados con pinctrl (%d lockers)", len(self._pins))
                return True

            logger.warning("No se pudo inicializar switches: sin backend GPIO funcional")
            self._available = False
            return False

    def _setup_pinctrl(self) -> bool:
        """Deja los pines de los sensores como entrada con pull-down (mismo modo que RPi.GPIO)."""
        try:
            for pin in self._pins.values():
                subprocess.run(
                    [self._pinctrl_bin, "set", str(pin), "ip", "pd"],
                    check=True, capture_output=True, text=True,
                )
            return True
        except Exception as exc:
            logger.warning("pinctrl no pudo configurar switches: %s", exc)
            return False

    def _pinctrl_read(self, pin: int) -> bool | None:
        """Lee todos los pines de sensores con UNA llamada a pinctrl (cache 100ms)."""
        with self._pinctrl_lock:
            now = time.monotonic()
            if now - self._pinctrl_read_ts >= _PINCTRL_CACHE_TTL_S:
                try:
                    out = subprocess.run(
                        [self._pinctrl_bin, "get", ",".join(str(p) for p in self._pins.values())],
                        check=True, capture_output=True, text=True, timeout=2,
                    ).stdout
                except Exception as exc:
                    logger.warning("Error leyendo switches con pinctrl: %s", exc)
                    self._pinctrl_levels = {}
                    return None
                levels: dict[int, bool] = {}
                for line in out.splitlines():
                    # Ej: " 5: ip    pd | hi // GPIO5 = input"
                    head, sep, tail = line.partition("|")
                    if not sep:
                        continue
                    try:
                        gpio = int(head.split(":", 1)[0])
                    except ValueError:
                        continue
                    token = tail.split("//", 1)[0].strip()
                    if token in ("hi", "lo"):
                        levels[gpio] = token == "hi"
                self._pinctrl_levels = levels
                self._pinctrl_read_ts = now
            return self._pinctrl_levels.get(pin)

    def read_state(self, locker_id: int) -> bool | None:
        """Return True if door is closed (HIGH), False if open (LOW), None if unavailable."""
        if not self._ensure_setup():
            return None

        pin = self._pins.get(int(locker_id))
        if pin is None:
            logger.warning("Switch read: locker_id=%s sin pin asignado", locker_id)
            return None

        if self._backend == "pinctrl":
            return self._pinctrl_read(pin)

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
