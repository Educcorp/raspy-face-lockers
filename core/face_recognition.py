"""
Face Recognition v2 – Versión simplificada y robusta.

Módulo completamente reescrito basándose en lo que SÍ funciona:
- Picamera2 para captura de video
- OpenCV DNN para detección de rostros
- Logging detallado para debugging
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import logging
import threading
import time
import sys
import site

from config import CAMERA_CONFIG, FACE_DETECTION_CONFIG, MODELS_DIR

logger = logging.getLogger(__name__)


# ── Helper: Importar picamera2 desde el sistema ─────────────────────────────

def _import_picamera2_from_system():
    """
    Intenta importar picamera2 desde el sistema site-packages.
    Esto es necesario porque picamera2 es un paquete del sistema en Raspberry Pi
    y puede no estar disponible en el venv.
    """
    try:
        # Primero, intentar importación normal
        import picamera2
        logger.info("✓ picamera2 importado desde venv")
        return picamera2
    except ImportError:
        pass
    
    # Si falla, intentar agregar rutas del sistema Python al path
    try:
        import site
        
        # Agregar rutas estándar donde picamera2 está en Raspberry Pi
        system_paths = [
            "/usr/lib/python3/dist-packages",         # Ruta principal en RPi
            "/usr/local/lib/python3/dist-packages",
            "/usr/lib/python3.13/dist-packages",      # Alternativa para Python 3.13
        ]
        
        for sitedir in system_paths:
            if sitedir not in sys.path:
                sys.path.insert(0, sitedir)
        
        # Reintentar importación
        import picamera2
        logger.info("✓ picamera2 importado desde site-packages del sistema")
        return picamera2
    except ImportError as e:
        logger.error(f"✗ No se pudo importar picamera2 ni del venv ni del sistema")
        logger.debug(f"  Error: {e}")
        logger.debug(f"  Rutas buscadas: {system_paths}")
        return None


# ── Face Detection ─────────────────────────────────────────────────────────

class FaceDetector:
    """Detección de rostros usando OpenCV DNN (modelo Caffe simple y robusto)."""

    def __init__(self):
        self.net = None
        self._load_model()

    def _load_model(self) -> None:
        """Carga el modelo DNN de Caffe."""
        try:
            prototxt = Path(FACE_DETECTION_CONFIG["prototxt"])
            caffemodel = Path(FACE_DETECTION_CONFIG["caffemodel"])

            if not prototxt.exists() or not caffemodel.exists():
                logger.warning(f"Modelos no encontrados en {MODELS_DIR}")
                logger.warning("La detección de rostros no funcionará")
                return

            self.net = cv2.dnn.readNetFromCaffe(str(prototxt), str(caffemodel))
            logger.info("✓ Modelo Caffe DNN cargado correctamente")

        except Exception as e:
            logger.error(f"Error cargando modelo DNN: {e}")
            self.net = None

    def detect(self, frame: np.ndarray) -> List[Dict]:
        """Detecta rostros en un frame. Retorna lista de cajas delimitadoras."""
        if self.net is None:
            return []

        try:
            h, w = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300),
                                        [104.0, 117.0, 123.0], False, False)
            self.net.setInput(blob)
            detections = self.net.forward()

            faces = []
            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence > FACE_DETECTION_CONFIG.get("confidence_threshold", 0.5):
                    x1 = int(detections[0, 0, i, 3] * w)
                    y1 = int(detections[0, 0, i, 4] * h)
                    x2 = int(detections[0, 0, i, 5] * w)
                    y2 = int(detections[0, 0, i, 6] * h)

                    faces.append({
                        "box": (x1, y1, x2 - x1, y2 - y1),
                        "confidence": float(confidence),
                    })

            return faces

        except Exception as e:
            logger.warning(f"Error detectando rostros: {e}")
            return []


# ── Camera Manager ─────────────────────────────────────────────────────────

class CameraManager:
    """Gestor de cámara usando picamera2 directamente."""

    def __init__(self):
        self.cam = None
        self.initialized = False
        self._lock = threading.Lock()
        self.face_detector = FaceDetector()

    def initialize(self) -> bool:
        """Inicializa la cámara con picamera2."""
        with self._lock:
            if self.initialized:
                logger.info("Cámara ya inicializada")
                return True

            try:
                logger.info("Importando Picamera2...")
                
                # Intentar importar picamera2 desde sistema o venv
                picamera2_module = _import_picamera2_from_system()
                if picamera2_module is None:
                    raise ImportError("Could not import picamera2")
                
                Picamera2 = picamera2_module.Picamera2

                self.cam = Picamera2(CAMERA_CONFIG.get("camera_index", 0))
                logger.info(f"Picamera2 creado (índice {CAMERA_CONFIG.get('camera_index', 0)})")

                # Configuración
                config = self.cam.create_preview_configuration(
                    main={
                        "format": "RGB888",
                        "size": (
                            CAMERA_CONFIG.get("width", 640),
                            CAMERA_CONFIG.get("height", 480),
                        )
                    }
                )
                self.cam.configure(config)
                logger.info("Configuración de cámara aplicada")

                # Iniciar captura
                self.cam.start()
                logger.info("✓ Cámara inicializada correctamente")
                self.initialized = True
                return True

            except ImportError as e:
                logger.error(f"✗ Picamera2 no disponible: {e}")
                logger.error("Instala: sudo apt install python3-picamera2")
                return False

            except PermissionError as e:
                logger.error(f"✗ Permisos denegados: {e}")
                logger.error("Ejecuta con sudo o agrega permisos a /dev/video*")
                return False

            except Exception as e:
                logger.error(f"✗ Error inicializando cámara: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                return False

    def get_frame(self) -> Optional[np.ndarray]:
        """Captura un frame de la cámara. Retorna BGR numpy array."""
        if not self.initialized or self.cam is None:
            return None

        try:
            # Picamera2 retorna RGB, convertir a BGR para OpenCV
            rgb_array = self.cam.capture_array()
            if rgb_array is None:
                return None
            bgr_frame = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
            return bgr_frame

        except Exception as e:
            logger.warning(f"Error capturando frame: {e}")
            return None

    def detect_faces(self, frame: np.ndarray) -> List[Dict]:
        """Detecta rostros en un frame."""
        if frame is None:
            return []
        return self.face_detector.detect(frame)

    def release(self) -> None:
        """Libera la cámara."""
        with self._lock:
            if self.cam is not None:
                try:
                    self.cam.stop()
                    logger.info("Cámara detenida")
                except Exception as e:
                    logger.warning(f"Error deteniendo cámara: {e}")

            self.initialized = False
            self.cam = None
            logger.info("✓ Cámara liberada")


# ── Singleton Global ──────────────────────────────────────────────────────

_camera_manager: Optional[CameraManager] = None
_camera_lock = threading.Lock()


def get_camera_manager() -> CameraManager:
    """Obtiene la instancia global del gestor de cámara."""
    global _camera_manager
    if _camera_manager is None:
        with _camera_lock:
            if _camera_manager is None:
                _camera_manager = CameraManager()
                logger.info("Creada nueva instancia de CameraManager")
    return _camera_manager


# ── Compatibilidad con código antiguo ──────────────────────────────────────

class FaceRecognitionManager:
    """
    Interfaz de compatibilidad con el código antiguo.
    Delega al CameraManager global.
    """

    def __init__(self, backend_type: str = None):
        self.manager = get_camera_manager()
        self.backend_type = "picamera2"
        self.initialized = False
        self.face_detector = self.manager.face_detector

    def initialize(self) -> bool:
        """Inicializa el manager."""
        if self.manager.initialize():
            self.initialized = True
            logger.info("✓ FaceRecognitionManager inicializado")
            return True
        return False

    def get_frame(self) -> Optional[np.ndarray]:
        """Captura un frame."""
        if not self.initialized:
            return None
        return self.manager.get_frame()

    def detect_faces_in_frame(self) -> Tuple[Optional[np.ndarray], List[Dict]]:
        """Captura un frame y detecta rostros."""
        frame = self.get_frame()
        if frame is None:
            return None, []
        faces = self.manager.detect_faces(frame)
        return frame, faces

    def release(self) -> None:
        """Libera recursos."""
        if self.initialized:
            self.manager.release()
            self.initialized = False


def get_face_recognition_manager() -> FaceRecognitionManager:
    """Compatibilidad: retorna una instancia de FaceRecognitionManager."""
    return FaceRecognitionManager()
