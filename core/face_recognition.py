"""
Face Recognition Module – Detección y reconocimiento de rostros.

Soporta múltiples backends de cámara:
  - libcamera  (Raspberry Pi 5+)
  - picamera2  (Raspberry Pi legacy/new)
  - OpenCV     (genérico)
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from abc import ABC, abstractmethod
import logging

from config import (
    CAMERA_CONFIG,
    FACE_DETECTION_CONFIG,
    MODELS_DIR,
)

logger = logging.getLogger(__name__)


# ── Interfaces ───────────────────────────────────────────────────────────

class CameraBackend(ABC):
    """Interfaz abstracta para diferentes backends de cámara."""

    @abstractmethod
    def initialize(self) -> bool:
        """Inicializa la cámara. Retorna True si éxito."""
        pass

    @abstractmethod
    def capture_frame(self) -> Optional[np.ndarray]:
        """Captura un frame. Retorna BGR numpy array o None en error."""
        pass

    @abstractmethod
    def release(self) -> None:
        """Libera recursos de cámara."""
        pass


# ── OpenCV Backend ──────────────────────────────────────────────────────

class OpenCVBackend(CameraBackend):
    """Backend de cámara usando OpenCV (funciona con V4L2 en RPi)."""

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.cap = None
        self.initialized = False

    def initialize(self) -> bool:
        """Intenta abrir la cámara con OpenCV."""
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                logger.error(f"No se pudo abrir cámara índice {self.camera_index}")
                return False

            # Configurar resolución y FPS
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_CONFIG["width"])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_CONFIG["height"])
            self.cap.set(cv2.CAP_PROP_FPS, CAMERA_CONFIG["fps"])

            # Prueba: capturar un frame
            ret, _ = self.cap.read()
            if not ret:
                logger.error("No se puede capturar frames de cámara")
                self.cap.release()
                return False

            self.initialized = True
            logger.info(f"Cámara inicializada (OpenCV, índice {self.camera_index})")
            return True

        except Exception as e:
            logger.error(f"Error inicializando cámara OpenCV: {e}")
            return False

    def capture_frame(self) -> Optional[np.ndarray]:
        """Captura un frame de la cámara."""
        if not self.initialized or self.cap is None:
            return None

        try:
            ret, frame = self.cap.read()
            if not ret:
                logger.warning("Error capturando frame")
                return None
            return frame
        except Exception as e:
            logger.error(f"Error en capture_frame: {e}")
            return None

    def release(self) -> None:
        """Libera la cámara."""
        if self.cap is not None:
            self.cap.release()
            self.initialized = False
            logger.info("Cámara liberada")


class Picamera2Backend(CameraBackend):
    """Backend para picamera2 (Raspberry Pi nueva generación)."""

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.cam = None
        self.initialized = False

    def initialize(self) -> bool:
        """Inicializa picamera2."""
        try:
            from picamera2 import Picamera2
            from libcamera import Transform

            self.cam = Picamera2(self.camera_index)
            # Use default config which handles auto-sizing
            config = self.cam.create_preview_configuration(
                main={"format": "RGB888", "size": (CAMERA_CONFIG["width"], CAMERA_CONFIG["height"])}
            )
            self.cam.configure(config)
            self.cam.start()
            self.initialized = True
            logger.info(f"Cámara inicializada (Picamera2, índice {self.camera_index})")
            return True

        except ImportError as e:
            logger.error(f"Dependencia picamera2 no está instalada: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inicializando Picamera2: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def capture_frame(self) -> Optional[np.ndarray]:
        """Captura un frame con picamera2."""
        if not self.initialized or self.cam is None:
            return None

        try:
            # picamera2 devuelve frames en RGB, convertir a BGR para OpenCV
            array = self.cam.capture_array()
            if array is None:
                return None
            # Convertir RGB → BGR
            return cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.error(f"Error en Picamera2 capture_frame: {e}")
            return None

    def release(self) -> None:
        """Libera picamera2."""
        if self.cam is not None:
            try:
                self.cam.stop()
            except:
                pass
            self.initialized = False
            logger.info("Cámara picamera2 liberada")


# ── Face Detection Module ──────────────────────────────────────────────────

class FaceDetector:
    """Detección de rostros usando OpenCV DNN."""

    def __init__(self):
        self.net = None
        self.confidence_threshold = FACE_DETECTION_CONFIG["confidence_threshold"]
        self._load_model()

    def _load_model(self) -> None:
        """Carga el modelo Caffe DNN para detección de rostros."""
        try:
            prototxt = Path(FACE_DETECTION_CONFIG["prototxt"])
            caffemodel = Path(FACE_DETECTION_CONFIG["caffemodel"])

            if not prototxt.exists() or not caffemodel.exists():
                logger.warning(
                    f"Modelos no encontrados en {MODELS_DIR}. "
                    f"Será necesario descargarlos."
                )
                return

            self.net = cv2.dnn.readNetFromCaffe(str(prototxt), str(caffemodel))
            logger.info("Modelo DNN de detección de rostros cargado")

        except Exception as e:
            logger.error(f"Error cargando modelo de detección: {e}")
            self.net = None

    def detect(self, frame: np.ndarray) -> List[Dict]:
        """
        Detecta rostros en el frame.

        Retorna lista de dicts con: {'box': (x,y,w,h), 'confidence': float}
        """
        if self.net is None:
            return []

        try:
            h, w = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300),
                                         [104.0, 117.0, 123.0], False, False)
            self.net.setInput(blob)
            detections = self.net.forward()

            faces = []
            for i in range(0, detections.shape[2]):
                confidence = detections[0, 0, i, 2]

                if confidence < self.confidence_threshold:
                    continue

                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = box.astype(int)
                x, y, w, h = x1, y1, x2 - x1, y2 - y1

                faces.append({
                    "box": (x, y, w, h),
                    "confidence": float(confidence),
                })

            return faces

        except Exception as e:
            logger.error(f"Error en detección de rostros: {e}")
            return []


# ── Face Recognition Manager ───────────────────────────────────────────────

class FaceRecognitionManager:
    """
    Gestor de reconocimiento facial.

    Coordina:
      - Acceso a cámara (múltiples backends)
      - Detección de rostros
      - Reconocimiento (futura extensión)
    """

    def __init__(self, backend_type: str = None):
        self.backend_type = backend_type or self._detect_platform()
        self.camera_backend: Optional[CameraBackend] = None
        self.face_detector = FaceDetector()
        self.initialized = False

    @staticmethod
    def _detect_platform() -> str:
        """Detecta la plataforma y retorna el backend recomendado."""
        try:
            # Intenta importar desde system site-packages
            import sys
            import importlib.util
            
            # Buscar picamera2 en el sistema
            spec = importlib.util.find_spec("picamera2")
            if spec is not None:
                logger.info("Plataforma Raspberry Pi detectada, usando picamera2")
                return "picamera2"
        except:
            pass
        
        logger.info("picamera2 no disponible, usando fallback (OpenCV)")
        return "opencv"

    def initialize(self) -> bool:
        """Inicializa el sistema de reconocimiento facial."""
        try:
            # Intentar con el backend preferido
            backends_to_try = []
            
            if self.backend_type == "picamera2":
                backends_to_try = [
                    ("picamera2", Picamera2Backend(CAMERA_CONFIG["camera_index"])),
                    ("opencv", OpenCVBackend(CAMERA_CONFIG["camera_index"])),
                ]
            else:
                backends_to_try = [
                    ("opencv", OpenCVBackend(CAMERA_CONFIG["camera_index"])),
                    ("picamera2", Picamera2Backend(CAMERA_CONFIG["camera_index"])),
                ]

            for backend_name, backend_instance in backends_to_try:
                logger.info(f"Intentando inicializar backend: {backend_name}")
                if backend_instance.initialize():
                    self.camera_backend = backend_instance
                    logger.info(f"Backend {backend_name} inicializado exitosamente")
                    self.initialized = True
                    return True
                else:
                    logger.debug(f"Backend {backend_name} falló")

            logger.error("No se pudo inicializar ningún backend de cámara")
            return False

        except Exception as e:
            logger.error(f"Error inicializando FaceRecognitionManager: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def detect_faces_in_frame(self) -> Tuple[Optional[np.ndarray], List[Dict]]:
        """
        Captura un frame y detecta rostros.

        Retorna: (frame, lista_de_rostros_detectados)
        """
        if not self.initialized or self.camera_backend is None:
            return None, []

        frame = self.camera_backend.capture_frame()
        if frame is None:
            return None, []

        faces = self.face_detector.detect(frame)
        return frame, faces

    def get_frame(self) -> Optional[np.ndarray]:
        """Captura un frame simple sin procesamiento."""
        if not self.initialized or self.camera_backend is None:
            return None
        return self.camera_backend.capture_frame()

    def release(self) -> None:
        """Libera recursos."""
        if self.camera_backend is not None:
            self.camera_backend.release()
        self.initialized = False


# ── Singleton para acceso global ──────────────────────────────────────────

_face_recognition_manager: Optional[FaceRecognitionManager] = None


def get_face_recognition_manager() -> FaceRecognitionManager:
    """Obtiene la instancia global del manager de reconocimiento facial."""
    global _face_recognition_manager
    if _face_recognition_manager is None:
        _face_recognition_manager = FaceRecognitionManager()
    return _face_recognition_manager
