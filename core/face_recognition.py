"""
Face Recognition v3 – Detección + Embeddings reales con dlib.

Pipeline:
  1. Picamera2 → captura de video (formato RGB888 / BGR en memoria)
  2. OpenCV DNN SSD → detección rápida de rostros (bounding boxes)
  3. dlib shape_predictor_68 → landmarks faciales (68 puntos)
  4. dlib face_recognition_resnet_model_v1 → embedding 128-dim

La detección DNN es rápida (~30 ms en Pi 5).
El embedding dlib es más pesado (~200 ms) pero muy preciso.
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

from config import (
    CAMERA_CONFIG, FACE_DETECTION_CONFIG, FACE_RECOGNITION_CONFIG, MODELS_DIR,
)

logger = logging.getLogger(__name__)


def _import_dlib_from_system():
    """
    Intenta importar dlib desde el entorno actual o desde site-packages del sistema.
    """
    try:
        import dlib as _dlib
        logger.info("✓ dlib importado desde venv")
        return _dlib
    except ImportError:
        pass

    system_paths = [
        "/usr/lib/python3/dist-packages",
        "/usr/local/lib/python3/dist-packages",
        "/usr/lib/python3.13/dist-packages",
    ]

    for sitedir in system_paths:
        if sitedir not in sys.path:
            sys.path.insert(0, sitedir)

    try:
        import dlib as _dlib
        logger.info("✓ dlib importado desde site-packages del sistema")
        return _dlib
    except ImportError as e:
        logger.error("✗ No se pudo importar dlib ni del venv ni del sistema")
        logger.debug(f"  Error: {e}")
        return None


dlib = _import_dlib_from_system()
DLIB_AVAILABLE = dlib is not None

if not DLIB_AVAILABLE:
    logger.warning("dlib no disponible: usando Haar cascade para detección")
    logger.warning("dlib no está instalado; embeddings faciales SERÁN manejados por backend HOG (cv2)")


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
    """
    Detección de rostros usando dlib HOG (primario) + Haar cascade (fallback).

    El modelo OpenCV DNN SSD no es compatible con OpenCV 4.13+, así que
    usamos el detector HOG frontal de dlib que es rápido y robusto.
    """

    def __init__(self):
        self._hog_detector = dlib.get_frontal_face_detector() if DLIB_AVAILABLE else None
        self._haar_cascade = None
        try:
            self._haar_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            if self._haar_cascade.empty():
                self._haar_cascade = None
        except Exception:
            pass
        if self._hog_detector is not None:
            logger.info("✓ FaceDetector inicializado (dlib HOG + Haar fallback)")
        else:
            logger.warning("⚠ FaceDetector inicializado sin dlib (solo Haar fallback)")

    def detect(self, frame: np.ndarray) -> List[Dict]:
        """Detecta rostros en un frame BGR. Retorna lista de dicts con 'box'."""
        faces = self._detect_hog(frame)
        if not faces and self._haar_cascade is not None:
            faces = self._detect_haar(frame)
        return faces

    def _detect_hog(self, frame: np.ndarray) -> List[Dict]:
        """Detector HOG de dlib – rápido y preciso para caras frontales."""
        if self._hog_detector is None:
            return []
        try:
            # dlib necesita RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Reducir resolución para velocidad en Pi
            h, w = rgb.shape[:2]
            scale = 1.0
            if w > 400:
                scale = 400.0 / w
                small = cv2.resize(rgb, (int(w * scale), int(h * scale)))
            else:
                small = rgb

            dets = self._hog_detector(small, 0)  # 0 = no upsampling

            faces = []
            for d in dets:
                x1 = int(d.left() / scale)
                y1 = int(d.top() / scale)
                x2 = int(d.right() / scale)
                y2 = int(d.bottom() / scale)
                faces.append({
                    "box": (x1, y1, x2 - x1, y2 - y1),
                    "confidence": 1.0,
                })
            return faces
        except Exception as e:
            logger.debug(f"HOG detection error: {e}")
            return []

    def _detect_haar(self, frame: np.ndarray) -> List[Dict]:
        """Fallback Haar cascade."""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rects = self._haar_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60)
            )
            return [{"box": (x, y, w, h), "confidence": 0.8}
                    for (x, y, w, h) in rects] if len(rects) > 0 else []
        except Exception as e:
            logger.debug(f"Haar detection error: {e}")
            return []


# ── Face Embedding Extractor ─────────────────────────────────────────────────

class FaceEmbeddingExtractor:
    """
    Extrae embeddings faciales de 128 dimensiones.

    Backend primario: dlib face_recognition_resnet_model_v1 (si dlib está instalado).
    Backend fallback: HOG descriptor cv2+numpy (128-dim normalizado).

    Ambos backends producen vectores float32 normalizados a norma unitaria,
    de forma que la distancia euclidiana es comparable entre sesiones
    siempre que se use el mismo backend.
    """

    # HOG params  (64×64 px crop, celdas 8×8, bloque 16×16, 9 bins)
    _HOG_WIN   = (64, 64)
    _HOG_BLOCK = (16, 16)
    _HOG_STEP  = (8, 8)
    _HOG_CELL  = (8, 8)
    _HOG_BINS  = 9
    # Total HOG dims = 1764 → tomamos los 128 primeros después de normalizar
    HOG_EMB_SIZE = 128

    def __init__(self):
        self._use_dlib = False
        self._shape_predictor = None
        self._face_rec_model  = None
        self._loaded = False
        self._hog = cv2.HOGDescriptor(
            self._HOG_WIN,
            self._HOG_BLOCK,
            self._HOG_STEP,
            self._HOG_CELL,
            self._HOG_BINS,
        )
        self._load_models()

    def _load_models(self) -> None:
        """Intenta cargar los modelos dlib. Si no es posible, usa backend HOG."""
        if DLIB_AVAILABLE:
            sp_path  = Path(FACE_RECOGNITION_CONFIG["shape_predictor"])
            rec_path = Path(FACE_RECOGNITION_CONFIG["face_rec_model"])

            if sp_path.exists() and rec_path.exists():
                try:
                    self._shape_predictor = dlib.shape_predictor(str(sp_path))
                    self._face_rec_model  = dlib.face_recognition_model_v1(str(rec_path))
                    self._use_dlib = True
                    self._loaded   = True
                    logger.info("✓ Backend dlib cargado (shape_predictor + face_recognition_model)")
                    return
                except Exception as e:
                    logger.error(f"Error cargando modelos dlib: {e}")
            else:
                logger.warning("Modelos dlib (.dat) no encontrados en assets/models/")

        # Fallback: HOG (siempre disponible con cv2)
        self._use_dlib = False
        self._loaded   = True
        logger.info("✓ Backend HOG (cv2) activo como extractor de embeddings")

    @property
    def is_ready(self) -> bool:
        return self._loaded

    # ── Embedding HOG ─────────────────────────────────────────────────────────

    def _hog_embedding(self, face_crop_gray: np.ndarray) -> Optional[np.ndarray]:
        """
        Calcula un embedding de 128-dim a partir de un recorte facial en escala de grises
        usando HOG. El vector se normaliza a norma unitaria.
        """
        try:
            # Redimensionar a tamaño fijo
            face_resized = cv2.resize(face_crop_gray, self._HOG_WIN,
                                      interpolation=cv2.INTER_LINEAR)
            # HOG necesita imagen de 3 canales
            face_bgr = cv2.cvtColor(face_resized, cv2.COLOR_GRAY2BGR)
            descriptor = self._hog.compute(face_bgr)          # shape: (1764,)
            vec = descriptor.flatten().astype(np.float32)

            # Reducir a 128 dim con suma-de-bloques (bin aggregation)
            # 1764 dims → agrupar en 128 bins de 13~14 valores cada uno
            split = np.array_split(vec, self.HOG_EMB_SIZE)
            compact = np.array([chunk.mean() for chunk in split], dtype=np.float32)

            # Normalizar a norma unitaria
            norm = np.linalg.norm(compact)
            if norm > 1e-6:
                compact = compact / norm
            return compact
        except Exception as e:
            logger.warning(f"HOG embedding error: {e}")
            return None

    # ── API pública ───────────────────────────────────────────────────────────

    def get_embedding(self, frame_bgr: np.ndarray,
                      face_box: tuple) -> Optional[np.ndarray]:
        """
        Extrae un embedding 128-dim de un rostro detectado.

        Args:
            frame_bgr: frame completo en BGR.
            face_box:  tupla (x, y, w, h) del bounding box del rostro.

        Returns:
            np.ndarray float32[128] normalizado, o None si falla.
        """
        try:
            x, y, w, h = [int(v) for v in face_box[:4]]
            img_h, img_w = frame_bgr.shape[:2]

            # Expandir bounding box un 20% para dar contexto
            pad = int(max(w, h) * 0.20)
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(img_w, x + w + pad)
            y2 = min(img_h, y + h + pad)

            if self._use_dlib:
                # ── Backend dlib ──
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                rect = dlib.rectangle(x1, y1, x2, y2)
                shape = self._shape_predictor(frame_rgb, rect)
                descriptor = self._face_rec_model.compute_face_descriptor(
                    frame_rgb, shape
                )
                vec = np.array(descriptor, dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 1e-6:
                    vec = vec / norm
                return vec
            else:
                # ── Backend HOG ──
                crop = frame_bgr[y1:y2, x1:x2]
                if crop.size == 0:
                    return None
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                # Ecualización de histograma para invariancia a iluminación
                gray = cv2.equalizeHist(gray)
                return self._hog_embedding(gray)

        except Exception as e:
            logger.warning(f"Error extrayendo embedding: {e}")
            return None

    def get_landmarks(self, frame_bgr: np.ndarray,
                      face_box: tuple) -> Optional[List[Tuple[int, int]]]:
        """
        Extrae los 68 landmarks faciales (solo disponible con backend dlib).
        Con HOG retorna None (sin landmarks).
        """
        if not self._use_dlib:
            return None
        try:
            x, y, w, h = [int(v) for v in face_box[:4]]
            img_h, img_w = frame_bgr.shape[:2]
            pad = int(max(w, h) * 0.15)
            x1, y1 = max(0, x - pad), max(0, y - pad)
            x2, y2 = min(img_w, x + w + pad), min(img_h, y + h + pad)
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            rect  = dlib.rectangle(x1, y1, x2, y2)
            shape = self._shape_predictor(frame_rgb, rect)
            return [(shape.part(i).x, shape.part(i).y) for i in range(68)]
        except Exception as e:
            logger.warning(f"Error extrayendo landmarks: {e}")
            return None

    def compare_embeddings(self, emb_a: np.ndarray,
                           emb_b: np.ndarray) -> float:
        """Distancia euclidiana entre dos embeddings (menor = más parecido)."""
        return float(np.linalg.norm(emb_a - emb_b))


# ── Camera Manager ─────────────────────────────────────────────────────────

class CameraManager:
    """Gestor de cámara usando picamera2 directamente."""

    def __init__(self):
        self.cam = None
        self.initialized = False
        self._lock = threading.Lock()
        self.face_detector = FaceDetector()
        self.embedding_extractor = FaceEmbeddingExtractor()

    def initialize(self) -> bool:
        """Inicializa la cámara con picamera2."""
        with self._lock:
            if self.initialized:
                logger.debug("Cámara ya inicializada")
                return True

            try:
                logger.info("Inicializando cámara...")
                
                # Si la cámara estaba inicializada antes, limpiar estado
                if self.cam is not None:
                    try:
                        logger.debug("Limpiando cámara anterior...")
                        self.cam.stop()
                        time.sleep(0.1)
                    except Exception as e:
                        logger.debug(f"Error limpiando cámara anterior: {e}")
                    self.cam = None
                
                # Importar picamera2
                picamera2_module = _import_picamera2_from_system()
                if picamera2_module is None:
                    raise ImportError("Could not import picamera2")
                
                Picamera2 = picamera2_module.Picamera2
                logger.debug("Creando instancia de Picamera2...")

                self.cam = Picamera2(CAMERA_CONFIG.get("camera_index", 0))
                logger.debug(f"✓ Picamera2 creado (índice {CAMERA_CONFIG.get('camera_index', 0)})")

                # Configuración
                logger.debug("Configurando cámara...")
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
                logger.debug("✓ Configuración de cámara aplicada")

                # Iniciar captura
                logger.debug("Iniciando captura...")
                self.cam.start()
                logger.debug("✓ Captura iniciada")
                
                # Esperar a que el buffer de picamera2 se establezca
                time.sleep(0.5)
                
                logger.info("✓ Cámara inicializada correctamente")
                self.initialized = True
                return True

            except ImportError as e:
                logger.error(f"✗ Picamera2 no disponible: {e}")
                logger.error("Instala: sudo apt install python3-picamera2")
                self.initialized = False
                return False

            except PermissionError as e:
                logger.error(f"✗ Permisos denegados: {e}")
                logger.error("Ejecuta con sudo o agrega permisos a /dev/video*")
                self.initialized = False
                return False

            except Exception as e:
                logger.error(f"✗ Error inicializando cámara: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                self.initialized = False
                self.cam = None
                return False

    def get_frame(self) -> Optional[np.ndarray]:
        """Captura un frame de la cámara. Retorna el array sin conversión."""
        if not self.initialized or self.cam is None:
            return None

        try:
            # Picamera2 retorna el frame directamente
            # Sin conversiones de canales - usar tal cual para evitar confusión
            frame_array = self.cam.capture_array()
            return frame_array

        except Exception as e:
            logger.warning(f"Error capturando frame: {e}")
            return None

    def detect_faces(self, frame: np.ndarray) -> List[Dict]:
        """Detecta rostros en un frame."""
        if frame is None:
            return []
        return self.face_detector.detect(frame)

    def release(self) -> None:
        """Libera la cámara completa y resetea el estado."""
        with self._lock:
            logger.info("Liberando cámara...")
            
            try:
                if self.cam is not None:
                    try:
                        self.cam.stop()
                        logger.debug("✓ Cámara detenida")
                    except Exception as e:
                        logger.debug(f"Error deteniendo cámara: {e}")
                    
                    try:
                        del self.cam
                        logger.debug("✓ Instancia de cámara eliminada")
                    except Exception as e:
                        logger.debug(f"Error eliminando instancia: {e}")
            except Exception as e:
                logger.debug(f"Error en release: {e}")
            finally:
                self.initialized = False
                self.cam = None
                logger.info("✓ Cámara completamente liberada")
        
        # CRÍTICO: Reset global singleton después de liberar
        global _camera_manager
        _camera_manager = None
        logger.info("✓ Singleton global resetado")


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
    Interfaz principal de reconocimiento facial.
    Combina cámara + detección DNN + embeddings dlib.
    """

    def __init__(self, backend_type: str = None):
        self.manager = get_camera_manager()
        self.backend_type = "picamera2"
        self.initialized = False
        self.face_detector = self.manager.face_detector
        self.embedding_extractor = self.manager.embedding_extractor

    def initialize(self) -> bool:
        """Inicializa el manager."""
        if self.manager.initialize():
            self.initialized = True
            logger.info("✓ FaceRecognitionManager inicializado")
            logger.info(f"  Embeddings dlib: {'OK' if self.embedding_extractor.is_ready else 'NO DISPONIBLE'}")
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

    def get_embedding(self, frame: np.ndarray,
                      face_box: tuple = None) -> Optional[np.ndarray]:
        """
        Extrae embedding 128-dim de un frame.
        Si no se provee face_box, detecta automáticamente el primer rostro.
        """
        if face_box is None:
            faces = self.manager.detect_faces(frame)
            if not faces:
                return None
            face_box = faces[0]["box"]
        return self.embedding_extractor.get_embedding(frame, face_box)

    def get_landmarks(self, frame: np.ndarray,
                      face_box: tuple) -> Optional[List[Tuple[int, int]]]:
        """Extrae 68 landmarks faciales."""
        return self.embedding_extractor.get_landmarks(frame, face_box)

    def release(self) -> None:
        """Libera recursos."""
        if self.initialized:
            self.manager.release()
            self.initialized = False


def get_face_recognition_manager() -> FaceRecognitionManager:
    """Retorna una instancia de FaceRecognitionManager."""
    return FaceRecognitionManager()
