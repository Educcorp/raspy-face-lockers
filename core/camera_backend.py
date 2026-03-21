"""
core/camera_backend.py
======================
Backend unificado de cámara + embeddings faciales HOG.

Prioridad de backend de cámara:
  1. picamera2  (Raspberry Pi con cámara CSI)
  2. OpenCV V4L2 (cualquier cámara USB)
  3. Modo sin cámara → frame simulado con imagen estática (desarrollo)

Embeddings faciales:
  - HOG descriptor 128-dim (cv2 + numpy puro, sin dlib)
  - Determinístico, misma clase usada en admin y locker

Ambos paneles importan este módulo directamente — NO usa singletons.
"""

import cv2
import numpy as np
import logging
import threading
import time
from typing import Optional, List, Tuple, Dict

logger = logging.getLogger(__name__)

# ── HOG params (fijo, igual en admin y locker) ─────────────────────────────
_HOG_WIN   = (64, 64)
_HOG_BLOCK = (16, 16)
_HOG_STEP  = (8, 8)
_HOG_CELL  = (8, 8)
_HOG_BINS  = 9
_EMB_SIZE  = 128

_HAAR_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"


# ══════════════════════════════════════════════════════════════════════════════
# Embedding HOG (sin dlib, sin modelos externos)
# ══════════════════════════════════════════════════════════════════════════════

class HOGEmbedder:
    """
    Extrae embeddings faciales de 128-dim usando HOG.
    Mismo resultado en admin y locker para el mismo rostro.
    """

    def __init__(self):
        self._hog = cv2.HOGDescriptor(_HOG_WIN, _HOG_BLOCK, _HOG_STEP,
                                      _HOG_CELL, _HOG_BINS)
        logger.info("✓ HOGEmbedder inicializado (cv2+numpy, sin dlib)")

    def get_embedding(self, frame_bgr: np.ndarray,
                      face_box: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        """
        Extrae embedding 128-dim de un rostro en frame BGR.

        Args:
            frame_bgr: imagen completa en BGR
            face_box: (x, y, w, h) del bounding box

        Returns:
            np.ndarray float32[128] normalizado a norma 1, o None.
        """
        try:
            x, y, w, h = [int(v) for v in face_box[:4]]
            H, W = frame_bgr.shape[:2]

            # Expandir box 20% para dar contexto
            pad = int(max(w, h) * 0.20)
            x1, y1 = max(0, x - pad), max(0, y - pad)
            x2, y2 = min(W, x + w + pad), min(H, y + h + pad)

            crop = frame_bgr[y1:y2, x1:x2]
            if crop.size == 0:
                return None

            # Escala de grises + ecualización (invariancia a iluminación)
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)

            # Redimensionar a ventana HOG
            resized = cv2.resize(gray, _HOG_WIN, interpolation=cv2.INTER_LINEAR)

            # HOG necesita 3 canales
            rgb = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
            desc = self._hog.compute(rgb).flatten().astype(np.float32)

            # Comprimir 1764-dim → 128-dim por mean-pooling
            splits = np.array_split(desc, _EMB_SIZE)
            compact = np.array([s.mean() for s in splits], dtype=np.float32)

            # Normalizar a norma unitaria
            norm = np.linalg.norm(compact)
            if norm > 1e-6:
                compact /= norm

            return compact

        except Exception as e:
            logger.warning(f"HOGEmbedder error: {e}")
            return None


# ══════════════════════════════════════════════════════════════════════════════
# Face Detector (Haar cascade, sin dlib)
# ══════════════════════════════════════════════════════════════════════════════

class HaarDetector:
    """Detección de rostros con Haar cascade (cv2 puro)."""

    def __init__(self):
        self._clf = cv2.CascadeClassifier(_HAAR_PATH)
        if self._clf.empty():
            logger.error("No se pudo cargar haarcascade_frontalface_default.xml")
        else:
            logger.info("✓ HaarDetector inicializado")

    def detect(self, frame_bgr: np.ndarray) -> List[Dict]:
        """Retorna lista de {'box': (x,y,w,h), 'confidence': float}"""
        try:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            rects = self._clf.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60)
            )
            if len(rects) == 0:
                return []
            return [{"box": (int(x), int(y), int(w), int(h)), "confidence": 0.9}
                    for (x, y, w, h) in rects]
        except Exception as e:
            logger.debug(f"HaarDetector error: {e}")
            return []


