#!/usr/bin/env python3
"""
Test Script: Simula el Step4 del Admin (Captura Facial)
Verifica que la cámara funciona correctamente en el contexto del admin.
"""

import sys
import logging
import threading
import time

# Configurar logging igual que main.py
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

print("\n" + "=" * 70)
print("TEST: Simulación de Step4 (Admin Capture Facial)")
print("=" * 70)

# Paso 1: Crear FaceRecognitionManager (como en el admin)
print("\n[1] Creando FaceRecognitionManager en contexto admin...")
try:
    from core.face_recognition import FaceRecognitionManager
    mgr = FaceRecognitionManager()
    print(f"    ✓ Manager creado (backend: {mgr.backend_type})")
except Exception as e:
    print(f"    ✗ Error: {e}")
    sys.exit(1)

# Paso 2: Inicializar (como en el admin on_enter)
print("\n[2] Inicializando manager (on_enter)...")
try:
    if not mgr.initialize():
        print("    ✗ mgr.initialize() retornó False")
        sys.exit(1)
    print("    ✓ Manager inicializado")
except Exception as e:
    print(f"    ✗ Error inicializando: {e}")
    sys.exit(1)

# Paso 3: Simular el camera_loop en threading
print("\n[3] Simulando camera_loop en thread...")
frames_captured = 0
faces_detected = 0

def camera_loop():
    global frames_captured, faces_detected
    for i in range(10):
        try:
            frame, faces = mgr.detect_faces_in_frame()
            if frame is not None:
                frames_captured += 1
                faces_detected = len(faces)
                print(f"    Frame {frames_captured}: {frame.shape}, {faces_detected} rostros")
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Error en loop: {e}")
            break

thread = threading.Thread(target=camera_loop, daemon=True)
thread.start()
thread.join(timeout=5)

print(f"\n    Total frames capturados: {frames_captured}")

# Paso 4: Liberar recursos
print("\n[4] Liberando recursos...")
try:
    mgr.release()
    print("    ✓ Manager liberado correctamente")
except Exception as e:
    print(f"    ✗ Error liberando: {e}")
    sys.exit(1)

# Resultado
print("\n" + "=" * 70)
if frames_captured > 0:
    print("✓ RESULTADO: Admin Step4 simulation PASSED")
    print(f"  Frames capturados: {frames_captured}")
    print(f"  Rostros detectados: {faces_detected} (últimas detección)")
    print("\n  ✓ La cámara funciona correctamente en el admin")
else:
    print("✗ RESULTADO: No frames capturados")
    sys.exit(1)
print("=" * 70 + "\n")
