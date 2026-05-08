"""Control GPIO para apertura de lockers por relay activo bajo."""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time

from config import GPIO_CONFIG

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
except Exception:  # pragma: no cover - útil para desarrollo fuera de Raspberry
    GPIO = None

# Mapeo idLocker (1-4) → pin BCM. Coincide con los canales M1-M4 del HW-316.
LOCKER_PIN_MAP: dict[int, int] = {
    1: int(GPIO_CONFIG.get("pin_locker_m1", 17)),
    2: int(GPIO_CONFIG.get("pin_locker_m2", 27)),
    3: int(GPIO_CONFIG.get("pin_locker_m3", 22)),
    4: int(GPIO_CONFIG.get("pin_locker_m4", 23)),
}


class LockerGPIOController:
    """Controla los 4 relays del HW-316 con activacion activo-bajo."""

    def __init__(self) -> None:
        self._pins = LOCKER_PIN_MAP.copy()
        self._active_low = bool(GPIO_CONFIG.get("relay_active_low", True))
        self._default_open_seconds = float(GPIO_CONFIG.get("locker_open_seconds", 3.0))
        self._pinctrl_bin = shutil.which("pinctrl")
        self._setup_done = False
        self._backend = "none"
        self._setup_lock = threading.Lock()
        # Un lock por locker para que puedan abrirse en paralelo sin bloquearse entre sí
        self._locker_locks: dict[int, threading.Lock] = {
            lid: threading.Lock() for lid in self._pins
        }

    def _pinctrl_level_token(self, active: bool) -> str:
        if self._active_low:
            return "dl" if active else "dh"
        return "dh" if active else "dl"

    def _pinctrl_write_pin(self, pin: int, active: bool) -> bool:
        if not self._pinctrl_bin:
            return False
        level = self._pinctrl_level_token(active)
        try:
            subprocess.run(
                [self._pinctrl_bin, "set", str(pin), "op", level],
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except Exception as exc:
            logger.error("Error ejecutando pinctrl para pin=%s: %s", pin, exc)
            return False

    def _ensure_setup(self) -> bool:
        if self._setup_done:
            return True

        with self._setup_lock:
            if self._setup_done:
                return True

            if GPIO is not None:
                try:
                    GPIO.setwarnings(False)
                    GPIO.setmode(GPIO.BCM)
                    # Todos los relays arrancan en HIGH (inactivo) — evita disparos involuntarios.
                    for locker_id, pin in self._pins.items():
                        GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)
                        logger.info("GPIO inicializado: Locker %s → BCM pin %s", locker_id, pin)
                    self._setup_done = True
                    self._backend = "rpi_gpio"
                    return True
                except Exception as exc:
                    logger.warning("RPi.GPIO no usable: %s", exc)

            # Fallback pinctrl: poner todos en HIGH (inactivo)
            all_ok = all(
                self._pinctrl_write_pin(pin, active=False)
                for pin in self._pins.values()
            )
            if all_ok:
                self._setup_done = True
                self._backend = "pinctrl"
                logger.info("GPIO inicializado con pinctrl para %d lockers", len(self._pins))
                return True

            logger.error("No hay backend GPIO funcional para los pines de locker")
            return False

    def open_locker_by_id(self, locker_id: int | None, seconds: float | None = None) -> bool:
        """Activa el relay del locker indicado por `locker_id` durante `seconds`."""
        hold_seconds = float(seconds if seconds is not None else self._default_open_seconds)
        if hold_seconds <= 0:
            hold_seconds = self._default_open_seconds

        if locker_id is None:
            logger.warning("open_locker_by_id: locker_id es None, no se activa ningún relay")
            return False

        pin = self._pins.get(int(locker_id))
        if pin is None:
            logger.warning(
                "open_locker_by_id: locker_id=%s sin pin asignado (mapa: %s)",
                locker_id, self._pins,
            )
            return False

        if not self._ensure_setup():
            return False

        locker_lock = self._locker_locks.get(int(locker_id))
        if locker_lock is None:
            logger.warning("Sin lock para locker_id=%s", locker_id)
            return False

        if not locker_lock.acquire(blocking=False):
            logger.info("Locker %s ya está en proceso de apertura, ignorando solicitud", locker_id)
            return False

        try:
            if self._backend == "rpi_gpio":
                active_value = GPIO.LOW if self._active_low else GPIO.HIGH
                inactive_value = GPIO.HIGH if self._active_low else GPIO.LOW
                GPIO.output(pin, active_value)
                logger.info("Locker %s abierto (pin=%s) por %.2fs", locker_id, pin, hold_seconds)
                time.sleep(hold_seconds)
                GPIO.output(pin, inactive_value)
            elif self._backend == "pinctrl":
                if not self._pinctrl_write_pin(pin, active=True):
                    return False
                logger.info("Locker %s abierto (pin=%s) por %.2fs", locker_id, pin, hold_seconds)
                time.sleep(hold_seconds)
                if not self._pinctrl_write_pin(pin, active=False):
                    return False
            else:
                logger.error("Backend GPIO desconocido: %s", self._backend)
                return False
        except Exception as exc:
            logger.error("Error activando relay Locker %s (pin=%s): %s", locker_id, pin, exc)
            return False
        finally:
            locker_lock.release()

        logger.info("Locker %s cerrado (pin=%s)", locker_id, pin)
        return True

    def open_locker(self, seconds: float | None = None) -> bool:
        """Compatibilidad hacia atrás: abre el Locker 1 (M1, pin 17)."""
        return self.open_locker_by_id(1, seconds)

    def cleanup(self) -> None:
        """Libera todos los pines para evitar estados flotantes."""
        if not self._setup_done:
            return

        with self._setup_lock:
            try:
                if self._backend == "rpi_gpio" and GPIO is not None:
                    inactive_value = GPIO.HIGH if self._active_low else GPIO.LOW
                    for pin in self._pins.values():
                        GPIO.output(pin, inactive_value)
                    GPIO.cleanup(list(self._pins.values()))
                elif self._backend == "pinctrl":
                    for pin in self._pins.values():
                        self._pinctrl_write_pin(pin, active=False)
            except Exception as exc:
                logger.warning("Error durante GPIO.cleanup: %s", exc)
            finally:
                self._setup_done = False
                self._backend = "none"


_controller_instance: LockerGPIOController | None = None


def get_locker_gpio_controller() -> LockerGPIOController:
    """Retorna una instancia singleton del controlador GPIO de lockers."""
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = LockerGPIOController()
    return _controller_instance
