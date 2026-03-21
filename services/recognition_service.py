from __future__ import annotations

from typing import Optional
import logging

import numpy as np

from config import FACE_RECOGNITION_CONFIG
from database.connection import fetch_all, fetch_one

logger = logging.getLogger(__name__)


def _to_vector(blob: bytes, dtype_name: str, dimension: int) -> Optional[np.ndarray]:
    dtype = np.float32 if dtype_name == "float32" else np.float64
    vector = np.frombuffer(blob, dtype=dtype)
    if vector.size == 0:
        return None
    if dimension and vector.size != int(dimension):
        if vector.size < int(dimension):
            return None
        vector = vector[: int(dimension)]
    vector = vector.astype(np.float32, copy=False)
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector


def find_best_user_match(probe_embedding: np.ndarray, threshold: Optional[float] = None) -> Optional[dict]:
    if probe_embedding is None or probe_embedding.size == 0:
        return None

    decision_threshold = float(threshold or FACE_RECOGNITION_CONFIG.get("distance_threshold", 0.6))

    rows = fetch_all(
        """
        SELECT idUsuario, vector, COALESCE(vectorDtype, 'float32') AS vectorDtype, dimension
        FROM encoding
        WHERE estado = 'activo'
        """
    )

    best_user_id: Optional[int] = None
    best_distance = 10.0

    for row in rows:
        vector = _to_vector(
            row.get("vector"),
            row.get("vectorDtype") or "float32",
            int(row.get("dimension") or FACE_RECOGNITION_CONFIG.get("embedding_size", 128)),
        )
        if vector is None:
            continue

        distance = float(np.linalg.norm(probe_embedding - vector))
        if distance < best_distance:
            best_distance = distance
            best_user_id = int(row["idUsuario"])

    if best_user_id is None or best_distance > decision_threshold:
        return None

    user = fetch_one(
        """
        SELECT idUsuario, nombre, apPaterno, apMaterno, estado
        FROM usuarios
        WHERE idUsuario = ?
        """,
        (best_user_id,),
    )
    if not user or user.get("estado") != "activo":
        return None

    full_name = " ".join(
        [
            (user.get("nombre") or "").strip(),
            (user.get("apPaterno") or "").strip(),
            (user.get("apMaterno") or "").strip(),
        ]
    ).strip()

    return {
        "user_id": int(user["idUsuario"]),
        "nombre": full_name or f"Usuario {user['idUsuario']}",
        "distance": best_distance,
        "threshold": decision_threshold,
    }


def recognize_user_from_face(face_manager, frame: np.ndarray, face_box: tuple) -> Optional[dict]:
    if face_manager is None or frame is None or not face_box:
        return None

    embedding = face_manager.get_embedding(frame, face_box)
    if embedding is None:
        return None

    try:
        return find_best_user_match(embedding)
    except Exception as exc:
        logger.error(f"Error reconociendo usuario facial: {exc}")
        return None
