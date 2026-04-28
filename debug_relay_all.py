"""Prueba los 4 relays del HW-316 uno por uno (activo bajo, BCM)."""

import shutil
import subprocess
import sys
import time

try:
    import RPi.GPIO as GPIO
except Exception:
    GPIO = None

# idLocker → pin BCM (igual que LOCKER_PIN_MAP en gpio_controller.py)
LOCKERS = {
    1: 17,  # IN1 → M1
    2: 27,  # IN2 → M2
    3: 22,  # IN3 → M3
    4: 23,  # IN4 → M4
}

PINCTRL_BIN = shutil.which("pinctrl")
HOLD_SECONDS = 3.0


def _pinctrl_write(pin: int, active: bool) -> None:
    if not PINCTRL_BIN:
        raise RuntimeError("pinctrl no encontrado en el sistema")
    level = "dl" if active else "dh"  # activo-bajo
    subprocess.run(
        [PINCTRL_BIN, "set", str(pin), "op", level],
        check=True, capture_output=True, text=True,
    )


def setup_all() -> str:
    if GPIO is not None:
        try:
            GPIO.setmode(GPIO.BCM)
            for locker_id, pin in LOCKERS.items():
                GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)
                print(f"  [OK] Locker {locker_id} → BCM {pin} inicializado en HIGH (cerrado)")
            return "rpi_gpio"
        except Exception as exc:
            print(f"  [WARN] RPi.GPIO falló: {exc} — usando pinctrl")
    for locker_id, pin in LOCKERS.items():
        _pinctrl_write(pin, active=False)
        print(f"  [OK] Locker {locker_id} → BCM {pin} inicializado en HIGH (cerrado)")
    return "pinctrl"


def open_relay(pin: int, backend: str) -> None:
    if backend == "rpi_gpio":
        GPIO.output(pin, GPIO.LOW)
        time.sleep(HOLD_SECONDS)
        GPIO.output(pin, GPIO.HIGH)
    else:
        _pinctrl_write(pin, active=True)
        time.sleep(HOLD_SECONDS)
        _pinctrl_write(pin, active=False)


def cleanup_all(backend: str) -> None:
    if backend == "rpi_gpio" and GPIO is not None:
        for pin in LOCKERS.values():
            GPIO.output(pin, GPIO.HIGH)
        GPIO.cleanup(list(LOCKERS.values()))
    else:
        for pin in LOCKERS.values():
            _pinctrl_write(pin, active=False)


def test_single(locker_id: int, backend: str) -> None:
    pin = LOCKERS[locker_id]
    print(f"\n>>> Abriendo Locker {locker_id} (BCM {pin}) por {HOLD_SECONDS}s ...")
    open_relay(pin, backend)
    print(f"    Locker {locker_id} cerrado.")


def test_sequence(backend: str) -> None:
    print("\n=== Prueba secuencial M1 → M2 → M3 → M4 ===")
    for locker_id in sorted(LOCKERS.keys()):
        test_single(locker_id, backend)
        time.sleep(1.0)


if __name__ == "__main__":
    print("=== Debug relay HW-316 — 4 canales ===\n")
    print("Inicializando pines (todos en HIGH = cerrados):")
    backend = setup_all()
    print(f"\nBackend activo: {backend}")

    # Si se pasa un número de locker como argumento, prueba solo ese
    if len(sys.argv) == 2 and sys.argv[1].isdigit():
        locker_arg = int(sys.argv[1])
        if locker_arg not in LOCKERS:
            print(f"[ERROR] Locker {locker_arg} no existe. Opciones: {list(LOCKERS.keys())}")
            sys.exit(1)
        try:
            test_single(locker_arg, backend)
        finally:
            cleanup_all(backend)
    else:
        # Sin argumento: prueba los 4 en secuencia
        try:
            test_sequence(backend)
        finally:
            cleanup_all(backend)

    print("\n[OK] GPIO limpiado. Fin de prueba.")
