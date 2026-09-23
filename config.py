"""
Configuración centralizada del sistema Smart Locker.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Rutas ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
ASSETS_DIR   = PROJECT_ROOT / "assets"
MODELS_DIR   = ASSETS_DIR / "models"
FONTS_DIR    = ASSETS_DIR / "fonts"

load_dotenv(PROJECT_ROOT / ".env")

# ── Base de datos ──────────────────────────────────────────────────────────
# Misma base de datos Postgres (Railway) que usa webapp/ — ver .env.example.
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ── Cámara / Visión ───────────────────────────────────────────────────────
# En Raspberry Pi 5, usa libcamera para acceso a cámaras
CAMERA_CONFIG = {
    # "opencv" usa DevCameraManager (webcam vía cv2.VideoCapture) para
    # desarrollar/probar en laptop sin Raspberry Pi. Override rápido sin
    # tocar este archivo: CAMERA_BACKEND=opencv python ...
    "backend": os.getenv("CAMERA_BACKEND", "picamera2"),  # opencv | picamera2
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

# ── Anti-spoofing (Silent-Face-Anti-Spoofing, minivision-ai, Apache-2.0) ────
ANTI_SPOOF_CONFIG = {
    # DESHABILITADO TEMPORALMENTE — los .onnx de assets/models están mal
    # convertidos: son funciones prácticamente constantes. Verificado con 12
    # entradas radicalmente distintas (gris plano, negro, ruido, tablero de
    # ajedrez, 8 parches de fotos reales): los logits se mueven <0.6 y la
    # clase 2 ("falso") gana 12/12 veces, dando siempre score≈0.95. Con
    # required=True eso negaba TODO acceso sin llegar nunca a comparar
    # rostros. Para reactivar: re-convertir los .pth originales con
    # tools/antispoof/convert_to_onnx.py y comprobar que la salida SÍ
    # reacciona a la entrada antes de volver a poner enabled=True.
    "enabled": False,
    "required": True,  # si True y los modelos no cargan, se BLOQUEA el acceso (fail-closed)
    "models": [
        {"path": str(MODELS_DIR / "2.7_80x80_MiniFASNetV2.onnx"), "scale": 2.7, "size": 80},
        {"path": str(MODELS_DIR / "4_0_0_80x80_MiniFASNetV1SE.onnx"), "scale": 4.0, "size": 80},
    ],
    "real_label": 1,
    "score_threshold": 0.75,
}

# ── GPIO / Hardware ────────────────────────────────────────────────────────
GPIO_CONFIG = {
    "mode": "BCM",
    "relay_active_low": True,
    "locker_open_seconds": 10.0,
    "pin_locker_m1": 17,
    "pin_locker_m2": 27,
    "pin_locker_m3": 22,
    "pin_locker_m4": 23,
    "debounce_ms": 50,
}

# ── Relay de herramientas (canal 5+, ej. interlock del taladro) ─────────────
# Este relay NO switchea directo el AC del taladro: activa la bobina de un
# contactor/toma controlada (12V, misma fuente que ya alimenta los solenoides
# de los lockers), y es ese contactor el que sí switchea la corriente de pared
# hacia la herramienta. Mismo patrón activo-bajo que los relays de locker.
TOOL_GPIO_CONFIG = {
    "mode": "BCM",
    "relay_active_low": True,
    # Segundos que el contactor permanece habilitado por activación.
    # A diferencia del locker (pulso corto para liberar un pestillo), aquí
    # es tiempo de USO real de la herramienta — ajusta según el caso de uso
    # real (o cámbialo por lógica de "mientras el usuario esté presente"
    # cuando se integre con el módulo de permisos).
    "activation_seconds": 300,
    "pins": {
        "taladro": 24,  # BCM24 / pin físico 18 — libre, no usado por lockers ni door switches
    },
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
    "active_lockers": [1, 2, 3, 4],
    "close_cooldown_seconds": 5.0,
    "close_timeout_seconds": 5.0,
    "warning_duration_seconds": 6.0,
    "warning_repeat_seconds": 45.0,
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
