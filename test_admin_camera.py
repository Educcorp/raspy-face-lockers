#!/usr/bin/env python3
"""
Test script para verificar que la cámara funciona en el contexto del admin.
Ejecuta los mismos pasos que el Paso 4 del admin.
"""

import sys
import logging

# Configurar logging igual que main.py
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

print("="*70)
print("TEST: Contexto de Cámara del Admin (Paso 4)")
print("="*70)

# Test 1: Verificar que picamera2 está disponible
print("\n[1] Verificando disponibilidad de picamera2...")
try:
    from picamera2 import Picamera2
    print("    ✓ picamera2 importado correctamente")
except ImportError as e:
    print(f"    ✗ Error importando picamera2: {e}")
    sys.exit(1)

# Test 2: Crear FaceRecognitionManager
print("\n[2] Creando FaceRecognitionManager...")
try:
    from core.face_recognition import FaceRecognitionManager
    mgr = FaceRecognitionManager()
    print(f"    ✓ FaceRecognitionManager creado (backend: {mgr.backend_type})")
except Exception as e:
    print(f"    ✗ Error: {e}")
    sys.exit(1)

# Test 3: Inicializar manager
print("\n[3] Inicializando FaceRecognitionManager...")
try:
    if mgr.initialize():
        print("    ✓ FaceRecognitionManager inicializado exitosamente")
    else:
        print("    ✗ FaceRecognitionManager.initialize() retornó False")
        sys.exit(1)
except Exception as e:
    print(f"    ✗ Error durante inicialización: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Capturar frames
print("\n[4] Capturando frames...")
try:
    for i in range(3):
        frame = mgr.get_frame()
        if frame is not None:
            print(f"    Frame {i+1}: {frame.shape} ✓")
        else:
            print(f"    Frame {i+1}: NULL ✗")
            break
except Exception as e:
    print(f"    ✗ Error capturando frames: {e}")
    sys.exit(1)

# Test 5: Liberar resources
print("\n[5] Liberando recursos...")
try:
    mgr.release()
    print("    ✓ Camera liberada correctamente")
except Exception as e:
    print(f"    ✗ Error liberando: {e}")
    sys.exit(1)

print("\n" + "="*70)
print("✓ RESULTADO: Admin camera test PASSED - Todo puedes funcionar correctamente")
print("="*70)
