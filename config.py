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
    "width": 640,
    "height": 480,
    "fps": 30,
    "exposure": 0,  # -8 a 8
    "brightness": 0,
}

# ── OpenCV DNN / Face Detection ────────────────────────────────────────────
FACE_DETECTION_CONFIG = {
    "model_type": "opencv_dnn",  # opencv_dnn | mediapipe | dlib
    "confidence_threshold": 0.5,
    "nms_threshold": 0.4,
    # Modelos DNN
    "prototxt": str(MODELS_DIR / "deploy.prototxt"),
    "caffemodel": str(MODELS_DIR / "res10_300x300_ssd_iter_140000.caffemodel"),
}

# ── Face Recognition / Embeddings ──────────────────────────────────────────
FACE_RECOGNITION_CONFIG = {
    "model_type": "facenet",  # facenet | arcface | dlib
    "embedding_size": 128,
    "distance_threshold": 0.6,  # para considerarse el mismo rostro
}

# ── GPIO / Hardware ────────────────────────────────────────────────────────
GPIO_CONFIG = {
    "pin_light_sensor": 17,  # BCM
    "pin_motor_relay": 27,
    "pin_button_test": 22,
    "debounce_ms": 50,
}

# ── UI ─────────────────────────────────────────────────────────────────────
UI_CONFIG = {
    "width": 480,
    "height": 800,
    "theme": "Greengage",
    "fullscreen": False,  # True en Raspberry Pi física
    "kiosk_mode": False,  # True en RPi (sin barra de título)
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
