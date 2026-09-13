"""
Extracción de embeddings faciales para el panel web.

Reutiliza directamente las clases de core/face_recognition.py (las mismas
que usa la Raspberry Pi para autenticar) para garantizar que los embeddings
generados aquí sean comparables con los que el Pi calcula en tiempo real.
Solo cambia el origen de la imagen: aquí viene de una foto subida desde el
navegador, no de un frame de picamera2.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

from core.face_recognition import FaceDetector, FaceEmbeddingExtractor

logger = logging.getLogger(__name__)

_detector = FaceDetector()
_extractor = FaceEmbeddingExtractor()

MODEL_NAME = "dlib_resnet_v1" if _extractor.uses_dlib else "fallback_gray_16x8"


def decode_image(raw_bytes: bytes) -> np.ndarray | None:
    """Decodifica bytes de imagen (JPEG/PNG) a un array BGR de OpenCV."""
    data = np.frombuffer(raw_bytes, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def extract_embedding(frame_bgr: np.ndarray) -> tuple[np.ndarray | None, str]:
    """
    Detecta el rostro más grande en la imagen y extrae su embedding 128-dim.

    Returns:
        (embedding, "ok") si tuvo éxito.
        (None, motivo) si falló: "no_face" | "extraction_failed".
    """
    faces = _detector.detect(frame_bgr)
    if not faces:
        return None, "no_face"

    box = max(faces, key=lambda f: f["box"][2] * f["box"][3])["box"]
    embedding = _extractor.get_embedding(frame_bgr, box)
    if embedding is None:
        return None, "extraction_failed"
    return embedding, "ok"
