#!/usr/bin/env python3
"""
Setup script para Smart Locker - configura todo lo necesario para ejecutar.

Uso: python setup.py
"""

import os
import sys
import subprocess
from pathlib import Path


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{'='*70}")
    print(f"  {text:^66}")
    print(f"{'='*70}\n")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"  ✓ {text}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"  ✗ {text}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"  ℹ {text}")


def run_command(cmd: list, description: str = None) -> bool:
    """Run a shell command and return success status."""
    if description:
        print_info(description)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True
        else:
            if result.stderr:
                print_error(f"Error: {result.stderr[:100]}")
            return False
    except Exception as e:
        print_error(f"Excepción: {e}")
        return False


def setup_directories():
    """Create required directories."""
    print_header("1. CREANDO ESTRUCTURA DE DIRECTORIOS")
    
    dirs = [
        "assets/models",
        "logs",
        "database",
    ]
    
    project_root = Path(__file__).parent
    for dir_path in dirs:
        full_path = project_root / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print_success(f"Directorio: {dir_path}")


def setup_dependencies():
    """Install Python dependencies."""
    print_header("2. INSTALANDO DEPENDENCIAS PYTHON")
    
    # Check if in virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print_success("Entorno virtual activado")
    else:
        print_info("No estás en un entorno virtual")
        print_info("Se recomienda: python3 -m venv venv && source venv/bin/activate")
    
    # Install requirements
    requirements_file = Path(__file__).parent / "requirements.txt"
    if requirements_file.exists():
        print_info("Instalando dependencias de requirements.txt...")
        if run_command([sys.executable, "-m", "pip", "install", "-q", "-r", str(requirements_file)]):
            print_success("Dependencias instaladas")
        else:
            print_error("Error instalando dependencias")
            return False
    return True


def setup_system_packages():
    """Install system packages for Raspberry Pi."""
    print_header("3. PAQUETES DE SISTEMA (Raspberry Pi)")
    
    packages = {
        "libcamera-apps": "Tools de libcamera para testing",
        "libcamera-dev": "Desarrollo de libcamera",
    }
    
    print_info("Los siguientes paquetes se recomienda instalar con:")
    print_info("  sudo apt update && sudo apt install -y libcamera-apps libcamera-dev")
    print()
    for pkg, desc in packages.items():
        print_info(f"{pkg:.<30} - {desc}")


def download_face_models():
    """Download face detection models."""
    print_header("4. DESCARGANDO MODELOS DE DETECCIÓN FACIAL")
    
    models_script = Path(__file__).parent / "download_models.py"
    if models_script.exists():
        print_info("Ejecutando descargador de modelos...")
        result = subprocess.run([sys.executable, str(models_script)])
        return result.returncode == 0
    else:
        print_error("Script de descarga no encontrado")
        return False


def verify_camera():
    """Verify camera setup."""
    print_header("5. VERIFICANDO CÁMARA")
    
    try:
        from core.face_recognition import FaceRecognitionManager
        
        manager = FaceRecognitionManager()
        print_info(f"Backend detectado: {manager.backend_type}")
        
        if manager.initialize():
            print_success("Cámara inicializada correctamente")
            
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
            print_error("No se pudo inicializar cámara")
            return False
    except Exception as e:
        print_error(f"Error verificando cámara: {e}")
        return False


def main():
    """Run all setup steps."""
    print("\n" + "="*70)
    print("  SETUP - SMART LOCKER SYSTEM".center(70))
    print("  Raspberry Pi 5 - Face Recognition".center(70))
    print("="*70)
    
    try:
        setup_directories()
        
        if not setup_dependencies():
            print_error("Error en dependencias")
            return 1
        
        setup_system_packages()
        
        print_header("6. DESCARGANDO MODELOS")
        if download_face_models():
            print_success("Modelos descargados")
        else:
            print_info("Se skipped descargador de modelos (puedes ejecutar manualmente)")
        
        print_header("7. VERIFICACIÓN FINAL")
        if verify_camera():
            print_success("Sistema listo para usar")
        else:
            print_error("Verificación de cámara falló")
            print_info("Ejecuta: python diagnose_camera.py para más detalles")
        
        print("\n" + "="*70)
        print("  SETUP COMPLETADO".center(70))
        print("="*70)
        print("\nPróximos pasos:")
        print("  1. Ejecutar: python main.py --mode locker")
        print("  2. O ejecutar: python main.py --mode admin")
        print("\nPara diagnosticar problemas:")
        print("  python diagnose_camera.py")
        print()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\nSetup cancelado por el usuario")
        return 1
    except Exception as e:
        print(f"\n\nError durante setup: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
