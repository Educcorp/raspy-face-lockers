#!/usr/bin/env python3
"""
Script de diagnóstico profundo para cámara.
Determina exactamente qué está pasando con la captura y el color.
"""

import sys
import os
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

try:
    import cv2
    import numpy as np
    from PIL import Image
    logger.info("✓ OpenCV y NumPy importados correctamente")
except ImportError as e:
    logger.error(f"✗ Error importando OpenCV/NumPy: {e}")
    sys.exit(1)

def test_picamera2():
    """Test picamera2 directamente."""
    logger.info("\n" + "="*70)
    logger.info("TEST 1: Picamera2")
    logger.info("="*70)
    
    try:
        # Intenta importar picamera2
        import sys
        import site
        
        # Agregar rutas del sistema
        system_paths = [
            "/usr/lib/python3/dist-packages",
            "/usr/local/lib/python3/dist-packages",
        ]
        
        for sitedir in system_paths:
            if sitedir not in sys.path:
                sys.path.insert(0, sitedir)
        
        from picamera2 import Picamera2
        logger.info("✓ Picamera2 importado correctamente")
        
        # Crear instancia
        cam = Picamera2(0)
        logger.info("✓ Picamera2(0) creado")
        
        # Configurar
        config = cam.create_preview_configuration(
            main={
                "format": "RGB888",
                "size": (640, 480)
            }
        )
        cam.configure(config)
        logger.info("✓ Configuración RGB888 640x480 aplicada")
        
        # Iniciar
        cam.start()
        logger.info("✓ Cámara iniciada")
        
        # Capturar varios frames
        import time
        for i in range(3):
            time.sleep(0.5)
            rgb_array = cam.capture_array()
            logger.info(f"\nFrame {i+1}:")
            logger.info(f"  Shape: {rgb_array.shape}")
            logger.info(f"  Dtype: {rgb_array.dtype}")
            logger.info(f"  Min/Max: {rgb_array.min()} / {rgb_array.max()}")
            
            # Analizar canales
            r_mean = rgb_array[:,:,0].mean()
            g_mean = rgb_array[:,:,1].mean()
            b_mean = rgb_array[:,:,2].mean()
            logger.info(f"  Canal R (promedio): {r_mean:.1f}")
            logger.info(f"  Canal G (promedio): {g_mean:.1f}")
            logger.info(f"  Canal B (promedio): {b_mean:.1f}")
            
            # Guarda un frame para inspección visual
            img = Image.fromarray(rgb_array, mode="RGB")
            img.save(f"/tmp/test_frame_{i}_picamera2_rgb.png")
            logger.info(f"  Guardado: /tmp/test_frame_{i}_picamera2_rgb.png")
            
            # Ahora convierte a BGR y compara
            bgr_frame = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
            logger.info(f"\nDespués de cvtColor(RGB→BGR):")
            logger.info(f"  Shape: {bgr_frame.shape}")
            logger.info(f"  Dtype: {bgr_frame.dtype}")
            b_mean_bgr = bgr_frame[:,:,0].mean()
            g_mean_bgr = bgr_frame[:,:,1].mean()
            r_mean_bgr = bgr_frame[:,:,2].mean()
            logger.info(f"  Canal B (promedio): {b_mean_bgr:.1f}")
            logger.info(f"  Canal G (promedio): {g_mean_bgr:.1f}")
            logger.info(f"  Canal R (promedio): {r_mean_bgr:.1f}")
            
            # Convierte de vuelta a RGB
            rgb_again = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            img2 = Image.fromarray(rgb_again, mode="RGB")
            img2.save(f"/tmp/test_frame_{i}_after_roundtrip_rgb.png")
            logger.info(f"  Guardado (después roundtrip): /tmp/test_frame_{i}_after_roundtrip_rgb.png")
        
        cam.stop()
        logger.info("\n✓ Picamera2 test completado")
        return True
        
    except ImportError as e:
        logger.error(f"✗ Picamera2 no disponible: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Error en test picamera2: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_face_recognition_manager():
    """Test FaceRecognitionManager."""
    logger.info("\n" + "="*70)
    logger.info("TEST 2: FaceRecognitionManager")
    logger.info("="*70)
    
    try:
        from core.face_recognition import FaceRecognitionManager
        logger.info("✓ FaceRecognitionManager importado")
        
        mgr = FaceRecognitionManager()
        logger.info("✓ FaceRecognitionManager creado")
        
        if not mgr.initialize():
            logger.error("✗ No se pudo inicializar FaceRecognitionManager")
            return False
        
        logger.info("✓ FaceRecognitionManager inicializado")
        logger.info(f"  Backend: {mgr.backend_type}")
        
        # Captura varios frames
        import time
        for i in range(3):
            time.sleep(0.5)
            frame, faces = mgr.detect_faces_in_frame()
            
            if frame is None:
                logger.warning(f"  Frame {i+1}: None")
                continue
            
            logger.info(f"\nFrame {i+1}:")
            logger.info(f"  Shape: {frame.shape}")
            logger.info(f"  Dtype: {frame.dtype}")
            
            # Analizar canales asumiendo BGR
            b_mean = frame[:,:,0].mean()
            g_mean = frame[:,:,1].mean()
            r_mean = frame[:,:,2].mean()
            logger.info(f"  Canal B (promedio): {b_mean:.1f}")
            logger.info(f"  Canal G (promedio): {g_mean:.1f}")
            logger.info(f"  Canal R (promedio): {r_mean:.1f}")
            
            logger.info(f"  Rostros detectados: {len(faces)}")
            for j, face in enumerate(faces):
                logger.info(f"    Rostro {j+1}: {face}")
            
            # Guarda frame como BGR (como lo hace OpenCV)
            cv2.imwrite(f"/tmp/test_frame_{i}_mgr_bgr.png", frame)
            logger.info(f"  Guardado (BGR): /tmp/test_frame_{i}_mgr_bgr.png")
        
        mgr.release()
        logger.info("\n✓ FaceRecognitionManager test completado")
        return True
        
    except Exception as e:
        logger.error(f"✗ Error en test FaceRecognitionManager: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_admin_screen_capture():
    """Test simulando lo que hace _Step4FaceCapture."""
    logger.info("\n" + "="*70)
    logger.info("TEST 3: Simulación Step4FaceCapture")
    logger.info("="*70)
    
    try:
        from core.face_recognition import FaceRecognitionManager
        import time
        
        mgr = FaceRecognitionManager()
        if not mgr.initialize():
            logger.error("✗ No se pudo inicializar cámara")
            return False
        
        logger.info("✓ Cámara inicializada")
        
        # Captura un frame
        time.sleep(0.5)
        frame, faces = mgr.detect_faces_in_frame()
        
        if frame is None:
            logger.error("✗ Frame es None")
            return False
        
        logger.info(f"✓ Frame capturado: {frame.shape}, {frame.dtype}")
        logger.info(f"  Rostros: {len(faces)}")
        
        # Simula _update_canvas
        WIN_W, WIN_H = 480, 600
        
        logger.info("\nSimulando _update_canvas:")
        logger.info(f"  WIN_W={WIN_W}, WIN_H={WIN_H}")
        
        # Redimensiona manteniendo aspect ratio
        h, w = frame.shape[:2]
        scale = min(WIN_W / w, WIN_H / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        logger.info(f"  Frame original: {w}x{h}")
        logger.info(f"  Scale: {scale:.3f}")
        logger.info(f"  Frame redimensionado: {new_w}x{new_h}")
        
        # Redimensiona
        frame_resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        logger.info(f"  ✓ Resize completado")
        
        # Convierte BGR → RGB
        frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
        logger.info(f"  ✓ Conversión BGR→RGB completada")
        
        # Analizas canales
        r_mean = frame_rgb[:,:,0].mean()
        g_mean = frame_rgb[:,:,1].mean()
        b_mean = frame_rgb[:,:,2].mean()
        logger.info(f"    Canal R: {r_mean:.1f}")
        logger.info(f"    Canal G: {g_mean:.1f}")
        logger.info(f"    Canal B: {b_mean:.1f}")
        
        # Crea canvas
        canvas = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)
        y_offset = (WIN_H - new_h) // 2
        x_offset = (WIN_W - new_w) // 2
        canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = frame_rgb
        logger.info(f"  ✓ Canvas creado (negro con imagen centrada)")
        
        # Crea PIL image
        img = Image.fromarray(canvas, mode="RGB").convert("RGBA")
        logger.info(f"  ✓ PIL image creado (mode=RGB → converted to RGBA)")
        
        # Guarda para inspección
        pil_rgb = Image.fromarray(canvas, mode="RGB")
        pil_rgb.save("/tmp/test_admin_canvas.png")
        logger.info(f"  Guardado: /tmp/test_admin_canvas.png")
        
        mgr.release()
        logger.info("\n✓ Simulación completada")
        return True
        
    except Exception as e:
        logger.error(f"✗ Error en simulación: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_capture_button():
    """Test la lógica del botón de captura."""
    logger.info("\n" + "="*70)
    logger.info("TEST 4: Lógica del botón Capturar")
    logger.info("="*70)
    
    try:
        from core.face_recognition import FaceRecognitionManager
        import time
        
        mgr = FaceRecognitionManager()
        if not mgr.initialize():
            logger.error("✗ No se pudo inicializar cámara")
            return False
        
        logger.info("✓ Cámara inicializada")
        
        # Simula lo que hace _capture()
        logger.info("\nSimulando _capture():")
        
        current_frame = None
        detected_faces = []
        
        # Captura varios frames hasta que detecte un rostro
        for attempt in range(10):
            time.sleep(0.33)
            frame, faces = mgr.detect_faces_in_frame()
            
            current_frame = frame
            detected_faces = faces
            
            logger.info(f"  Intento {attempt+1}: {len(faces)} rostro(s)")
            
            if len(faces) > 0:
                logger.info(f"    ✓ Rostro detectado!")
                break
        
        # Verifica precondiciones de _capture
        logger.info("\nVerificación de precondiciones:")
        
        if current_frame is None:
            logger.error("  ✗ current_frame es None")
            return False
        logger.info("  ✓ current_frame no es None")
        
        if not detected_faces:
            logger.warning("  ⚠ detected_faces está vacío")
            logger.info("  Nota: Este es el problema - no se detectó rostro")
            return False
        
        logger.info(f"  ✓ detected_faces contiene {len(detected_faces)} rostro(s)")
        
        # Simula extracción de embedding
        logger.info("\nSimulando _extract_embedding():")
        face_info = detected_faces[0]
        box = face_info.get("box")
        logger.info(f"  Box: {box}")
        
        if box is not None:
            x, y, w, h = [int(v) for v in box[:4]]
            face_crop = current_frame[max(0, y):y+h, max(0, x):x+w]
            logger.info(f"  Face crop: {face_crop.shape}")
            
            # Placeholder embedding
            resized = cv2.resize(face_crop, (16, 8))
            vec = resized.astype(np.float32).flatten()
            if len(vec) < 128:
                vec = np.pad(vec, (0, 128 - len(vec)))
            else:
                vec = vec[:128]
            norm = np.linalg.norm(vec)
            embedding = (vec / norm) if norm > 0 else vec
            logger.info(f"  ✓ Embedding extraído: {embedding.shape}, norm={norm:.3f}")
        
        mgr.release()
        logger.info("\n✓ Test de botón completado")
        return True
        
    except Exception as e:
        logger.error(f"✗ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    logger.info("\n" + "="*70)
    logger.info("DIAGNÓSTICO PROFUNDO DE CÁMARA")
    logger.info("="*70)
    
    results = {
        "Picamera2": test_picamera2(),
        "FaceRecognitionManager": test_face_recognition_manager(),
        "Simulación Admin Screen": test_admin_screen_capture(),
        "Lógica Botón Capturar": test_capture_button(),
    }
    
    logger.info("\n" + "="*70)
    logger.info("RESUMEN")
    logger.info("="*70)
    for test_name, result in results.items():
        status = "✓" if result else "✗"
        logger.info(f"{status} {test_name}")
    
    logger.info("\n" + "="*70)
    logger.info("Archivos generados en /tmp/:")
    logger.info("  - test_frame_*_picamera2_rgb.png (Raw de Picamera2)")
    logger.info("  - test_frame_*_after_roundtrip_rgb.png (Después de BGR→RGB)")
    logger.info("  - test_frame_*_mgr_bgr.png (De FaceRecognitionManager)")
    logger.info("  - test_admin_canvas.png (Simulación del canvas admin)")
    logger.info("="*70 + "\n")
