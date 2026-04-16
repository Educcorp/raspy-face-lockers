"""Prueba rapida de relay M1 en GPIO 17 (activo bajo)."""

import shutil
import subprocess
import time

try:
    import RPi.GPIO as GPIO
except Exception:
    GPIO = None

PIN = 17
PINCTRL_BIN = shutil.which("pinctrl")


def _pinctrl_write(active: bool) -> None:
    if not PINCTRL_BIN:
        raise RuntimeError("pinctrl no disponible en el sistema")
    level = "dl" if active else "dh"  # Relay activo-bajo
    subprocess.run(
        [PINCTRL_BIN, "set", str(PIN), "op", level],
        check=True,
        capture_output=True,
        text=True,
    )


def _setup_backend() -> str:
    if GPIO is not None:
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(PIN, GPIO.OUT, initial=GPIO.HIGH)
            return "rpi_gpio"
        except Exception:
            pass
    _pinctrl_write(active=False)
    return "pinctrl"


def abrir_locker(segundos: float = 3.0, backend: str = "rpi_gpio") -> None:
    if backend == "rpi_gpio":
        GPIO.output(PIN, GPIO.LOW)  # Activo bajo = abre
        time.sleep(segundos)
        GPIO.output(PIN, GPIO.HIGH)  # Cierra
        return

    _pinctrl_write(active=True)
    time.sleep(segundos)
    _pinctrl_write(active=False)


def _cleanup(backend: str) -> None:
    if backend == "rpi_gpio" and GPIO is not None:
        GPIO.cleanup(PIN)
        return
    if backend == "pinctrl":
        _pinctrl_write(active=False)


if __name__ == "__main__":
    selected_backend = _setup_backend()
    print(f"Backend GPIO en uso: {selected_backend}")
    try:
        abrir_locker(3, backend=selected_backend)
    finally:
        _cleanup(selected_backend)
