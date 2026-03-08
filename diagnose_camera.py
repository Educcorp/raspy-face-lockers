#!/usr/bin/env python3
"""
Diagnostic script para verificar la configuración de cámara en Raspberry Pi.

Uso: python diagnose_camera.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"✓ {text}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"✗ {text}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"ℹ {text}")


def check_imports() -> bool:
    """Check if required Python packages are installed."""
    print_header("1. VERIFICANDO IMPORTS")

    packages = {
        "cv2": "OpenCV",
        "customtkinter": "CustomTkinter",
        "numpy": "NumPy",
    }

    all_ok = True
    for module_name, display_name in packages.items():
        try:
            __import__(module_name)
            print_success(f"{display_name} instalado")
        except ImportError:
            print_error(f"{display_name} NO INSTALADO")
            all_ok = False

    # Check optional packages
    print_info("Paquetes opcionales:")
    optional = {
        "picamera2": "Picamera2 (Raspberry Pi nueva generación)",
        "dlib": "DLib (reconocimiento avanzado)",
        "mediapipe": "MediaPipe (detección alternativa)",
    }

    for module_name, display_name in optional.items():
        try:
            __import__(module_name)
            print_success(f"  {display_name} disponible")
        except ImportError:
            print_info(f"  {display_name} no instalado")

    return all_ok


def check_camera_opencv() -> bool:
    """Test camera access with OpenCV."""
    print_header("2. PROBANDO CÁMARA CON OPENCV")

    try:
        import cv2

        # Try different camera indices
        for idx in range(3):
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    h, w = frame.shape[:2]
                    print_success(f"Cámara encontrada en /dev/video{idx}")
                    print_info(f"  Resolución: {w}x{h}")
                    cap.release()
                    return True
                else:
                    cap.release()

        print_error("No se puede capturar frames de ninguna cámara")
        return False

    except Exception as e:
        print_error(f"Error con OpenCV: {e}")
        return False


def check_camera_libcamera() -> bool:
    """Test camera availability with libcamera (RPi native)."""
    print_header("3. VERIFICANDO LIBCAMERA (Raspberry Pi)")

    try:
        # Check if we can import libcamera or picamera2
        has_picamera2 = False
        has_libcamera = False

        try:
            import picamera2
            has_picamera2 = True
            print_success("Picamera2 disponible")
        except ImportError:
            print_info("Picamera2 no instalado")

        # Check libcamera installation
        import subprocess

        result = subprocess.run(
            ["which", "libcamera-hello"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            has_libcamera = True
            print_success("libcamera-hello disponible")
        else:
            print_info("libcamera-hello no instalado")
            print_info("  Instala: sudo apt install -y libcamera-apps")

        # Check /dev/video devices
        video_devices = list(Path("/dev").glob("video*"))
        if video_devices:
            print_success(f"Dispositivos de vídeo encontrados: {video_devices}")
        else:
            print_error("No se encontraron dispositivos de vídeo en /dev")

        return has_picamera2 or has_libcamera or len(video_devices) > 0

    except Exception as e:
        print_error(f"Error verificando libcamera: {e}")
        return False


def check_display_env() -> None:
    """Check display environment."""
    print_header("4. ENTORNO DE PANTALLA")

    display = os.getenv("DISPLAY", "NOT SET")
    xauth = os.getenv("XAUTHORITY", "NOT SET")

    print_info(f"DISPLAY={display}")
    print_info(f"XAUTHORITY={xauth}")

    if display != "NOT SET":
        print_success("Display configurado (puede ejecutar GUI)")
    else:
        print_error("Display no configurado (headless mode)")


def check_app_structure() -> bool:
    """Check if project structure is complete."""
    print_header("5. ESTRUCTURA DEL PROYECTO")

    required_files = [
        "config.py",
        "main.py",
        "core/face_recognition.py",
        "ui/app.py",
        "requirements.txt",
    ]

    all_ok = True
    for file_path in required_files:
        full_path = Path(__file__).parent / file_path
        if full_path.exists():
            print_success(f"{file_path} existe")
        else:
            print_error(f"{file_path} FALTA")
            all_ok = False

    return all_ok


def test_face_recognition_module() -> bool:
    """Test if face recognition module can be imported and initialized."""
    print_header("6. PROBANDO MÓDULO DE RECONOCIMIENTO FACIAL")

    try:
        from core.face_recognition import FaceRecognitionManager

        print_success("Módulo de reconocimiento facial importado")

        manager = FaceRecognitionManager()
        print_info("Intentando inicializar gestor de reconocimiento facial...")

        if manager.initialize():
            print_success("Gestor inicializado correctamente")
            print_info("Intentando capturar un frame...")

            frame = manager.get_frame()
            if frame is not None:
                print_success(f"Frame capturado: {frame.shape}")
                manager.release()
                return True
            else:
                print_error("No se pudo capturar un frame")
                manager.release()
                return False
        else:
            print_error("No se pudo inicializar el gestor")
            return False

    except Exception as e:
        print_error(f"Error en módulo de reconocimiento facial: {e}")
        import traceback

        traceback.print_exc()
        return False


def main() -> None:
    """Run all diagnostics."""
    print("\n" + "=" * 60)
    print("  DIAGNÓSTICO DE CÁMARA - SMART LOCKER")
    print("=" * 60)

    results = {
        "Imports": check_imports(),
        "OpenCV Camera": check_camera_opencv(),
        "Libcamera/Picamera2": check_camera_libcamera(),
        "App Structure": check_app_structure(),
        "Face Recognition Module": test_face_recognition_module(),
    }

    check_display_env()

    # Summary
    print_header("RESUMEN")
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:.<40} {status}")

    total = len(results)
    passed = sum(1 for r in results.values() if r)
    print(f"\n{passed}/{total} pruebas pasadas")

    if passed == total:
        print_success("Sistema listo para uso")
    else:
        print_error("Se necesitan ajustes antes de usar")
        print("\nPasos recomendados:")
        print("1. Instala las dependencias: pip install -r requirements.txt")
        print("2. En Raspberry Pi, asegúrate de:")
        print("   - Habilitar la cámara en raspi-config")
        print("   - Tener libcamera instalado: sudo apt install libcamera-tools")
        print("3. Prueba acceso a cámara: libcamera-hello")


if __name__ == "__main__":
    main()
