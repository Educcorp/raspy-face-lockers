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

try:
    import dlib
    _DLIB_AVAILABLE = True
except ImportError:
    dlib = None  # type: ignore
    _DLIB_AVAILABLE = False


# ── Helper: Corrección de iluminación mejorada ──────────────────────────────

def enhance_illumination(frame_bgr: np.ndarray) -> np.ndarray:
    """
    Mejora la iluminación del frame usando CLAHE y corrección gamma.
    Esto permite funcionar bien con contrastes difíciles (luz de fondo, cara oscura).
    Similar al preprocesamiento de Face ID de iPhone.

    Args:
        frame_bgr: Frame en formato BGR

    Returns:
        Frame mejorado en BGR
    """
    try:
        # Convertir a LAB para trabajar solo con el canal de luminancia
        lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        # Aplicar CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # Esto mejora el contraste local sin amplificar demasiado el ruido
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l)

        # Recombinar canales
        lab_enhanced = cv2.merge([l_enhanced, a, b])

        # Convertir de vuelta a BGR
        enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

        return enhanced

    except Exception as e:
        logger.debug(f"Error en enhance_illumination: {e}")
        return frame_bgr  # Retornar frame original si falla


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
        self._hog_detector = dlib.get_frontal_face_detector() if _DLIB_AVAILABLE else None
        self._haar_cascade = None
        try:
            self._haar_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            if self._haar_cascade.empty():
                self._haar_cascade = None
        except Exception:
            pass
        if _DLIB_AVAILABLE:
            logger.info("✓ FaceDetector inicializado (dlib HOG + Haar fallback)")
        else:
            logger.warning("⚠ dlib no disponible; FaceDetector usará solo Haar cascade")

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
            # OPTIMIZADO: Mejorar iluminación antes de detección
            enhanced = enhance_illumination(frame)

            # dlib necesita RGB
            rgb = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)
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
            # OPTIMIZADO: Mejorar iluminación antes de detección
            enhanced = enhance_illumination(frame)
            gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
            rects = self._haar_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60)
            )
            return [{"box": (x, y, w, h), "confidence": 0.8}
                    for (x, y, w, h) in rects] if len(rects) > 0 else []
        except Exception as e:
            logger.debug(f"Haar detection error: {e}")
            return []


# ── Face Embedding Extractor (dlib) ──────────────────────────────────────────

