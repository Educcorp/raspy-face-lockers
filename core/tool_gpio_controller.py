"""
Control GPIO para herramientas (relay de interlock, ej. taladro).

Mismo patrón que core/gpio_controller.py (locker), pero en módulo aparte:
un canal por herramienta, activo-bajo, con fallback a pinctrl si RPi.GPIO
no está disponible. El relay NO switchea el AC de la herramienta directo —
habilita la bobina de un contactor/toma controlada; ese contactor es el que
switchea la corriente real hacia la herramienta.

Este módulo solo expone la activación del relay. La decisión de CUÁNDO
llamarlo (según permisos del usuario reconocido) vive en otro lado — este
archivo no valida permisos, solo mueve el pin.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time

from config import TOOL_GPIO_CONFIG

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
except Exception:  # pragma: no cover - útil para desarrollo fuera de Raspberry
    GPIO = None

# Mapeo nombre de herramienta → pin BCM. Agregar más entradas aquí (y en
# config.py TOOL_GPIO_CONFIG["pins"]) para futuras herramientas.
TOOL_PIN_MAP: dict[str, int] = {
    name: int(pin) for name, pin in TOOL_GPIO_CONFIG.get("pins", {}).items()
}


class ToolGPIOController:
    """Controla los relays de herramientas con activación activo-baja."""

    def __init__(self) -> None:
        self._pins = TOOL_PIN_MAP.copy()
        self._active_low = bool(TOOL_GPIO_CONFIG.get("relay_active_low", True))
        self._default_seconds = float(TOOL_GPIO_CONFIG.get("activation_seconds", 300))
        self._pinctrl_bin = shutil.which("pinctrl")
        self._setup_done = False
        self._backend = "none"
        self._setup_lock = threading.Lock()
        # Un lock por herramienta para poder activarse en paralelo sin bloquearse entre sí
        self._tool_locks: dict[str, threading.Lock] = {
            name: threading.Lock() for name in self._pins
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

            if not self._pins:
                logger.warning("ToolGPIOController sin herramientas configuradas (TOOL_GPIO_CONFIG['pins'] vacío)")
                return False

            if GPIO is not None:
                try:
                    GPIO.setwarnings(False)
                    GPIO.setmode(GPIO.BCM)
                    # Todos los relays arrancan en HIGH (inactivo) — evita disparos involuntarios.
                    for tool_name, pin in self._pins.items():
                        GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)
                        logger.info("GPIO inicializado: Herramienta '%s' → BCM pin %s", tool_name, pin)
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
                logger.info("GPIO inicializado con pinctrl para %d herramienta(s)", len(self._pins))
                return True

            logger.error("No hay backend GPIO funcional para los pines de herramientas")
            return False

    def activate_tool_by_id(self, tool_name: str | None, seconds: float | None = None) -> bool:
        """Activa el relay/contactor de la herramienta indicada durante `seconds`.

        Llamada BLOQUEANTE (duerme `seconds`) — igual que open_locker_by_id.
        Ejecútala en un thread aparte si no quieres bloquear el hilo que llama
        (así se usa en scanning_screen.py para los lockers).
        """
        hold_seconds = float(seconds if seconds is not None else self._default_seconds)
        if hold_seconds <= 0:
            hold_seconds = self._default_seconds

        if not tool_name:
            logger.warning("activate_tool_by_id: tool_name vacío, no se activa ningún relay")
            return False

        pin = self._pins.get(tool_name)
        if pin is None:
            logger.warning(
                "activate_tool_by_id: tool_name=%s sin pin asignado (mapa: %s)",
                tool_name, self._pins,
            )
            return False

        if not self._ensure_setup():
            return False

        tool_lock = self._tool_locks.get(tool_name)
        if tool_lock is None:
            logger.warning("Sin lock para tool_name=%s", tool_name)
            return False

        if not tool_lock.acquire(blocking=False):
            logger.info("Herramienta '%s' ya está activa, ignorando solicitud", tool_name)
            return False

        try:
            if self._backend == "rpi_gpio":
                active_value = GPIO.LOW if self._active_low else GPIO.HIGH
                inactive_value = GPIO.HIGH if self._active_low else GPIO.LOW
                GPIO.output(pin, active_value)
                logger.info("Herramienta '%s' activada (pin=%s) por %.2fs", tool_name, pin, hold_seconds)
                time.sleep(hold_seconds)
                GPIO.output(pin, inactive_value)
            elif self._backend == "pinctrl":
                if not self._pinctrl_write_pin(pin, active=True):
                    return False
                logger.info("Herramienta '%s' activada (pin=%s) por %.2fs", tool_name, pin, hold_seconds)
                time.sleep(hold_seconds)
                if not self._pinctrl_write_pin(pin, active=False):
                    return False
            else:
                logger.error("Backend GPIO desconocido: %s", self._backend)
                return False
        except Exception as exc:
            logger.error("Error activando relay de herramienta '%s' (pin=%s): %s", tool_name, pin, exc)
            return False
        finally:
            tool_lock.release()

        logger.info("Herramienta '%s' desactivada (pin=%s)", tool_name, pin)
        return True

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


_controller_instance: ToolGPIOController | None = None


def get_tool_gpio_controller() -> ToolGPIOController:
    """Retorna una instancia singleton del controlador GPIO de herramientas."""
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = ToolGPIOController()
    return _controller_instance
