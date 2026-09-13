#!/usr/bin/env python3
"""
Prueba manual del pipeline completo (detección + anti-spoofing) con la
webcam de la laptop, sin necesitar el Raspberry Pi.

Uso:
    CAMERA_BACKEND=opencv python tools/antispoof/test_liveness_webcam.py

Controles:
    q — salir

Qué probar:
  1. Tu cara real frente a la cámara -> debería marcar REAL en verde.
  2. Una foto tuya impresa, o tu cara en la pantalla de otro celular,
     sostenida frente a la cámara -> debería marcar FAKE en rojo.

Si algún caso falla, ajusta ANTI_SPOOF_CONFIG["score_threshold"] en
config.py (más alto = más estricto, más rechazos de caras reales border-line;
más bajo = más permisivo, más riesgo de dejar pasar spoofing).
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("CAMERA_BACKEND", "opencv")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import cv2

from core.face_recognition import get_face_recognition_manager


def main() -> None:
    manager = get_face_recognition_manager()
    if not manager.initialize():
        print("✗ No se pudo inicializar la cámara. ¿Está CAMERA_BACKEND=opencv?")
        return

    print(f"Embeddings dlib: {'OK' if manager.embedding_extractor.is_ready else 'FALLBACK (débil)'}")
    print(f"Anti-spoofing:   {'OK' if manager.anti_spoof.is_ready else 'NO DISPONIBLE'}")
    print("Presiona 'q' para salir.\n")

    try:
        while True:
            frame, faces = manager.detect_faces_in_frame()
            if frame is None:
                continue

            display = frame.copy()
            for face in faces:
                x, y, w, h = face["box"]
                is_real, score = manager.check_liveness(frame, face["box"])
                color = (0, 200, 0) if is_real else (0, 0, 220)
                label = f"{'REAL' if is_real else 'FAKE'} {score:.2f}"
                cv2.rectangle(display, (x, y), (x + w, y + h), color, 2)
                cv2.putText(display, label, (x, max(20, y - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            cv2.imshow("Anti-spoof test (q para salir)", display)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        manager.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
