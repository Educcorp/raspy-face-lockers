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
    "distance_threshold": 0.65,  # OPTIMIZADO: de 0.6 a 0.65 - más tolerante (iPhone-style)
    # dlib models
    "shape_predictor": str(MODELS_DIR / "shape_predictor_68_face_landmarks.dat"),
    "face_rec_model": str(MODELS_DIR / "dlib_face_recognition_resnet_model_v1.dat"),
}

# ── GPIO / Hardware ────────────────────────────────────────────────────────
GPIO_CONFIG = {
    "mode": "BCM",
    "relay_active_low": True,
    "locker_open_seconds": 3.0,
    "pin_locker_m1": 17,
    "pin_locker_m2": 27,
    "pin_locker_m3": 22,
    "pin_locker_m4": 23,
    "pin_light_sensor": 17,  # BCM
    "pin_motor_relay": 17,
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
