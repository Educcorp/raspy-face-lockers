"""Control GPIO para apertura de locker por relay activo bajo."""

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


class LockerGPIOController:
    """Controla un relay de locker con activacion activo-bajo."""

    def __init__(self) -> None:
        self._pin_m1 = int(GPIO_CONFIG.get("pin_locker_m1", 17))
        self._active_low = bool(GPIO_CONFIG.get("relay_active_low", True))
        self._default_open_seconds = float(GPIO_CONFIG.get("locker_open_seconds", 3.0))
        self._pinctrl_bin = shutil.which("pinctrl")
        self._setup_done = False
        self._backend = "none"
        self._lock = threading.Lock()

    def _pinctrl_level_token(self, active: bool) -> str:
        if self._active_low:
            return "dl" if active else "dh"
        return "dh" if active else "dl"

    def _pinctrl_write(self, active: bool) -> bool:
        if not self._pinctrl_bin:
            return False
        level = self._pinctrl_level_token(active)
        try:
            subprocess.run(
                [self._pinctrl_bin, "set", str(self._pin_m1), "op", level],
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except Exception as exc:
            logger.error("Error ejecutando pinctrl para pin=%s: %s", self._pin_m1, exc)
            return False

    def _ensure_setup(self) -> bool:
        if self._setup_done:
            return True

        if GPIO is not None:
            try:
                GPIO.setwarnings(False)
                GPIO.setmode(GPIO.BCM)
                # Mantener el relay inactivo al iniciar evita disparos involuntarios.
                GPIO.setup(self._pin_m1, GPIO.OUT, initial=GPIO.HIGH)
                self._setup_done = True
                self._backend = "rpi_gpio"
                logger.info("GPIO inicializado con RPi.GPIO en BCM pin=%s (M1)", self._pin_m1)
                return True
            except Exception as exc:
                logger.warning("RPi.GPIO no usable en este sistema (pin=%s): %s", self._pin_m1, exc)

        if self._pinctrl_write(active=False):
            self._setup_done = True
            self._backend = "pinctrl"
            logger.info("GPIO inicializado con pinctrl en BCM pin=%s (M1)", self._pin_m1)
            return True

        logger.error("No hay backend GPIO funcional para el pin BCM %s", self._pin_m1)
        return False

    def open_locker(self, seconds: float | None = None) -> bool:
        """Abre el locker M1 durante `seconds` y luego lo vuelve a cerrar."""
        hold_seconds = float(seconds if seconds is not None else self._default_open_seconds)
        if hold_seconds <= 0:
            hold_seconds = self._default_open_seconds

        with self._lock:
            if not self._ensure_setup():
                return False

            try:
                if self._backend == "rpi_gpio":
                    active_value = GPIO.LOW if self._active_low else GPIO.HIGH
                    inactive_value = GPIO.HIGH if self._active_low else GPIO.LOW
                    GPIO.output(self._pin_m1, active_value)
                    logger.info("Locker abierto en pin=%s por %.2fs", self._pin_m1, hold_seconds)
                    time.sleep(hold_seconds)
                    GPIO.output(self._pin_m1, inactive_value)
                elif self._backend == "pinctrl":
                    if not self._pinctrl_write(active=True):
                        return False
                    logger.info("Locker abierto en pin=%s por %.2fs", self._pin_m1, hold_seconds)
                    time.sleep(hold_seconds)
                    if not self._pinctrl_write(active=False):
                        return False
                else:
                    logger.error("Backend GPIO desconocido: %s", self._backend)
                    return False
            except Exception as exc:
                logger.error("Error activando relay del locker: %s", exc)
                return False

            logger.info("Locker cerrado en pin=%s", self._pin_m1)
            return True

    def cleanup(self) -> None:
        """Libera el pin usado por el relay para evitar estados flotantes."""
        if not self._setup_done:
            return

        with self._lock:
            try:
                if self._backend == "rpi_gpio" and GPIO is not None:
                    inactive_value = GPIO.HIGH if self._active_low else GPIO.LOW
                    GPIO.output(self._pin_m1, inactive_value)
                    GPIO.cleanup(self._pin_m1)
                elif self._backend == "pinctrl":
                    self._pinctrl_write(active=False)
            except Exception as exc:
                logger.warning("Error durante GPIO.cleanup en pin=%s: %s", self._pin_m1, exc)
            finally:
                self._setup_done = False
                self._backend = "none"


_controller_instance: LockerGPIOController | None = None


def get_locker_gpio_controller() -> LockerGPIOController:
    """Retorna una instancia singleton del controlador GPIO del locker."""
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = LockerGPIOController()
    return _controller_instance
