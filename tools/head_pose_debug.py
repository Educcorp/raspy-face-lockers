"""
Verifica en vivo, con la cámara real, cómo se mide la pose de la cabeza.

Cierra antes el kiosco (la cámara solo puede tenerla un proceso) y ejecuta:
    python tools/head_pose_debug.py

Mira de frente unos segundos (fija la referencia) y luego gira a TU derecha,
a tu izquierda y levanta la barbilla. Debe imprimir la dirección correcta:
  * Si derecha/izquierda salen INVERTIDAS → HEAD_POSE_CONFIG["yaw_sign"] = -1.0
  * Si tu giro no llega a marcarse → baja "yaw_threshold" / "pitch_up_threshold"
Ctrl+C para salir.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import HEAD_POSE_CONFIG  # noqa: E402
from core import head_pose  # noqa: E402
from core.face_recognition import FaceRecognitionManager, filter_close_faces  # noqa: E402


def main() -> int:
    mgr = FaceRecognitionManager()
    if not mgr.initialize():
        print("No se pudo abrir la cámara (¿el kiosco sigue abierto?)")
        return 1
    if not getattr(mgr.embedding_extractor, "uses_dlib", False):
        print("dlib no disponible: no hay landmarks para medir la pose.")
        return 1

    print(f"yaw_sign={HEAD_POSE_CONFIG['yaw_sign']}  umbral yaw={HEAD_POSE_CONFIG['yaw_threshold']}  "
          f"umbral arriba={HEAD_POSE_CONFIG['pitch_up_threshold']}")
    print("Mira de frente para fijar la referencia…\n")
    neutral: list[head_pose.HeadPose] = []
    baseline = None
    try:
        while True:
            frame = mgr.get_frame()
            if frame is None:
                time.sleep(0.05)
                continue
            faces = filter_close_faces(mgr.face_detector.detect(frame), frame)
            if not faces:
                print("\r(sin rostro cercano)                                          ", end="")
                time.sleep(0.1)
                continue
            box = max(faces, key=lambda f: f["box"][2] * f["box"][3])["box"]
            pose = head_pose.estimate_head_pose(mgr.get_landmarks_fast(frame, box))
            if pose is None:
                continue
            if baseline is None:
                if head_pose.is_frontal(pose):
                    neutral.append(pose)
                if len(neutral) >= 10:
                    baseline = head_pose.HeadPose(float(np.median([p.yaw for p in neutral])),
                                                  float(np.median([p.pitch for p in neutral])))
                    print(f"Referencia fijada (yaw={baseline.yaw:+.3f} pitch={baseline.pitch:+.3f}). ¡Gira!\n")
                continue
            d = pose.minus(baseline)
            hits = [name.upper() for name in head_pose.DIRECTIONS if head_pose.matches_direction(d, name)]
            print(f"\ryaw={pose.yaw:+.3f} (Δ{d.yaw:+.3f})  pitch={pose.pitch:+.3f} (Δ{d.pitch:+.3f})  "
                  f"→ {', '.join(hits) or 'frente':<12}", end="")
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nListo.")
    finally:
        mgr.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
