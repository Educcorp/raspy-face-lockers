#!/usr/bin/env python3
"""
Test simple para diagnóstico de color en admin register.
SOLO austra Picamera2 directo, sin el singleton.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.DEBUG)

import cv2
import numpy as np
import time
from PIL import Image

try:
    import sys
    import site
    system_paths = ["/usr/lib/python3/dist-packages"]
    for sitedir in system_paths:
        if sitedir not in sys.path:
            sys.path.insert(0, sitedir)
    from picamera2 import Picamera2
except ImportError as e:
    print(f"Error: {e}")
    sys.exit(1)

print("="*70)
print("TEST SIMPLE: Picamera2 → Admin Canvas → PIL Image")
print("="*70)

# Crear instancia NUEVA de Picamera2 (sin singleton)
print("\n1. Creando Picamera2...")
cam = Picamera2(0)

print("2. Configurando...")
config = cam.create_preview_configuration(
    main={"format": "RGB888", "size": (640, 480)}
)
cam.configure(config)

print("3. Iniciando cámara...")
cam.start()
time.sleep(1)

print("4. Capturando frame...")
rgb_array = cam.capture_array()
print(f"   Shape: {rgb_array.shape}, Dtype: {rgb_array.dtype}")
print(f"   Canales de la imagen DIRECTA de Picamera2 (RGB):")
print(f"     Canal [0] (R): promedio={rgb_array[:,:,0].mean():.1f}")
print(f"     Canal [1] (G): promedio={rgb_array[:,:,1].mean():.1f}")
print(f"     Canal [2] (B): promedio={rgb_array[:,:,2].mean():.1f}")

# Opción 1: PIL directamente (sin conversión)
print("\n5. Opción 1: PIL Image.fromarray(rgb_array, mode='RGB')...")
pil_img1 = Image.fromarray(rgb_array, mode="RGB")
pil_img1.save("/tmp/test_option1_direct_rgb.png")
print("   ✓ Guardado en /tmp/test_option1_direct_rgb.png")

# Opción 2: Convertir RGB→BGR (como lo hace FaceRecognitionManager)
print("\n6. Opción 2: RGB→BGR→RGB (doble conversión como el código actual)...")
bgr_frame = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
print(f"   Después RGB→BGR:")
print(f"     Canal [0] (B): promedio={bgr_frame[:,:,0].mean():.1f}")
print(f"     Canal [1] (G): promedio={bgr_frame[:,:,1].mean():.1f}")
print(f"     Canal [2] (R): promedio={bgr_frame[:,:,2].mean():.1f}")

frame_rgb_again = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
pil_img2 = Image.fromarray(frame_rgb_again, mode="RGB")
pil_img2.save("/tmp/test_option2_roundtrip.png")
print("   ✓ Guardado en /tmp/test_option2_roundtrip.png")

# Opción 3: Simulación de _update_canvas (con canvas)
print("\n7. Opción 3: Simulación exacta de _update_canvas...")
WIN_W, WIN_H = 480, 600

h, w = bgr_frame.shape[:2]
scale = min(WIN_W / w, WIN_H / h)
new_w = int(w * scale)
new_h = int(h * scale)
print(f"   Scale: {scale:.3f}, Nuevo tamaño: {new_w}x{new_h}")

# Crear canvas Y COLOCAR LA IMAGEN
frame_resized = cv2.resize(bgr_frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
print(f"   Frame resized)")

frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
print(f"   Convertido a RGB")

canvas = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)
y_offset = (WIN_H - new_h) // 2
x_offset = (WIN_W - new_w) // 2
canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = frame_rgb

print(f"   Canvas creado:")
print(f"     Canales en la zona de imagen:")
# Extraer la zona de imagen para inspeccionar
img_zone = canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w]
print(f"       Canal [0]: promedio={img_zone[:,:,0].mean():.1f}")
print(f"       Canal [1]: promedio={img_zone[:,:,1].mean():.1f}")
print(f"       Canal [2]: promedio={img_zone[:,:,2].mean():.1f}")

# Crear PIL image DIRECTAMENTE CON CANVAS (como el código)
pil_img3_rgba = Image.fromarray(canvas, mode="RGB").convert("RGBA")
pil_img3 = pil_img3_rgba.convert("RGB")
pil_img3.save("/tmp/test_option3_canvas.png")
print("   ✓ Guardado en /tmp/test_option3_canvas.png")

# Opción 4: SIN conversión BGR→RGB
print("\n8. Opción 4: RGB directo sin convertir a BGR...")
frame_resized_direct = cv2.resize(rgb_array, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
canvas_direct = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)
canvas_direct[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = frame_resized_direct
pil_img4 = Image.fromarray(canvas_direct, mode="RGB").convert("RGBA").convert("RGB")
pil_img4.save("/tmp/test_option4_rgb_direct.png")
print("   ✓ Guardado en /tmp/test_option4_rgb_direct.png")

# Limpieza
print("\n9. Limpiando...")
cam.stop()

print("\n" + "="*70)
print("RESULTADOS GUARDADOS")
print("="*70)
print("Compara estas imágenes en el explorador de archivos:")
print("  1. /tmp/test_option1_direct_rgb.png          - PIL(rgb_array, 'RGB')")
print("  2. /tmp/test_option2_roundtrip.png           - RGB→BGR→RGB")
print("  3. /tmp/test_option3_canvas.png              - Canvas actual(buggy)")
print("  4. /tmp/test_option4_rgb_direct.png          - RGB directo sin BGR")
print("\n¿Cuál se ve correcta? (La que NO está azul dominante)")
print("="*70)
