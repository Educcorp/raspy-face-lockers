"""
Pose de la cabeza (giro lateral e inclinación) a partir de los 68 landmarks de dlib.

Se usa para dos cosas:
  * Registro de rostro en la Pi: comprobar que la persona REALMENTE giró a la
    derecha/izquierda o levantó la barbilla (antes se capturaba tras 15 cuadros
    estables aunque no se moviera).
  * Kiosco: reto de vivacidad. Una foto o pantalla estática no puede girar la
    cabeza; aunque se incline una foto, sus rasgos siguen siendo "frontales".

Las señales son relativas al tamaño de la cara (no grados) y NO dependen de la
distancia a la cámara. Convención (desde el punto de vista del USUARIO, no del
espejo): yaw > 0 = gira a SU derecha; pitch > 0 = levanta la barbilla.

Calibración: tools/head_pose_selftest.py (modelo 3D sintético). Los signos con la
cámara real se comprueban con tools/head_pose_debug.py; si derecha/izquierda salen
invertidas, cambiar HEAD_POSE_CONFIG["yaw_sign"] a -1.0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np

from config import HEAD_POSE_CONFIG

DIRECTIONS = ("derecha", "izquierda", "arriba")


@dataclass(frozen=True)
class HeadPose:
    yaw: float
    pitch: float

    def minus(self, other: "HeadPose") -> "HeadPose":
        return HeadPose(self.yaw - other.yaw, self.pitch - other.pitch)


def estimate_head_pose(
    landmarks: Optional[Sequence[Tuple[float, float]]],
) -> Optional[HeadPose]:
    """Pose a partir de los 68 landmarks (frame SIN espejar). None si no es utilizable."""
    if landmarks is None or len(landmarks) < 68:
        return None
    pts = np.asarray(landmarks, dtype=np.float32)

    left_eye, right_eye = pts[36], pts[45]      # esquinas externas (lado imagen)
    nose_tip, chin = pts[30], pts[8]
    iod = float(right_eye[0] - left_eye[0])
    if iod <= 1.0:
        return None

    eye_mid = (left_eye + right_eye) * 0.5
    chin_drop = float(chin[1] - eye_mid[1])
    if chin_drop <= 1.0:
        return None

    # Nariz desplazada respecto al punto medio de los ojos, normalizada por la
    # distancia interocular. En imagen SIN espejar, la derecha del usuario es la
    # izquierda de la imagen → el signo se invierte.
    yaw_img = float(nose_tip[0] - eye_mid[0]) / iod
    yaw = -yaw_img * float(HEAD_POSE_CONFIG["yaw_sign"])

    # Posición vertical de la nariz entre la línea de los ojos y la barbilla: al
    # levantar la barbilla la nariz sube hacia los ojos y la fracción BAJA.
    nose_frac = float(nose_tip[1] - eye_mid[1]) / chin_drop
    pitch = -nose_frac
    return HeadPose(yaw=yaw, pitch=pitch)


def is_frontal(pose: HeadPose, baseline: Optional[HeadPose] = None) -> bool:
    """¿Mira de frente? Sin baseline solo se exige yaw≈0 (el pitch depende de cada rostro)."""
    if abs(pose.yaw) > HEAD_POSE_CONFIG["frontal_max_yaw"]:
        return False
    if baseline is not None:
        return abs(pose.pitch - baseline.pitch) <= HEAD_POSE_CONFIG["frontal_max_pitch"]
    return True


def matches_direction(delta: HeadPose, direction: str) -> bool:
    """`delta` = pose actual − pose de referencia (de frente) del mismo usuario."""
    if direction == "derecha":
        return delta.yaw >= HEAD_POSE_CONFIG["yaw_threshold"]
    if direction == "izquierda":
        return delta.yaw <= -HEAD_POSE_CONFIG["yaw_threshold"]
    if direction == "arriba":
        return (
            delta.pitch >= HEAD_POSE_CONFIG["pitch_up_threshold"]
            and abs(delta.yaw) < HEAD_POSE_CONFIG["yaw_threshold"]
        )
    raise ValueError(f"Dirección desconocida: {direction!r}")