# ══════════════════════════════════════════════════════════════════════════════
# Camera (picamera2 → OpenCV → modo sin cámara)
# ══════════════════════════════════════════════════════════════════════════════

class Camera:
    """
    Wrapper de cámara multi-backend.

    Uso:
        cam = Camera()
        if cam.open():
            frame = cam.read()   # ndarray BGR
            cam.close()
    """

    def __init__(self, width: int = 640, height: int = 480):
        self.width  = width
        self.height = height
        self._kind  = None   # 'picamera2' | 'opencv' | 'none'
        self._cam   = None
        self._lock  = threading.Lock()
        self.is_open = False

    # ── Apertura ───────────────────────────────────────────────────────────

    def open(self) -> bool:
        """Abre la cámara. Retorna True si tiene algún backend disponible."""
        if self._try_picamera2():
            return True
        if self._try_opencv():
            return True
        # Sin cámara: modo frame estático (desarrollo en PC sin cámara)
        logger.warning("Sin cámara física — modo frame estático para desarrollo")
        self._kind   = "none"
        self.is_open = True
        return True   # True para que la UI arranque aunque no haya cámara real

    def _try_picamera2(self) -> bool:
        try:
            # picamera2 puede estar en site-packages del sistema
            import sys
            for p in ["/usr/lib/python3/dist-packages",
                      "/usr/local/lib/python3/dist-packages"]:
                if p not in sys.path:
                    sys.path.insert(0, p)
            from picamera2 import Picamera2
            cam = Picamera2(0)
            cfg = cam.create_preview_configuration(
                main={"format": "RGB888", "size": (self.width, self.height)}
            )
            cam.configure(cfg)
            cam.start()
            time.sleep(0.3)
            self._cam  = cam
            self._kind = "picamera2"
            self.is_open = True
            logger.info("✓ Cámara: picamera2")
            return True
        except Exception as e:
            logger.debug(f"picamera2 no disponible: {e}")
            return False

    def _try_opencv(self) -> bool:
        for idx in range(4):
            try:
                cap = cv2.VideoCapture(idx)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                    # Verificar que entrega frames
                    ret, _ = cap.read()
                    if ret:
                        self._cam  = cap
                        self._kind = "opencv"
                        self.is_open = True
                        logger.info(f"✓ Cámara: OpenCV índice {idx}")
                        return True
                cap.release()
            except Exception:
                pass
        logger.debug("OpenCV: ninguna cámara disponible")
        return False

    # ── Lectura ────────────────────────────────────────────────────────────

    def read(self) -> Optional[np.ndarray]:
        """Retorna frame BGR (o frame sintético si no hay cámara)."""
        with self._lock:
            try:
                if self._kind == "picamera2":
                    rgb = self._cam.capture_array()          # RGB888
                    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

                elif self._kind == "opencv":
                    ret, frame = self._cam.read()
                    return frame if ret else None

                else:  # modo sin cámara → frame negro con texto
                    return self._synthetic_frame()

            except Exception as e:
                logger.warning(f"Camera.read error: {e}")
                return None

    def _synthetic_frame(self) -> np.ndarray:
        """Frame negro con texto 'SIN CÁMARA' para pruebas en PC."""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[:] = (30, 30, 30)
        cv2.putText(frame, "SIN CAMARA", (self.width//2 - 130, self.height//2 - 20),
                    cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 140, 255), 2)
        cv2.putText(frame, "Conecta una camara y reinicia",
                    (self.width//2 - 200, self.height//2 + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (150, 150, 150), 1)
        # Añadir timestamp para que el frame cambie visualmente
        t = time.strftime("%H:%M:%S")
        cv2.putText(frame, t, (20, self.height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 80, 80), 1)
        return frame

    # ── Cierre ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        with self._lock:
            try:
                if self._kind == "picamera2" and self._cam:
                    self._cam.stop()
                elif self._kind == "opencv" and self._cam:
                    self._cam.release()
            except Exception as e:
                logger.debug(f"Camera.close error: {e}")
            finally:
                self._cam    = None
                self._kind   = None
                self.is_open = False
                logger.info("Cámara liberada")

    @property
    def has_real_camera(self) -> bool:
        return self._kind in ("picamera2", "opencv")
