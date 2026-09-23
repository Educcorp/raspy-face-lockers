"""
Autotest de core/head_pose.py con un modelo 3D sintético de cabeza.

No usa cámara: proyecta un rostro genérico con giros/inclinaciones conocidos y
comprueba que (1) los signos son los esperados, (2) los umbrales de HEAD_POSE_CONFIG
se cumplen con giros moderados y NO con la cabeza quieta, y (3) una foto plana
"girada" como cuerpo rígido no cumple ninguna pose (el caso de suplantación).

Uso:  python tools/head_pose_selftest.py
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.head_pose import HeadPose, estimate_head_pose, is_frontal, matches_direction  # noqa: E402

# Modelo genérico (mm). x: derecha de la IMAGEN (vista frontal), y: arriba, z: hacia la
# cámara. Origen: centro de la cabeza. Índices = landmarks dlib de 68 puntos.
MODEL = {
    0: (-70, 15, -10), 16: (70, 15, -10), 8: (0, -105, 55),
    30: (0, -28, 105), 36: (-45, 32, 45), 45: (45, 32, 45),
}


def _rot(yaw_deg: float, up_deg: float) -> np.ndarray:
    """yaw>0: el usuario gira a SU derecha (la nariz va hacia x<0 de la imagen)."""
    a, b = np.radians(yaw_deg), np.radians(up_deg)
    ry = np.array([[np.cos(a), 0, -np.sin(a)], [0, 1, 0], [np.sin(a), 0, np.cos(a)]])
    rx = np.array([[1, 0, 0], [0, np.cos(b), np.sin(b)], [0, -np.sin(b), np.cos(b)]])
    return ry @ rx


def _landmarks(yaw_deg=0.0, up_deg=0.0, flat=False, dist=900.0):
    lm = np.zeros((68, 2), dtype=np.float32)
    r = _rot(yaw_deg, up_deg)
    for i, (x, y, z) in MODEL.items():
        q = r @ np.array([x, y, 50.0 if flat else z], dtype=float)
        s = dist / (dist - q[2])
        lm[i] = (q[0] * s, -q[1] * s)          # imagen: y hacia abajo
    return lm


def main() -> int:
    fails = []

    def check(name, cond):
        print(("  ok   " if cond else "  FALLA"), name)
        if not cond:
            fails.append(name)

    base = estimate_head_pose(_landmarks())
    check("cara de frente es 'frontal'", is_frontal(base))
    for d in ("derecha", "izquierda", "arriba"):
        check(f"quieto NO cumple '{d}'", not matches_direction(HeadPose(0, 0), d))

    for deg in (15, 25, 35):
        p = estimate_head_pose(_landmarks(yaw_deg=deg)).minus(base)
        check(f"giro {deg}° a la derecha → 'derecha' (y no 'izquierda')",
              matches_direction(p, "derecha") and not matches_direction(p, "izquierda"))
        p = estimate_head_pose(_landmarks(yaw_deg=-deg)).minus(base)
        check(f"giro {deg}° a la izquierda → 'izquierda' (y no 'derecha')",
              matches_direction(p, "izquierda") and not matches_direction(p, "derecha"))
    for deg in (12, 20, 30):
        p = estimate_head_pose(_landmarks(up_deg=deg)).minus(base)
        check(f"barbilla arriba {deg}° → 'arriba'", matches_direction(p, "arriba"))
    p = estimate_head_pose(_landmarks(yaw_deg=5)).minus(base)
    check("giro leve de 5° no dispara 'derecha'", not matches_direction(p, "derecha"))

    # Suplantación: foto plana girada / inclinada como cuerpo rígido
    flat0 = estimate_head_pose(_landmarks(flat=True))
    worst = 0.0
    for yaw in (-45, -30, 30, 45):
        d = estimate_head_pose(_landmarks(yaw_deg=yaw, flat=True)).minus(flat0)
        worst = max(worst, abs(d.yaw))
        check(f"foto plana girada {yaw}° NO cumple derecha/izquierda",
              not matches_direction(d, "derecha") and not matches_direction(d, "izquierda"))
    for up in (-30, 30, 45):
        d = estimate_head_pose(_landmarks(up_deg=up, flat=True)).minus(flat0)
        check(f"foto plana inclinada {up}° NO cumple 'arriba'", not matches_direction(d, "arriba"))
    print(f"  (máx. yaw espurio de la foto plana: {worst:.3f})")

    print("\n" + ("TODO OK" if not fails else f"{len(fails)} comprobación(es) FALLARON"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