class FaceEmbeddingExtractor:
    """
    Extrae embeddings faciales de 128 dimensiones usando dlib.

    Pipeline:
      frame (BGR) → convertir a RGB → alinear con shape_predictor_68
      → face_recognition_resnet_model_v1 → vector float64[128]

    Se normaliza a norma unitaria para que la distancia euclidiana
    coincida con la distancia coseno.
    """

    def __init__(self):
        self.shape_predictor = None
        self.face_rec_model = None
        self._loaded = False
        self._using_fallback = False
        self._load_models()

    def _load_models(self) -> None:
        if not _DLIB_AVAILABLE:
            self._using_fallback = True
            logger.warning("⚠ dlib no disponible; usando embedding fallback (grayscale 16x8)")
            return

        sp_path = Path(FACE_RECOGNITION_CONFIG["shape_predictor"])
        rec_path = Path(FACE_RECOGNITION_CONFIG["face_rec_model"])

        if not sp_path.exists():
            logger.error(f"shape_predictor no encontrado: {sp_path}")
            self._using_fallback = True
            logger.warning("⚠ Usando embedding fallback por falta de shape_predictor")
            return
        if not rec_path.exists():
            logger.error(f"face_rec_model no encontrado: {rec_path}")
            self._using_fallback = True
            logger.warning("⚠ Usando embedding fallback por falta de modelo de reconocimiento")
            return

        try:
            self.shape_predictor = dlib.shape_predictor(str(sp_path))
            self.face_rec_model = dlib.face_recognition_model_v1(str(rec_path))
            self._loaded = True
            logger.info("✓ dlib shape_predictor + face_recognition_model cargados")
        except Exception as e:
            logger.error(f"Error cargando modelos dlib: {e}")
            self._using_fallback = True
            logger.warning("⚠ Usando embedding fallback por error cargando dlib")

    @property
    def uses_dlib(self) -> bool:
        return self._loaded

    @property
    def is_ready(self) -> bool:
        return self._loaded or self._using_fallback

    def _extract_face_roi(self, frame_bgr: np.ndarray, face_box: tuple) -> Optional[np.ndarray]:
        try:
            x, y, w, h = [int(v) for v in face_box[:4]]
            img_h, img_w = frame_bgr.shape[:2]
            if w <= 0 or h <= 0:
                return None

            pad = int(max(w, h) * 0.12)
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(img_w, x + w + pad)
            y2 = min(img_h, y + h + pad)

            if x2 <= x1 or y2 <= y1:
                return None
            return frame_bgr[y1:y2, x1:x2]
        except Exception:
            return None

    def _fallback_embedding(self, frame_bgr: np.ndarray, face_box: tuple) -> Optional[np.ndarray]:
        # OPTIMIZADO: Mejorar iluminación antes de extraer embedding fallback
        enhanced = enhance_illumination(frame_bgr)
        face_roi = self._extract_face_roi(enhanced, face_box)
        if face_roi is None or face_roi.size == 0:
            return None

        try:
            gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (16, 8), interpolation=cv2.INTER_AREA)
            vec = small.astype(np.float32).reshape(-1)
            vec -= float(np.mean(vec))
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec.astype(np.float32)
        except Exception as e:
            logger.warning(f"Error generando embedding fallback: {e}")
            return None

    def _fallback_landmarks(self, face_box: tuple) -> List[Tuple[int, int]]:
        x, y, w, h = [int(v) for v in face_box[:4]]
        if w <= 0 or h <= 0:
            return []

        def p(rx: float, ry: float) -> Tuple[int, int]:
            return (int(x + w * rx), int(y + h * ry))

        # Plantilla 68 puntos (estilo dlib) para mantener forma facial humana
        # cuando el sistema está en modo fallback sin modelos dlib.
        jaw = [
            (0.08, 0.32), (0.06, 0.40), (0.05, 0.48), (0.06, 0.57), (0.09, 0.65),
            (0.14, 0.72), (0.20, 0.78), (0.28, 0.83), (0.38, 0.86), (0.50, 0.88),
            (0.62, 0.86), (0.72, 0.83), (0.80, 0.78), (0.86, 0.72), (0.91, 0.65),
            (0.94, 0.57), (0.95, 0.48),
        ]

        brow_left = [
            (0.20, 0.28), (0.27, 0.24), (0.35, 0.22), (0.43, 0.24), (0.49, 0.28),
        ]
        brow_right = [
            (0.51, 0.28), (0.57, 0.24), (0.65, 0.22), (0.73, 0.24), (0.80, 0.28),
        ]

        nose_bridge = [
            (0.50, 0.32), (0.50, 0.40), (0.50, 0.48), (0.50, 0.56),
        ]
        nose_base = [
            (0.42, 0.62), (0.46, 0.66), (0.50, 0.67), (0.54, 0.66), (0.58, 0.62),
        ]

        eye_left = [
            (0.26, 0.36), (0.31, 0.33), (0.37, 0.33), (0.42, 0.36), (0.37, 0.39), (0.31, 0.39),
        ]
        eye_right = [
            (0.58, 0.36), (0.63, 0.33), (0.69, 0.33), (0.74, 0.36), (0.69, 0.39), (0.63, 0.39),
        ]

        mouth_outer = [
            (0.32, 0.73), (0.38, 0.70), (0.44, 0.69), (0.50, 0.70), (0.56, 0.69), (0.62, 0.70),
            (0.68, 0.73), (0.62, 0.77), (0.56, 0.79), (0.50, 0.80), (0.44, 0.79), (0.38, 0.77),
        ]
        mouth_inner = [
            (0.40, 0.73), (0.45, 0.72), (0.50, 0.73), (0.55, 0.72),
            (0.60, 0.73), (0.55, 0.76), (0.50, 0.77), (0.45, 0.76),
        ]

        groups = [
            jaw,
            brow_left,
            brow_right,
            nose_bridge,
            nose_base,
            eye_left,
            eye_right,
            mouth_outer,
            mouth_inner,
        ]

        points: List[Tuple[int, int]] = []
        for group in groups:
            points.extend([p(rx, ry) for (rx, ry) in group])
        return points

    def get_embedding(self, frame_bgr: np.ndarray,
                      face_box: tuple) -> Optional[np.ndarray]:
        """
        Extrae un embedding 128-dim de un rostro detectado.

        Args:
            frame_bgr: frame completo en BGR (tal como sale de picamera2 RGB888).
            face_box: tupla (x, y, w, h) del bounding box del rostro.

        Returns:
            np.ndarray float32[128] normalizado, o None si falla.
        """
        if self._using_fallback:
            return self._fallback_embedding(frame_bgr, face_box)

        if not self._loaded:
            return None

        try:
            # OPTIMIZADO: Mejorar iluminación antes de extraer embedding
            enhanced = enhance_illumination(frame_bgr)

            x, y, w, h = [int(v) for v in face_box[:4]]
            img_h, img_w = enhanced.shape[:2]

            # Expandir un poco el box para dar contexto al shape_predictor
            pad = int(max(w, h) * 0.15)
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(img_w, x + w + pad)
            y2 = min(img_h, y + h + pad)

            # dlib necesita RGB
            frame_rgb = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)

            # Construir dlib rectangle
            rect = dlib.rectangle(x1, y1, x2, y2)

            # Extraer landmarks (68 puntos)
            shape = self.shape_predictor(frame_rgb, rect)

            # Calcular embedding 128-dim
            face_descriptor = self.face_rec_model.compute_face_descriptor(
                frame_rgb, shape
            )
            vec = np.array(face_descriptor, dtype=np.float32)

            # Normalizar a norma unitaria
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm

            return vec

        except Exception as e:
            logger.warning(f"Error extrayendo embedding: {e}")
            return None

    def get_landmarks(self, frame_bgr: np.ndarray,
                      face_box: tuple) -> Optional[List[Tuple[int, int]]]:
        """
        Extrae los 68 landmarks faciales.

        Returns:
            Lista de 68 tuplas (x, y), o None si falla.
        """
        if self._using_fallback:
            return self._fallback_landmarks(face_box)

        if not self._loaded:
            return None

        try:
            # OPTIMIZADO: Mejorar iluminación antes de extraer landmarks
            enhanced = enhance_illumination(frame_bgr)

            x, y, w, h = [int(v) for v in face_box[:4]]
            img_h, img_w = enhanced.shape[:2]
            pad = int(max(w, h) * 0.15)
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(img_w, x + w + pad)
            y2 = min(img_h, y + h + pad)

            frame_rgb = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)
            rect = dlib.rectangle(x1, y1, x2, y2)
            shape = self.shape_predictor(frame_rgb, rect)

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
