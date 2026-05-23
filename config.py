"""
Configuración centralizada del sistema Smart Locker.
"""

import os
from pathlib import Path

# ── Rutas ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
ASSETS_DIR   = PROJECT_ROOT / "assets"
MODELS_DIR   = ASSETS_DIR / "models"
FONTS_DIR    = ASSETS_DIR / "fonts"

# ── Base de datos ──────────────────────────────────────────────────────────
DATABASE_URL = "sqlite:///locker_system.db"

# ── Cámara / Visión ───────────────────────────────────────────────────────
# En Raspberry Pi 5, usa libcamera para acceso a cámaras
CAMERA_CONFIG = {
    "backend": "picamera2",  # libcamera | opencv | picamera2
    "camera_index": 0,
    "width": 1296,
    "height": 972,
    "fps": 30,
    "exposure": 0,  # -8 a 8
    "brightness": 0,
}

# ── OpenCV DNN / Face Detection ────────────────────────────────────────────
FACE_DETECTION_CONFIG = {
    "model_type": "opencv_dnn",  # opencv_dnn | mediapipe | dlib
    "confidence_threshold": 0.25,  # OPTIMIZADO: de 0.3 a 0.25 para más sensibilidad
    "nms_threshold": 0.4,
    # Modelos DNN
    "prototxt": str(MODELS_DIR / "deploy.prototxt"),
    "caffemodel": str(MODELS_DIR / "res10_300x300_ssd_iter_140000.caffemodel"),
}

# ── Face Recognition / Embeddings ──────────────────────────────────────────
FACE_RECOGNITION_CONFIG = {
    "model_type": "dlib",
    "embedding_size": 128,
    "distance_threshold": 0.50,  # dlib resnet: 0.5 reduce falsos positivos (0.65 era demasiado permisivo)
    # dlib models
    "shape_predictor": str(MODELS_DIR / "shape_predictor_68_face_landmarks.dat"),
    "face_rec_model": str(MODELS_DIR / "dlib_face_recognition_resnet_model_v1.dat"),
}

# ── GPIO / Hardware ────────────────────────────────────────────────────────
GPIO_CONFIG = {
    "mode": "BCM",
    "relay_active_low": True,
    "locker_open_seconds": 2.5,
    "pin_locker_m1": 17,
    "pin_locker_m2": 27,
    "pin_locker_m3": 22,
    "pin_locker_m4": 23,
    "debounce_ms": 50,
}

# ── Door limit switches (KW11-3Z) ──────────────────────────────────────────
DOOR_SWITCH_CONFIG = {
    "pins": {
        1: 5,   # Locker 1
        2: 6,   # Locker 2
        3: 12,  # Locker 3
        4: 13,  # Locker 4
    },
    # Activar logica solo para lockers confirmados (por ahora solo el 3).
    "active_lockers": [3],
    "close_cooldown_seconds": 10.0,
    "close_timeout_seconds": 10.0,
    "poll_interval_ms": 200,
}

# ── UI ─────────────────────────────────────────────────────────────────────
UI_CONFIG = {
    "width": 480,
    "height": 800,
    "theme": "Greengage",
    "fullscreen": True,   # Pantalla completa en RPi
    "kiosk_mode": True,   # Sin barra de título (modo kiosco)
}

# ── Timeouts ───────────────────────────────────────────────────────────────
TIMEOUTS = {
    "camera_init": 10.0,  # segundos
    "face_detection": 5.0,
    "face_recognition": 10.0,
    "display_user_info": 8,  # segundos antes de volver a standby
    "max_attempts": 3,
}

# ── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = PROJECT_ROOT / "logs" / "locker_system.log"
