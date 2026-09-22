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
    ANTI_SPOOF_CONFIG, CAMERA_CONFIG, FACE_DETECTION_CONFIG, FACE_RECOGNITION_CONFIG, MODELS_DIR,
)

logger = logging.getLogger(__name__)

# ── Filtro de distancia ─────────────────────────────────────────────────────
# Cara debe ocupar al menos MIN_FACE_SIZE_RATIO del ancho del frame (~1 metro).
# Pi Camera v2/3 ≈ 62° HFOV; a 1 m un rostro adulto ocupa ~82 px en 480 px.
MIN_FACE_SIZE_RATIO: float = 0.17


def filter_close_faces(faces: list, frame) -> list:
    """Retiene solo las caras dentro del rango de ~1 metro.

    Filtra por bounding box: la cara debe tener un ancho >= MIN_FACE_SIZE_RATIO
    del ancho del frame. Esto evita detectar rostros o movimientos lejanos.
    """
    if not faces:
        return faces
    frame_w = frame.shape[1] if frame is not None else 480
    min_w = max(60, int(frame_w * MIN_FACE_SIZE_RATIO))
    return [f for f in faces if (f.get("box") or (0, 0, 0, 0))[2] >= min_w]


# Rutas de site-packages del sistema. En Raspberry Pi, dlib, onnxruntime y
# picamera2 se instalan con apt (PEP 668 impide hacerlo con pip), así que viven
# SOLO en el Python del sistema. Si la app se lanza desde un venv creado sin
# --system-site-packages, esos módulos no se ven.
def _system_site_paths() -> list[str]:
    """Rutas donde viven los paquetes fuera del venv.

    Incluye el site-packages de USUARIO (~/.local/...), no solo los
    dist-packages del sistema: dlib está instalado ahí con `pip --user`, y un
    venv lo excluye igual que a los del sistema.
    """
    ver = f"python3.{sys.version_info.minor}"
    paths = [
        f"/usr/lib/python3/dist-packages",
        f"/usr/local/lib/{ver}/dist-packages",
        f"/usr/lib/{ver}/dist-packages",
    ]
    try:
        # En un venv, getusersitepackages() sigue devolviendo la ruta real
        # del usuario aunque el venv la tenga deshabilitada.
        paths.insert(0, site.getusersitepackages())
    except Exception:
        paths.insert(0, str(Path.home() / ".local" / "lib" / ver / "site-packages"))
    return paths


def _add_system_site_packages() -> None:
    """Añade esas rutas a sys.path (idempotente)."""
    for path in _system_site_paths():
        if path and path not in sys.path and Path(path).is_dir():
            sys.path.append(path)


_DLIB_IMPORT_ERROR: str | None = None
try:
    import dlib
    _DLIB_AVAILABLE = True
except ImportError:
    # Segundo intento desde el sistema. Sin esto, arrancar desde el venv dejaba
    # el reconocimiento en modo fallback 'grayscale 16x8' silenciosamente: los
    # rostros guardados son 'dlib_resnet_v1', así que NINGUNO podía coincidir y
    # todo acceso se denegaba. El log decía "Embeddings dlib: OK" porque
    # is_ready también es True en modo fallback.
    _add_system_site_packages()
    try:
        import dlib
        _DLIB_AVAILABLE = True
        logger.info("✓ dlib importado desde site-packages del sistema")
    except ImportError as e:
        dlib = None  # type: ignore
        _DLIB_AVAILABLE = False
        _DLIB_IMPORT_ERROR = str(e)
        logger.error(f"✗ dlib no se pudo importar: {e}")


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

# Ancho al que se reduce el frame antes de detectar. La cámara entrega
# 1296x972, pero los detectores no ganan nada con esa resolución y sí pagan
# mucho: se trabaja a 400px de ancho y las cajas se reescalan después.
_DETECTION_WIDTH = 400


def _downscale_for_detection(frame: np.ndarray) -> Tuple[np.ndarray, float]:
    """Reduce el frame a _DETECTION_WIDTH de ancho.

    Devuelve (imagen_reducida, escala), donde `escala` es el factor aplicado:
    una coordenada de la imagen reducida se lleva al frame original
    dividiéndola entre `escala`.
    """
    h, w = frame.shape[:2]
    if w <= _DETECTION_WIDTH:
        return frame, 1.0
    scale = _DETECTION_WIDTH / float(w)
    return cv2.resize(frame, (int(w * scale), int(h * scale))), scale

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
            logger.warning(f"⚠ dlib no disponible ({_DLIB_IMPORT_ERROR}); FaceDetector usará solo Haar cascade")

    def detect(self, frame: np.ndarray) -> List[Dict]:
        """Detecta rostros en un frame BGR. Retorna lista de dicts con 'box'."""
        # La reducción y el CLAHE se hacen UNA vez y se comparten con ambos
        # detectores: antes, cuando HOG no encontraba nada, Haar repetía todo
        # el preprocesado desde el frame original.
        try:
            small_bgr, scale = _downscale_for_detection(frame)
            prepared = (enhance_illumination(small_bgr), scale)
        except Exception as exc:
            logger.debug("Preprocesado de detección falló: %s", exc)
            prepared = None

        faces = self._detect_hog(frame, prepared)
        if not faces and self._haar_cascade is not None:
            faces = self._detect_haar(frame, prepared)
        return faces

    def _detect_hog(self, frame: np.ndarray, prepared=None) -> List[Dict]:
        """Detector HOG de dlib – rápido y preciso para caras frontales.

        `prepared` es la tupla (imagen_bgr_reducida_y_ecualizada, escala) que
        ya calculó detect(); si viene None se calcula aquí.
        """
        if self._hog_detector is None:
            return []
        try:
            # Se reduce PRIMERO y se ecualiza después. Al revés, el CLAHE
            # corría sobre el frame completo (1296x972 = ~39 ms) para luego
            # tirar el 90% de esos píxeles al escalar a 400px. Sobre la imagen
            # ya reducida cuesta una fracción y la detección no cambia, porque
            # es exactamente la imagen que ve el detector.
            if prepared is None:
                small_bgr, scale = _downscale_for_detection(frame)
                enhanced = enhance_illumination(small_bgr)
            else:
                enhanced, scale = prepared

            # dlib necesita RGB
            small = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)

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

    def _detect_haar(self, frame: np.ndarray, prepared=None) -> List[Dict]:
        """Fallback Haar cascade. `prepared`: ver _detect_hog."""
        try:
            # Mismo criterio que _detect_hog: detectMultiScale sobre el frame
            # completo costaba ~151 ms por cuadro. Se trabaja sobre la imagen
            # reducida y las cajas se reescalan a coordenadas del frame real.
            if prepared is None:
                small_bgr, scale = _downscale_for_detection(frame)
                enhanced = enhance_illumination(small_bgr)
            else:
                enhanced, scale = prepared
            gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
            # minSize acompaña la escala: 60px en el frame original son
            # 60*scale px en la imagen reducida.
            min_side = max(20, int(60 * scale))
            rects = self._haar_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4, minSize=(min_side, min_side)
            )
            return [{"box": (int(x / scale), int(y / scale),
                             int(w / scale), int(h / scale)), "confidence": 0.8}
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
        # Detector propio, usado solo para refinar la caja a resolución
        # completa antes de extraer landmarks (ver _refine_rect).
        self._hog_detector = dlib.get_frontal_face_detector() if _DLIB_AVAILABLE else None
        self._load_models()

    def _load_models(self) -> None:
        if not _DLIB_AVAILABLE:
            self._using_fallback = True
            logger.warning(f"⚠ dlib no disponible ({_DLIB_IMPORT_ERROR}); usando embedding fallback (grayscale 16x8)")
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
            # NO se aplica enhance_illumination aquí: CLAHE es adaptativo por
            # frame, así que el mismo rostro con encuadre ligeramente distinto
            # recibe una normalización distinta y el embedding se vuelve
            # inestable. El descriptor de dlib se entrenó con imágenes
            # naturales, así que se le pasa el frame sin ecualizar.
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

            # El shape_predictor de dlib espera exactamente la caja que produce
            # su propio detector: agrandarla desalinea los 68 landmarks y
            # degrada el descriptor. Se refina a resolución completa en vez de
            # reutilizar la caja escalada desde la detección a 400px.
            rect = self._refine_rect(frame_rgb, face_box)

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

    def _refine_rect(self, frame_rgb: np.ndarray, face_box: tuple) -> "dlib.rectangle":
        """
        Devuelve la caja del rostro tal como la produciría el detector de dlib
        a resolución completa.

        La detección del bucle de video corre sobre una imagen reducida a
        400px por velocidad, así que su caja trae un error de cuantización que
        se amplifica al reescalarla (~3px por cada píxel a 400px). Ese temblor
        se propaga a los landmarks y hace que el mismo rostro produzca
        embeddings distintos entre frames. Aquí se re-detecta sobre un ROI
        pequeño a resolución nativa, que es rápido y da una caja estable.
        """
        x, y, w, h = [int(v) for v in face_box[:4]]
        img_h, img_w = frame_rgb.shape[:2]

        if self._hog_detector is not None:
            margin = int(max(w, h) * 0.4)
            # Los límites del ROI se cuantizan a una rejilla de 16px para que
            # un temblor pequeño en la caja de entrada caiga en el mismo ROI y
            # la re-detección devuelva exactamente la misma caja. Sin esto, el
            # refinado hereda parte del temblor que intenta corregir.
            grid = 16
            rx1 = max(0, ((x - margin) // grid) * grid)
            ry1 = max(0, ((y - margin) // grid) * grid)
            rx2 = min(img_w, -(-(x + w + margin) // grid) * grid)
            ry2 = min(img_h, -(-(y + h + margin) // grid) * grid)
            roi = frame_rgb[ry1:ry2, rx1:rx2]
            if roi.size:
                try:
                    # El upsample duplica la imagen antes de buscar, lo que
                    # cuadruplica el costo (se midió 343 ms en un ROI de
                    # 720x720 contra 82 ms sin él). Solo hace falta cuando la
                    # cara es pequeña: HOG necesita ~80px de lado para
                    # detectarla, así que por encima de ese margen se omite.
                    upsample = 1 if max(w, h) < 150 else 0
                    dets = self._hog_detector(roi, upsample)
                    if dets:
                        d = max(dets, key=lambda r: r.width() * r.height())
                        return dlib.rectangle(
                            rx1 + d.left(), ry1 + d.top(),
                            rx1 + d.right(), ry1 + d.bottom(),
                        )
                except Exception as err:
                    logger.debug("Refinado de caja falló, usando la original: %s", err)

        # Sin refinamiento posible: la caja del detector, sin padding.
        return dlib.rectangle(x, y, x + w, y + h)

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


try:
    import onnxruntime as ort
    _ORT_AVAILABLE = True
except ImportError:
    # Igual que dlib: en la Pi se instala con apt y solo existe en el Python
    # del sistema.
    _add_system_site_packages()
    try:
        import onnxruntime as ort
        _ORT_AVAILABLE = True
    except ImportError as e:
        ort = None  # type: ignore
        _ORT_AVAILABLE = False
        logger.warning(f"⚠ onnxruntime no disponible ({e}); anti-spoofing deshabilitado")


# ── Anti-Spoofing (Silent-Face-Anti-Spoofing / MiniFASNet) ──────────────────

class AntiSpoofDetector:
    """
    Clasificador de "vida" (rostro real vs. foto impresa / pantalla) usando
    MiniFASNet (Silent-Face-Anti-Spoofing, minivision-ai, Apache-2.0), vía
    ONNX Runtime — los .onnx se generan una sola vez con
    tools/antispoof/convert_to_onnx.py a partir de los pesos .pth originales.

    Corre dos modelos con distinto "zoom" alrededor del bbox de la cara
    (scale 2.7 y 4.0), suma sus softmax de 3 clases y decide "real" solo si
    la clase 1 (real) gana Y su confianza supera ANTI_SPOOF_CONFIG["score_threshold"]
    — el repo original solo hace argmax sin piso de confianza, insuficiente
    para control de acceso.
    """

    def __init__(self):
        self._sessions: List[Tuple["ort.InferenceSession", float, int]] = []
        self._loaded = False
        self._load_models()

    def _load_models(self) -> None:
        if not _ORT_AVAILABLE:
            return
        for spec in ANTI_SPOOF_CONFIG["models"]:
            path = Path(spec["path"])
            if not path.exists():
                logger.error(f"✗ Modelo anti-spoof no encontrado: {path}")
                continue
            try:
                sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
                self._sessions.append((sess, spec["scale"], spec["size"]))
            except Exception as e:
                logger.error(f"✗ Error cargando {path.name}: {e}")

        expected = len(ANTI_SPOOF_CONFIG["models"])
        self._loaded = len(self._sessions) == expected
        if self._loaded:
            logger.info(f"✓ AntiSpoofDetector: {len(self._sessions)} modelos cargados")
        elif self._sessions:
            logger.error(
                f"✗ AntiSpoofDetector: solo {len(self._sessions)}/{expected} modelos "
                "cargaron; se considera NO listo (fail-closed)"
            )

    @property
    def is_ready(self) -> bool:
        return self._loaded

    @staticmethod
    def _crop_box(src_w: int, src_h: int, bbox: tuple, scale: float) -> tuple:
        """Idéntico a CropImage._get_new_box del repo original: expande el
        bbox por `scale` centrado, con clamp a los bordes de la imagen."""
        x, y, box_w, box_h = bbox
        scale = min((src_h - 1) / box_h, min((src_w - 1) / box_w, scale))
        new_w, new_h = box_w * scale, box_h * scale
        cx, cy = x + box_w / 2, y + box_h / 2
        x1, y1 = cx - new_w / 2, cy - new_h / 2
        x2, y2 = cx + new_w / 2, cy + new_h / 2
        if x1 < 0:
            x2 -= x1
            x1 = 0
        if y1 < 0:
            y2 -= y1
            y1 = 0
        if x2 > src_w - 1:
            x1 -= (x2 - src_w + 1)
            x2 = src_w - 1
        if y2 > src_h - 1:
            y1 -= (y2 - src_h + 1)
            y2 = src_h - 1
        return int(x1), int(y1), int(x2), int(y2)

    def _prep(self, frame_bgr: np.ndarray, face_box: tuple, scale: float, size: int) -> np.ndarray:
        h, w = frame_bgr.shape[:2]
        x1, y1, x2, y2 = self._crop_box(w, h, face_box, scale)
        crop = frame_bgr[y1:y2 + 1, x1:x2 + 1]
        crop = cv2.resize(crop, (size, size))
        # NOTA: el modelo original se entrenó con imágenes BGR (cv2.imread
        # directo, sin conversión a RGB) — NO convertir color aquí.
        arr = crop.astype(np.float32) / 255.0
        return np.transpose(arr, (2, 0, 1))[None, ...]  # HWC -> NCHW

    def predict(self, frame_bgr: np.ndarray, face_box: tuple) -> Tuple[bool, float]:
        """Retorna (es_real, score). Fail-closed: sin modelos listos -> (False, 0.0)."""
        if not self._loaded:
            return False, 0.0

        total = np.zeros(3, dtype=np.float32)
        for sess, scale, size in self._sessions:
            inp = self._prep(frame_bgr, face_box, scale, size)
            logits = sess.run(None, {sess.get_inputs()[0].name: inp})[0][0]
            exp = np.exp(logits - np.max(logits))
            total += exp / exp.sum()

        label = int(np.argmax(total))
        score = float(total[label] / len(self._sessions))
        is_real = (label == ANTI_SPOOF_CONFIG["real_label"]) and (score >= ANTI_SPOOF_CONFIG["score_threshold"])
        return is_real, score


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

                # Determinar Transform según rotación configurada
                try:
                    from libcamera import Transform
                    rotation = CAMERA_CONFIG.get("rotation", 0)
                    if rotation == 90:
                        cam_transform = Transform(vflip=1, transpose=1)   # rot90 horario
                    elif rotation == 270:
                        cam_transform = Transform(hflip=1, transpose=1)   # rot270 antihorario
                    elif rotation == 180:
                        cam_transform = Transform(hflip=1, vflip=1)
                    else:
                        cam_transform = Transform()
                    logger.debug(f"✓ Transform aplicado: rotation={rotation}°")
                except ImportError:
                    cam_transform = None
                    logger.warning("libcamera.Transform no disponible, sin rotación")

                # Configuración
                logger.debug("Configurando cámara...")
                config_kwargs = {
                    "main": {
                        "format": "RGB888",
                        "size": (
                            CAMERA_CONFIG.get("width", 480),
                            CAMERA_CONFIG.get("height", 640),
                        ),
                    }
                }
                if cam_transform is not None:
                    config_kwargs["transform"] = cam_transform

                config = self.cam.create_preview_configuration(**config_kwargs)
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

                    # close() libera el file descriptor del dispositivo; sin esto
                    # picamera2 mantiene la cámara "abierta" y el siguiente
                    # Picamera2() falla al intentar abrirla de nuevo.
                    try:
                        self.cam.close()
                        logger.debug("✓ Cámara cerrada (fd liberado)")
                    except Exception as e:
                        logger.debug(f"Error cerrando cámara: {e}")

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

        # Pausa breve para que el kernel procese el cierre antes del próximo init
        time.sleep(0.2)

        # Reset global singleton después de liberar
        global _camera_manager
        _camera_manager = None
        logger.info("✓ Singleton global resetado")


class DevCameraManager(CameraManager):
    """
    CameraManager para desarrollo en laptop (sin Raspberry Pi / picamera2):
    usa cv2.VideoCapture con la webcam integrada. Comparte detección de
    rostros, embeddings y anti-spoofing con la clase base — solo cambia
    de dónde vienen los frames. Se activa con CAMERA_CONFIG["backend"] = "opencv".
    """

    def initialize(self) -> bool:
        with self._lock:
            if self.initialized:
                return True
            index = CAMERA_CONFIG.get("camera_index", 0)
            self.cam = cv2.VideoCapture(index)
            if not self.cam.isOpened():
                logger.error(f"✗ No se pudo abrir la webcam (índice {index})")
                self.initialized = False
                return False
            self.initialized = True
            logger.info(f"✓ DevCameraManager (webcam índice {index}) inicializada")
            return True

    def get_frame(self) -> Optional[np.ndarray]:
        if not self.initialized or self.cam is None:
            return None
        ok, frame = self.cam.read()
        if not ok:
            logger.warning("Error capturando frame de la webcam")
            return None
        return frame

    def release(self) -> None:
        with self._lock:
            if self.cam is not None:
                self.cam.release()
            self.initialized = False
            self.cam = None
        global _camera_manager
        _camera_manager = None


# ── Singleton Global ──────────────────────────────────────────────────────

_camera_manager: Optional[CameraManager] = None
_camera_lock = threading.Lock()


def get_camera_manager() -> CameraManager:
    """Obtiene la instancia global del gestor de cámara.

    Usa DevCameraManager (webcam vía cv2.VideoCapture) si
    CAMERA_CONFIG["backend"] == "opencv" — útil para desarrollar/probar
    en laptop antes de tener el Raspberry Pi. En cualquier otro caso usa
    CameraManager (picamera2), el backend real del locker.
    """
    global _camera_manager
    if _camera_manager is None:
        with _camera_lock:
            if _camera_manager is None:
                if CAMERA_CONFIG.get("backend") == "opencv":
                    _camera_manager = DevCameraManager()
                    logger.info("Creada nueva instancia de DevCameraManager (webcam)")
                else:
                    _camera_manager = CameraManager()
                    logger.info("Creada nueva instancia de CameraManager (picamera2)")
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
        self.anti_spoof = AntiSpoofDetector()

    def initialize(self) -> bool:
        """Inicializa el manager."""
        if self.manager.initialize():
            self.initialized = True
            logger.info("✓ FaceRecognitionManager inicializado")
            if self.embedding_extractor.uses_dlib:
                logger.info("  Embeddings: dlib resnet v1 (OK)")
            elif self.embedding_extractor.is_ready:
                # is_ready también es True en fallback, así que antes esto se
                # reportaba como "OK" y ocultaba que ningún rostro guardado
                # podría coincidir.
                logger.error("  Embeddings: MODO FALLBACK (grayscale 16x8) — "
                             "los rostros registrados usan dlib y NO podrán reconocerse. "
                             "Causa habitual: la app se lanzó desde un venv sin dlib.")
            else:
                logger.error("  Embeddings: NO DISPONIBLE")
            if not ANTI_SPOOF_CONFIG.get("enabled"):
                logger.warning("  Anti-spoofing: DESHABILITADO por configuración "
                               "(modelos .onnx mal convertidos — ver nota en config.py)")
            else:
                logger.info(f"  Anti-spoofing: {'OK' if self.anti_spoof.is_ready else 'NO DISPONIBLE'}")
            return True
        return False

    def check_liveness(self, frame: np.ndarray, face_box: tuple) -> Tuple[bool, float]:
        """
        Verifica que el rostro sea real (no foto/pantalla) con MiniFASNet.

        Fail-closed por configuración: si ANTI_SPOOF_CONFIG["required"] es True
        y los modelos no cargaron, niega el acceso en vez de degradar en
        silencio (a diferencia del fallback de embeddings, que sí degrada
        silenciosamente — comportamiento que NO se quiere repetir aquí).
        """
        if not ANTI_SPOOF_CONFIG.get("enabled"):
            return True, 1.0
        if not self.anti_spoof.is_ready:
            if ANTI_SPOOF_CONFIG.get("required"):
                logger.critical("Anti-spoof requerido pero no cargado — bloqueando acceso")
                return False, 0.0
            logger.warning("Anti-spoof no cargado y no es requerido — omitiendo verificación")
            return True, 1.0
        return self.anti_spoof.predict(frame, face_box)

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
