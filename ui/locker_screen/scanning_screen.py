"""
ScanningScreen – pantalla de escaneo facial (480×800 px).

La cámara ocupa casi toda la ventana. Se dibuja una silueta guía
que cambia de rojo a verde según la detección del rostro.
Al reconocer al usuario, se muestra un overlay verde con los datos
(nombre, casillero, fecha) y un countdown de regreso automático.
Un botón de flecha ← en la parte inferior permite volver al standby.
"""

import customtkinter as ctk
import threading
import os
import time
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import tkinter
import logging
from typing import Optional
from datetime import datetime
from collections import deque
import random

from config import FACE_RECOGNITION_CONFIG, CAMERA_CONFIG
from config import GPIO_CONFIG
from config import DOOR_SWITCH_CONFIG
from ui.i18n import t
from core.gpio_controller import get_locker_gpio_controller
from core.face_recognition import filter_close_faces as _filter_close_faces
from services import user_service, locker_service, access_log_service

logger = logging.getLogger(__name__)


def _largest_face(faces: list) -> dict | None:
    """Selecciona el rostro más cercano (caja más grande) de la lista detectada."""
    if not faces:
        return None
    return max(faces, key=lambda f: (
        (f.get("box") or (0, 0, 0, 0))[2] * (f.get("box") or (0, 0, 0, 0))[3]
    ))



class ScanningScreen(ctk.CTkFrame):
    """
    Pantalla activa durante el reconocimiento facial.
    La cámara ocupa toda la ventana con silueta guía superpuesta.
    """

    BG_COLOR   = "#1A1A2E"   # fondo oscuro para contraste con cámara
    PRIMARY    = "#5B8C5A"
    SUCCESS    = "#4CAF50"
    WARNING    = "#D4A34A"
    DANGER     = "#C75C5C"
    TEXT_COLOR = "#FFFFFF"
    MUTED      = "#B0B0B0"

    # Colores de la silueta
    SILHOUETTE_NO_FACE  = (200, 80, 80, 160)    # rojo semi-transparente
    SILHOUETTE_FACE_OK  = (90, 180, 90, 160)     # verde semi-transparente

    MAX_ATTEMPTS    = 3
    PIN_MAX_FAILS   = 3
    LOCK_SECONDS    = 60
    DISPLAY_SECONDS = 5
    DOOR_ALERT_DELAY_S    = 10.0   # segundos de espera antes de mostrar alerta
    DOOR_ALERT_DURATION_S =  5.0   # segundos que dura la pantalla de alerta
    RECOGNITION_INTERVAL_FRAMES = 4   # intentos de reconocimiento cada 4 frames
    STABLE_FACE_FRAMES = 6            # rostro estable ~0.4s antes de intentar reconocimiento
    RECOGNITION_COOLDOWN_SECONDS = 1.5  # mínimo 1.5s entre intentos de reconocimiento
    LIVENESS_HISTORY_FRAMES = 12      # 12 frames de historial de movimiento (~0.8s)
    LIVENESS_MIN_MOTION = 1.5         # requiere movimiento natural real (no ruido)
    LIVENESS_MIN_BOX_SHIFT = 0.015    # desplazamiento mínimo visible del rostro
    MIN_SCAN_SECONDS = 2.0            # tiempo mínimo de escaneo antes de intentar identificar
    AUTO_RETURN_SECONDS = 25.0        # segundos sin cara cercana → volver a standby
    LIVENESS_CHALLENGE_TIMEOUT = 9.0  # No usado en modo pasivo
    CHALLENGE_SHIFT_THRESHOLD = 0.16  # No usado en modo pasivo
    CHALLENGE_SCALE_IN_THRESHOLD = 0.18  # No usado en modo pasivo
    CHALLENGE_SCALE_OUT_THRESHOLD = -0.15  # No usado en modo pasivo

    # Dimensiones de la ventana
    WIN_W = 480
    WIN_H = 800

    def __init__(self, parent: ctk.CTk, controller) -> None:
        super().__init__(parent, fg_color=self.BG_COLOR, corner_radius=0)
        self.controller = controller
        self._attempts  = 0
        self._face_detected = False
        self._success_shown = False
        self._return_job = None
        self._frame_counter = 0
        self._stable_face_frames = 0
        self._last_recognition_ts = 0.0
        self._last_seen_face_box = None
        self._face_first_seen_ts: float = 0.0   # cuando el rostro apareció por primera vez
        self._scan_progress_pct: int = 0         # 0-100, para barra de progreso en UI
        self._last_close_face_ts: float = 0.0   # última vez que se detectó cara cercana
        self._liveness_passed = False
        self._passive_liveness_ok = False
        self._active_liveness_ok = False
        self._liveness_motion_score = 0.0
        self._liveness_shift_score = 0.0
        self._liveness_face_history = deque(maxlen=self.LIVENESS_HISTORY_FRAMES)
        self._liveness_box_history = deque(maxlen=self.LIVENESS_HISTORY_FRAMES)
        self._challenge_steps: list[str] = []
        self._challenge_index = 0
        self._challenge_started_at = 0.0
        self._challenge_ref_box = None
        self._blink_closed_seen = False
        self._auto_return_started_ts: float | None = None
        self._door_wait_job = None
        self._door_wait_active = False
        self._door_wait_started_at = 0.0
        self._door_open_seen = False
        self._door_wait_phase: str = "waiting"   # "waiting" | "alerting"
        self._door_wait_locker_id: int | None = None
        self._door_wait_assignment_id: int | None = None

        # Variables de captura de cámara
        self._camera_thread: Optional[threading.Thread] = None
        self._detect_thread: Optional[threading.Thread] = None
        self._camera_running = False
        self._camera_frame: Optional[np.ndarray] = None
        self._latest_frame_for_detect: Optional[np.ndarray] = None  # canal entre hilos
        self._detected_faces = []
        self._photo_image: Optional[tkinter.PhotoImage] = None

        # Datos del usuario reconocido
        self._user_data: Optional[dict] = None

        # Estado del overlay de PIN
        self._pin_state: str = "matricula"  # "matricula" | "pin"
        self._pin_matricula: str = ""
        self._pin_code: str = ""
        self._pin_fail_count: int = 0
        self._pin_matricula_fail_count: int = 0   # intentos de matrícula incorrecta
        self._last_failed_closest: Optional[dict] = None  # candidato más cercano en fallo facial
        self._display_pending: bool = False               # evita acumular frames en la cola
        self._found_user: Optional[dict] = None

        # Inicializar módulo de reconocimiento facial
        try:
            from core.face_recognition import get_face_recognition_manager
            self.face_manager = get_face_recognition_manager()
        except Exception as e:
            logger.error(f"Error importando FaceRecognitionManager: {e}")
            self.face_manager = None

        self.gpio_controller = get_locker_gpio_controller()

        self._build_ui()
        self._build_pin_overlay()
        self._build_lock_overlay()
        self._reset_liveness_state()

    # ── Construcción de UI ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Canvas que ocupa TODA la ventana para dibujar cámara + overlays
        self.canvas = tkinter.Canvas(
            self,
            width=self.WIN_W,
            height=self.WIN_H,
            bg="#1A1A2E",
            highlightthickness=0,
        )
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)

        # ── Status label (fondo oscuro para legibilidad sobre cámara) ─────────
        self.lbl_status = ctk.CTkLabel(
            self,
            text=t("scan.position_face"),
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.TEXT_COLOR,
            fg_color="#1A1A2E",
            corner_radius=10,
            height=44,
            width=390,
        )
        self.lbl_status.place(relx=0.5, y=104, anchor="center")

        # ── Contador de intentos ──────────────────────────────────────────────
        self.lbl_attempts = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=self.WARNING,
            fg_color="#1A1A2E",
            corner_radius=8,
            height=30,
            width=260,
        )
        self.lbl_attempts.place(relx=0.5, y=56, anchor="center")

        # ── Barra de progreso de escaneo ──────────────────────────────────────
        self.scan_progress_bar = ctk.CTkProgressBar(
            self,
            width=340,
            height=8,
            fg_color="#2A2A3E",
            progress_color=self.PRIMARY,
            corner_radius=4,
        )
        self.scan_progress_bar.set(0)
        self.scan_progress_bar.place(relx=0.5, rely=0.885, anchor="center")

        # ── Botón de acceso a panel admin (icono de perfil, top-right) ────────
        _admin_icon_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "assets", "icons", "icon_persona_blanco.png"
        )
        self._admin_icon_img = None
        try:
            if os.path.exists(_admin_icon_path):
                _img = Image.open(_admin_icon_path)
                self._admin_icon_img = ctk.CTkImage(
                    light_image=_img, dark_image=_img, size=(22, 22)
                )
        except Exception:
            pass

        self.btn_admin = ctk.CTkButton(
            self,
            text="" if self._admin_icon_img else "⚙",
            image=self._admin_icon_img,
            font=ctk.CTkFont(size=14),
            fg_color="#2A2A4E",
            bg_color="transparent",
            hover_color="#3A3A6E",
            text_color="#FFFFFF",
            border_width=1,
            border_color="#5B8C5A",
            width=38, height=38,
            corner_radius=10,
            command=self._go_admin_login,
        )
        self.btn_admin.place(x=452, y=44, anchor="center")

        # ── Overlay de éxito — fondo verde pantalla completa ─────────────────
        self.overlay_bg = ctk.CTkFrame(
            self,
            fg_color="#5B8C5A",
            corner_radius=0,
            width=self.WIN_W, height=self.WIN_H,
            border_width=0,
        )

        # Panel interior centrado (todos los labels viven aquí).
        # on_face_match() reordena el pack según si hay locker o no.
        self._success_inner = ctk.CTkFrame(self.overlay_bg, fg_color="transparent")
        self._success_inner.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.86)

        # Ícono
        _icon_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "assets", "icons", "icon_persona_blanco.png"
        )
        self._success_icon = None
        try:
            if os.path.exists(_icon_path):
                _icon_img = Image.open(_icon_path)
                self._success_icon = ctk.CTkImage(
                    light_image=_icon_img,
                    dark_image=_icon_img,
                    size=(80, 80),
                )
        except Exception as e:
            logger.warning(f"No se pudo cargar icono de éxito: {e}")

        self.lbl_success_icon = ctk.CTkLabel(
            self._success_inner,
            text="" if self._success_icon else "👤",
            image=self._success_icon,
            fg_color="transparent",
            width=84, height=84,
        )

        # Nombre del usuario
        self.lbl_success_name = ctk.CTkLabel(
            self._success_inner,
            text="",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
            wraplength=390,
            justify="center",
            anchor="center",
        )

        # Matrícula
        self.lbl_success_matricula = ctk.CTkLabel(
            self._success_inner,
            text="",
            font=ctk.CTkFont(size=15),
            text_color="#D4EDDA",
            fg_color="transparent",
            anchor="center",
        )

        # Estado (se reconfigura en on_face_match según el caso)
        self.lbl_success_main = ctk.CTkLabel(
            self._success_inner,
            text="",
            font=ctk.CTkFont(size=15),      # sin negrita, igual que matrícula
            text_color="#FFFFFF",
            fg_color="transparent",
            anchor="center",
        )

        # Etiqueta "Locker" — grande y en negrita en pantalla verde
        self.lbl_success_locker_label = ctk.CTkLabel(
            self._success_inner,
            text="Locker",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
            anchor="center",
        )

        # Número de locker — muy grande y visible
        self.lbl_success_locker_big = ctk.CTkLabel(
            self._success_inner,
            text="",
            font=ctk.CTkFont(size=88, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
            anchor="center",
        )

        # Sub-mensaje sin locker — grande y en negrita para que destaque
        self.lbl_success_sub = ctk.CTkLabel(
            self._success_inner,
            text="",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
            wraplength=390,
            justify="center",
            anchor="center",
        )

        # Countdown
        self.lbl_countdown = ctk.CTkLabel(
            self._success_inner,
            text="",
            font=ctk.CTkFont(size=13),
            text_color="#D4EDDA",
            fg_color="transparent",
            anchor="center",
            justify="center",
        )

        # Mantener referencia legacy por compatibilidad interna
        self.success_frame = self._success_inner

        # ── Overlay de acceso denegado (fondo completamente rojo) ─────────────
        self.denied_overlay = ctk.CTkFrame(
            self,
            fg_color="#C0392B",
            corner_radius=0,
            width=self.WIN_W,
            height=self.WIN_H,
        )
        _di = ctk.CTkFrame(self.denied_overlay, fg_color="transparent")
        _di.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.85)

        ctk.CTkLabel(
            _di,
            text="✗",
            font=ctk.CTkFont(size=90, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
        ).pack(pady=(0, 16))

        ctk.CTkLabel(
            _di,
            text=t("scan.denied_title"),
            font=ctk.CTkFont(size=36, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
            wraplength=390,
            justify="center",
        ).pack()

        # ── Overlay de alerta de puerta abierta (pantalla completa, 5 s) ────
        self.door_warning_overlay = ctk.CTkFrame(
            self,
            fg_color="#F3C94A",
            corner_radius=0,
            width=self.WIN_W,
            height=self.WIN_H,
        )
        _dw = ctk.CTkFrame(self.door_warning_overlay, fg_color="transparent")
        _dw.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.85)

        ctk.CTkLabel(
            _dw,
            text="⚠",
            font=ctk.CTkFont(size=64, weight="bold"),
            text_color="#4A3B00",
            fg_color="transparent",
        ).pack(pady=(0, 4))

        self.lbl_door_alert_title = ctk.CTkLabel(
            _dw,
            text=t("door.alert_title"),
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#4A3B00",
            fg_color="transparent",
            wraplength=390,
            justify="center",
        )
        self.lbl_door_alert_title.pack()

        self.lbl_door_warning_locker = ctk.CTkLabel(
            _dw,
            text="",
            font=ctk.CTkFont(size=130, weight="bold"),
            text_color="#4A3B00",
            fg_color="transparent",
        )
        self.lbl_door_warning_locker.pack(pady=(0, 0))

        self.lbl_door_alert_subtitle = ctk.CTkLabel(
            _dw,
            text=t("door.alert_subtitle"),
            font=ctk.CTkFont(size=15),
            text_color="#4A3B00",
            fg_color="transparent",
        )
        self.lbl_door_alert_subtitle.pack(pady=(4, 0))

    # ── Captura de video en background ────────────────────────────────────────

    def _camera_loop(self) -> None:
        """Thread worker que captura frames y detecta rostros."""
        if not self.face_manager:
            logger.error("FaceManager no inicializado")
            self.after(0, self._show_camera_error, "Gestor de reconocimiento facial no disponible")
            return

        if not self.face_manager.initialized:
            # Pausa para que el hardware de picamera2 termine de liberar recursos
            # de cualquier sesión anterior (registro admin, etc.) antes de reiniciar.
            time.sleep(0.6)
            if not self._camera_running:
                return
            logger.warning("Intentando inicializar cámara...")
            init_ok = False
            for attempt in range(1, 4):
                if self.face_manager.initialize():
                    init_ok = True
                    break
                logger.warning(f"Inicialización de cámara falló (intento {attempt}/3)")
                try:
                    self.face_manager.release()
                except Exception:
                    pass
                time.sleep(0.35 * attempt)

            if not init_ok:
                logger.error("✗ No se pudo inicializar cámara")
                error_msg = "No se pudo acceder a la cámara. Verifica:\n1. Cámara conectada\n2. Permisos de acceso\n3. Configuración en raspi-config"
                self.after(0, self._show_camera_error, error_msg)
                return

        logger.info("✓ Camera loop iniciado correctamente")

        # Hilo de detección independiente: HOG+Haar corre en background
        # para que la captura y el display nunca se bloqueen.
        self._detect_thread = threading.Thread(
            target=self._detection_loop, daemon=True
        )
        self._detect_thread.start()

        try:
            while self._camera_running:
                # ── Captura (bloquea ~33 ms al ritmo de la cámara) ───────────────
                frame = self.face_manager.get_frame()
                if frame is None:
                    time.sleep(0.005)
                    continue

                self._camera_frame = frame
                self._frame_counter += 1
                # Publicar para el hilo de detección (el hilo consume el más reciente)
                self._latest_frame_for_detect = frame

                # ── Display: siempre al ritmo completo de la cámara ──────────────
                if not self._display_pending:
                    self._display_pending = True
                    try:
                        self._update_camera_display(frame, self._detected_faces)
                    except Exception as e:
                        self._display_pending = False
                        logger.error("Display error: %s", e)

        except Exception as e:
            logger.error(f"Error en camera loop: {e}")
            self.after(0, self._show_camera_error, f"Error crítico: {str(e)}")
        finally:
            # NO liberar la cámara aquí: on_hide() lo hace después de que
            # el hilo termina, evitando la condición de carrera.
            logger.info("Camera loop finalizado.")

    def _detection_loop(self) -> None:
        """
        Hilo de detección independiente.
        Corre HOG+Haar y toda la lógica de liveness/reconocimiento en background,
        sin bloquear nunca el hilo de captura/display.
        """
        last_frame_id: int = -1
        detect_count: int  = 0

        while self._camera_running:
            frame = self._latest_frame_for_detect
            if frame is None or id(frame) == last_frame_id:
                time.sleep(0.005)
                continue

            last_frame_id = id(frame)
            detect_count += 1

            # ── Detección (HOG + Haar si es necesario) ───────────────────────
            try:
                all_faces = self.face_manager.manager.detect_faces(frame)
            except Exception as err:
                logger.debug("Detection error: %s", err)
                all_faces = []

            faces = _filter_close_faces(all_faces, frame)

            # Reject faces whose bounding box touches or overflows the frame edges
            if faces:
                fh, fw = frame.shape[:2]
                edge = int(min(fh, fw) * 0.05)  # 5% margin on each side
                complete = []
                for f in faces:
                    bx, by, bw, bh = f.get("box", (0, 0, 0, 0))
                    if bx >= edge and by >= edge and bx + bw <= fw - edge and by + bh <= fh - edge:
                        complete.append(f)
                faces = complete

            self._detected_faces = faces
            self._face_detected  = len(faces) > 0

            if self._success_shown:
                continue

            now = time.time()

            if faces:
                self._last_close_face_ts = now
                primary_face = _largest_face(faces)
                face_box = primary_face.get("box") if primary_face else None

                face_switched = False
                if face_box and self._last_seen_face_box:
                    prev = self._last_seen_face_box
                    prev_cx = prev[0] + prev[2] * 0.5
                    prev_cy = prev[1] + prev[3] * 0.5
                    curr_cx = face_box[0] + face_box[2] * 0.5
                    curr_cy = face_box[1] + face_box[3] * 0.5
                    dist = np.sqrt((curr_cx - prev_cx) ** 2 + (curr_cy - prev_cy) ** 2)
                    if dist / max(frame.shape[1], 1) > 0.15:
                        face_switched = True

                if face_switched:
                    self._stable_face_frames = 0
                    self._face_first_seen_ts = 0.0
                    self._scan_progress_pct  = 0
                    self._reset_liveness_state()

                if self._stable_face_frames == 0:
                    self._face_first_seen_ts = now
                self._stable_face_frames += 1
                self._last_seen_face_box = face_box
                if face_box:
                    self._update_liveness(frame, face_box)
            else:
                self._stable_face_frames = 0
                self._last_seen_face_box = None
                self._face_first_seen_ts = 0.0
                self._scan_progress_pct  = 0
                self._reset_liveness_state()

                if now - self._last_close_face_ts >= self.AUTO_RETURN_SECONDS:
                    logger.info("Sin cara %.0f s → standby", self.AUTO_RETURN_SECONDS)
                    self._camera_running = False
                    self._auto_return_started_ts = time.time()
                    self.after(0, self._finalize_auto_return)
                    return

            if self._face_first_seen_ts > 0:
                scan_elapsed = now - self._face_first_seen_ts
                self._scan_progress_pct = min(100, int(scan_elapsed / self.MIN_SCAN_SECONDS * 100))
            else:
                scan_elapsed = 0.0
                self._scan_progress_pct = 0

            enough_stability = self._stable_face_frames >= self.STABLE_FACE_FRAMES
            cooldown_ok      = (now - self._last_recognition_ts) >= self.RECOGNITION_COOLDOWN_SECONDS
            scan_time_ok     = scan_elapsed >= self.MIN_SCAN_SECONDS
            do_recognize     = detect_count % self.RECOGNITION_INTERVAL_FRAMES == 0

            if faces and do_recognize and enough_stability and cooldown_ok and self._liveness_passed and scan_time_ok:
                self._last_recognition_ts = now
                try:
                    user_data = self._recognize_current_face(frame, faces)
                    if user_data:
                        self.after(0, self.on_face_match, user_data)
                    else:
                        self.after(0, self.on_face_no_match)
                except Exception as err:
                    logger.error("Error en reconocimiento: %s", err)
                    self.after(0, self.on_face_no_match)

        logger.debug("Detection loop finalizado. Total detecciones: %d", detect_count)

    def _update_camera_display(self, frame: np.ndarray, faces: list) -> None:
        """Dibuja el frame en modo espejo con recorte 1:1 y guía de rostro."""
        try:
            backend = getattr(self.face_manager, "backend_type", CAMERA_CONFIG.get("backend", "picamera2"))
            if backend == "opencv":
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                frame_rgb = frame

            # Espejo horizontal (modo selfie)
            frame_rgb = cv2.flip(frame_rgb, 1)
            h, w = frame_rgb.shape[:2]

            # Recorte central 1:1 y escalado a cuadro cuadrado
            square_size = min(self.WIN_W, self.WIN_H)
            crop_side = min(h, w)
            crop_x0 = (w - crop_side) // 2
            crop_y0 = (h - crop_side) // 2
            frame_crop = frame_rgb[crop_y0:crop_y0 + crop_side, crop_x0:crop_x0 + crop_side]

            scale = square_size / max(crop_side, 1)
            frame_resized = cv2.resize(
                frame_crop,
                (square_size, square_size),
                interpolation=cv2.INTER_AREA,
            )

            # Centrar en lienzo negro
            canvas_arr = np.zeros((self.WIN_H, self.WIN_W, 3), dtype=np.uint8)
            x_off = (self.WIN_W - square_size) // 2
            y_off = (self.WIN_H - square_size) // 2
            canvas_arr[y_off:y_off + square_size, x_off:x_off + square_size] = frame_resized

            pil_image = Image.fromarray(canvas_arr, mode="RGB")
            draw = ImageDraw.Draw(pil_image)

            # Calcular cuadro guía usando el rostro más cercano (mayor área)
            if len(faces) > 0:
                face_box = (_largest_face(faces) or {}).get("box")
                if face_box:
                    fx, fy, fw, fh = face_box
                    # Espejo: invertir x en el espacio del frame original
                    fx_m = w - fx - fw
                    # Mapear al recorte 1:1 y luego al cuadrado mostrado
                    fx_c = fx_m - crop_x0
                    fy_c = fy - crop_y0

                    if (fx_c + fw) <= 0 or (fy_c + fh) <= 0 or fx_c >= crop_side or fy_c >= crop_side:
                        x1, y1, x2, y2 = self._default_guide_box()
                    else:
                        xs = int(fx_c * scale) + x_off
                        ys = int(fy_c * scale) + y_off
                        ws = int(fw * scale)
                        hs = int(fh * scale)
                        pad = int(max(ws, hs) * 0.3)
                        x1 = max(0, xs - pad)
                        y1 = max(0, ys - pad)
                        x2 = min(self.WIN_W, xs + ws + pad)
                        y2 = min(self.WIN_H, ys + hs + pad)
                else:
                    x1, y1, x2, y2 = self._default_guide_box()
            else:
                x1, y1, x2, y2 = self._default_guide_box()

            box_color = (90, 180, 90) if self._liveness_passed else (200, 80, 80)
            cl, lw = 40, 5
            draw.line([(x1,      y1), (x1 + cl, y1)], fill=box_color, width=lw)
            draw.line([(x1,      y1), (x1,      y1 + cl)], fill=box_color, width=lw)
            draw.line([(x2 - cl, y1), (x2,      y1)], fill=box_color, width=lw)
            draw.line([(x2,      y1), (x2,      y1 + cl)], fill=box_color, width=lw)
            draw.line([(x1,      y2 - cl), (x1, y2)], fill=box_color, width=lw)
            draw.line([(x1,      y2), (x1 + cl, y2)], fill=box_color, width=lw)
            draw.line([(x2,      y2 - cl), (x2, y2)], fill=box_color, width=lw)
            draw.line([(x2 - cl, y2), (x2,      y2)], fill=box_color, width=lw)

            try:
                self.after(0, self._set_camera_image, pil_image.copy())
            except Exception as e:
                logger.warning(f"Error enviando frame al display: {e}")

        except Exception as e:
            logger.error(f"Error actualizando display: {e}")

    def _default_guide_box(self) -> tuple[int, int, int, int]:
        """Cuadro guía centrado cuando no hay rostro detectado."""
        square_size = min(self.WIN_W, self.WIN_H)
        x_off = (self.WIN_W - square_size) // 2
        y_off = (self.WIN_H - square_size) // 2
        cx, cy = x_off + square_size // 2, y_off + square_size // 2 - 40
        return cx - 140, cy - 180, cx + 140, cy + 180

    def _show_camera_error(self, error_msg: str) -> None:
        """Muestra un mensaje de error cuando la cámara no está disponible."""
        logger.error(f"Camera Error: {error_msg}")
        
        # Mostrar error en el canvas
        self.canvas.delete("all")
        self.canvas.create_rectangle(
            0, 0, self.WIN_W, self.WIN_H,
            fill=self.BG_COLOR,
            outline=self.BG_COLOR
        )
        
        self.canvas.create_text(
            self.WIN_W // 2, 150,
            text=t("scan.camera_error_title"),
            font=("Arial", 24, "bold"),
            fill="#FF6B6B",
            justify="center"
        )
        self.canvas.create_text(
            self.WIN_W // 2, 300,
            text=error_msg,
            font=("Arial", 14),
            fill="#FFFFFF",
            justify="center",
            width=360
        )
        
        self.lbl_status.configure(
            text=t("scan.camera_unavailable"),
            text_color="#FF6B6B"
        )


    def _set_camera_image(self, pil_img: "Image.Image") -> None:
        """Recibe imagen PIL y la muestra en el canvas. Siempre corre en el main thread."""
        self._display_pending = False   # liberar para el siguiente frame
        try:
            from PIL import ImageTk
            photo = ImageTk.PhotoImage(pil_img)
            self._photo_image = photo  # mantener referencia para evitar GC
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=photo)
            self.canvas.image = photo
            self.btn_admin.lift()

            if not self._success_shown:
                if self._face_detected:
                    if self._liveness_passed:
                        pct = self._scan_progress_pct
                        self.scan_progress_bar.set(pct / 100)
                        if pct >= 100:
                            self.lbl_status.configure(
                                text=t("scan.identifying"),
                                text_color="#A5D6A7",
                            )
                        else:
                            self.lbl_status.configure(
                                text=t("scan.scanning_pct", pct=pct),
                                text_color="#FFD54F",
                            )
                    else:
                        self.scan_progress_bar.set(0)
                        self.lbl_status.configure(
                            text=t("scan.move_face"),
                            text_color="#FFD54F",
                        )
                else:
                    self.scan_progress_bar.set(0)
                    self.lbl_status.configure(
                        text=t("scan.position_frame"),
                        text_color="#FFFFFF",
                    )
        except Exception as e:
            logger.error(f"Error mostrando imagen: {e}")

    # ── API pública ───────────────────────────────────────────────────────────

    def on_show(self) -> None:
        """Inicia captura de vídeo cuando la pantalla se activa."""
        self._attempts = 0
        self._success_shown = False
        self._user_data = None
        self._frame_counter = 0
        self._stable_face_frames = 0
        self._last_recognition_ts = 0.0
        self._last_seen_face_box = None
        self._face_first_seen_ts = 0.0
        self._scan_progress_pct = 0
        self._last_close_face_ts = time.time()  # arrancar temporizador de inactividad
        self._auto_return_started_ts = None
        self._door_wait_active = False
        self._door_wait_started_at = 0.0
        self._door_open_seen = False
        self._door_wait_phase = "waiting"
        self._door_wait_locker_id = None
        self._door_wait_assignment_id = None
        if self._door_wait_job:
            self.after_cancel(self._door_wait_job)
            self._door_wait_job = None
        self._reset_liveness_state()
        self._pin_fail_count = 0
        self._pin_matricula_fail_count = 0
        self._last_failed_closest = None
        self._found_user = None
        self.lbl_status.configure(text=t("scan.starting_camera"), text_color="#FFFFFF")
        self.lbl_attempts.configure(text="")
        self.scan_progress_bar.set(0)
        self.overlay_bg.place_forget()
        self.denied_overlay.place_forget()
        self.door_warning_overlay.place_forget()
        self._hide_pin_overlay()
        self._hide_lock_overlay()
        self.btn_admin.place(x=452, y=44, anchor="center")
        self.btn_admin.lift()

        # Recrear face_manager para obtener la instancia fresca del singleton
        # global de CameraManager. Sin esto, al volver del panel admin el manager
        # apunta a un objeto viejo que puede causar que Picamera2 se cuelgue.
        try:
            from core.face_recognition import get_face_recognition_manager
            self.face_manager = get_face_recognition_manager()
        except Exception as e:
            logger.error("Error recreando FaceManager en on_show: %s", e)

        if self._camera_thread and self._camera_thread.is_alive():
            self._camera_thread.join(timeout=1.0)
        self._camera_thread = None

        if self._detect_thread and self._detect_thread.is_alive():
            self._detect_thread.join(timeout=1.0)
        self._detect_thread = None
        self._latest_frame_for_detect = None

        if not self._camera_running:
            self._camera_running = True
            # El hilo de detección lo arranca _camera_loop internamente
            self._camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
            self._camera_thread.start()
            self.after(1000, lambda: self.lbl_status.configure(
                text=t("scan.position_face"), text_color="#FFFFFF"
            ))

    def on_hide(self) -> None:
        """Detiene captura de vídeo al salir de la pantalla."""
        self._camera_running = False
        self._latest_frame_for_detect = None
        self._door_wait_active = False
        self._door_open_seen = False
        if self._door_wait_job:
            self.after_cancel(self._door_wait_job)
            self._door_wait_job = None

        # Liberar la cámara antes de joinear para que get_frame() retorne rápido.
        if self.face_manager and self.face_manager.initialized:
            try:
                self.face_manager.release()
            except Exception as e:
                logger.warning("Error liberando cámara en on_hide: %s", e)

        if self._camera_thread and self._camera_thread.is_alive():
            self._camera_thread.join(timeout=1.0)
        self._camera_thread = None

        if self._detect_thread and self._detect_thread.is_alive():
            self._detect_thread.join(timeout=1.0)
        self._detect_thread = None

        if self._return_job:
            self.after_cancel(self._return_job)
            self._return_job = None
        self.door_warning_overlay.place_forget()
        logger.info("Camera capture detenido")

    def on_face_match(self, user_data: dict) -> None:
        """Muestra el overlay de resultado según si el usuario tiene locker o no."""
        self._success_shown = True
        self._camera_running = False
        self._user_data = user_data

        nombre    = user_data.get("nombre", "—")
        matricula = user_data.get("matricula", "—")
        locker_num = user_data.get("locker_numero")

        # Reordenar labels (pack_forget todos primero, luego pack en orden correcto)
        for w in self._success_inner.winfo_children():
            w.pack_forget()

        self.lbl_success_icon.pack(pady=(0, 10))

        self.lbl_success_name.configure(text=nombre)
        self.lbl_success_name.pack(pady=(0, 2))

        self.lbl_success_matricula.configure(
            text=f"{t('scan.matricula_label')}  {matricula}"
        )
        self.lbl_success_matricula.pack(pady=(0, 16))

        if locker_num:
            self.overlay_bg.configure(fg_color="#5B8C5A")          # verde: locker desbloqueado
            self.lbl_status.configure(text=t("scan.access_granted"), text_color="#A5D6A7")
            self.lbl_success_main.configure(text=t("scan.unlocked"))
            self.lbl_success_main.pack(pady=(0, 4))
            self.lbl_success_locker_label.configure(text=t("scan.locker_label"))
            self.lbl_success_locker_label.pack(pady=(0, 0))
            self.lbl_success_locker_big.configure(text=str(locker_num))
            self.lbl_success_locker_big.pack(pady=(0, 6))
        else:
            self.overlay_bg.configure(fg_color="#B8860B")          # amarillo: sin locker
            self.lbl_status.configure(text=t("scan.identity_verified"), text_color="#FFF8E1")
            self.lbl_success_main.configure(text=t("scan.success_identity"))
            self.lbl_success_main.pack(pady=(0, 8))
            self.lbl_success_sub.configure(text=t("scan.success_no_locker"))
            self.lbl_success_sub.pack(pady=(0, 8))

        self.lbl_countdown.pack(pady=(6, 0))

        self.lbl_attempts.configure(text="")
        self.overlay_bg.place(x=0, y=0, relwidth=1, relheight=1)
        self.btn_admin.place_forget()
        if locker_num and self._should_wait_for_door(int(locker_num)):
            self._start_door_close_wait(int(locker_num), user_data.get("locker_assignment_id"))
        else:
            self._start_countdown(self.DISPLAY_SECONDS)

    def on_face_no_match(self) -> None:
        """Llamado cuando no hay match."""
        if self._success_shown:
            return

        self._reset_liveness_state()
        self._attempts += 1
        self.scan_progress_bar.set(0)

        if self._attempts >= self.MAX_ATTEMPTS:
            # Registrar un único intento fallido al agotar los 3 intentos
            access_log_service.register_access(
                self._last_failed_closest.get("idLockerAsignado") if self._last_failed_closest else None,
                permitted=False,
                motivo="no_reconocido",
            )
            self._last_failed_closest = None
            # Mostrar overlay rojo 3 segundos, luego el PIN
            self.lbl_attempts.configure(text="")
            self.btn_admin.place_forget()
            self.denied_overlay.place(x=0, y=0, relwidth=1, relheight=1)
            self.denied_overlay.lift()
            self.after(3000, self._dismiss_denied_overlay)
        else:
            self.lbl_attempts.configure(
                text=t("scan.attempts", a=self._attempts, m=self.MAX_ATTEMPTS)
            )
            self.lbl_status.configure(
                text=t("scan.position_face"),
                text_color="#FFFFFF",
            )

    def _dismiss_denied_overlay(self) -> None:
        """Cierra el overlay rojo y abre el panel de PIN."""
        self.denied_overlay.place_forget()
        if not self._success_shown:
            self._show_pin_overlay()

    def _show_denied_to_standby(self) -> None:
        """Muestra overlay de acceso denegado 3 segundos y regresa al inicio."""
        self.btn_admin.place_forget()
        self.denied_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.denied_overlay.lift()
        self.after(3000, self._dismiss_denied_to_standby)

    def _dismiss_denied_to_standby(self) -> None:
        self.denied_overlay.place_forget()
        if not self._success_shown:
            self._go_standby()

    # ── Countdown ─────────────────────────────────────────────────────────────

    def _start_countdown(self, seconds: int) -> None:
        if self._return_job is not None:
            self.after_cancel(self._return_job)

        if seconds <= 0:
            self._go_standby()
            return

        self.lbl_countdown.configure(text=t("scan.return_in", s=seconds))
        self._return_job = self.after(1000, self._start_countdown, seconds - 1)

    def _should_wait_for_door(self, locker_id: int) -> bool:
        active = DOOR_SWITCH_CONFIG.get("active_lockers", [])
        return int(locker_id) in [int(x) for x in active]

    def _start_door_close_wait(self, locker_id: int, assignment_id: int | None) -> None:
        from core.door_switch_controller import get_door_switch_controller

        controller = get_door_switch_controller()
        if not controller.is_available():
            self._start_countdown(self.DISPLAY_SECONDS)
            return

        self._door_wait_active = True
        self._door_wait_phase = "waiting"
        self._door_open_seen = False
        self._door_wait_locker_id = int(locker_id)
        self._door_wait_assignment_id = assignment_id
        self._door_wait_started_at = time.time()
        self.lbl_countdown.configure(text=t("door.waiting_close"))
        self._poll_door_close()

    def _poll_door_close(self) -> None:
        if not self._door_wait_active or self._door_wait_locker_id is None:
            return

        from core.door_switch_controller import get_door_switch_controller

        controller = get_door_switch_controller()
        state = controller.read_state(self._door_wait_locker_id)
        now = time.time()
        elapsed = now - self._door_wait_started_at

        if state is None:
            self._door_wait_active = False
            self._door_wait_job = None
            self._start_countdown(self.DISPLAY_SECONDS)
            return

        if state is False:
            self._door_open_seen = True

        # Door closed after being opened → success, go to standby
        if state is True and self._door_open_seen:
            self._door_wait_active = False
            if self._door_wait_job:
                self.after_cancel(self._door_wait_job)
                self._door_wait_job = None
            access_log_service.register_access(
                self._door_wait_assignment_id,
                permitted=True,
                motivo="puerta_cerrada",
            )
            self._go_standby()
            return

        # Phase transition: waiting → alerting at DOOR_ALERT_DELAY_S
        if self._door_wait_phase == "waiting" and elapsed >= self.DOOR_ALERT_DELAY_S:
            self._door_wait_phase = "alerting"
            self._show_door_alert()

        # Phase end: alerting expires → mark locker open and go to standby
        if self._door_wait_phase == "alerting" and elapsed >= self.DOOR_ALERT_DELAY_S + self.DOOR_ALERT_DURATION_S:
            self._door_wait_active = False
            if self._door_wait_job:
                self.after_cancel(self._door_wait_job)
                self._door_wait_job = None
            access_log_service.register_access(
                self._door_wait_assignment_id,
                permitted=False,
                motivo="puerta_no_cerrada",
            )
            from ui.locker_screen.door_state import add_open_locker
            add_open_locker(self._door_wait_locker_id)
            self._go_standby()
            # Badge must be lifted AFTER show_frame raises the new screen
            if hasattr(self.controller, "show_open_locker_badge"):
                self.controller.show_open_locker_badge()
            return

        poll_ms = int(DOOR_SWITCH_CONFIG.get("poll_interval_ms", 200))
        self._door_wait_job = self.after(poll_ms, self._poll_door_close)

    def _show_door_alert(self) -> None:
        self.overlay_bg.place_forget()
        self.canvas.delete("all")
        if self._door_wait_locker_id is not None:
            self.lbl_door_warning_locker.configure(
                text=str(self._door_wait_locker_id)
            )
        self.door_warning_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.door_warning_overlay.lift()

    # ── Métodos internos ──────────────────────────────────────────────────────

    def _go_standby(self) -> None:
        from ui.locker_screen.standby_screen import StandbyScreen
        self.controller.show_frame(StandbyScreen)

    def _finalize_auto_return(self) -> None:
        if self._camera_thread and self._camera_thread.is_alive():
            elapsed = 0.0
            if self._auto_return_started_ts is not None:
                elapsed = time.time() - self._auto_return_started_ts
            if elapsed >= 1.5 and self.face_manager and self.face_manager.initialized:
                try:
                    self.face_manager.release()
                except Exception as e:
                    logger.debug("Auto-return: fallo al liberar camara: %s", e)
            self.after(120, self._finalize_auto_return)
            return

        self._auto_return_started_ts = None
        self._go_standby()

    def _go_admin_login(self) -> None:
        # Detener reconocimiento ANTES de construir los frames de admin
        # para evitar que una detección en vuelo abra el locker.
        self._camera_running = False
        from ui.admin.login_screen import LoginScreen
        if hasattr(self.controller, "ensure_admin_frames"):
            self.controller.ensure_admin_frames()
        self.controller.show_frame(LoginScreen)

    def _reset_liveness_state(self) -> None:
        self._liveness_passed = False
        self._passive_liveness_ok = False
        self._active_liveness_ok = False
        self._liveness_motion_score = 0.0
        self._liveness_shift_score = 0.0
        self._liveness_face_history.clear()
        self._liveness_box_history.clear()
        self._challenge_ref_box = None
        self._challenge_index = 0
        self._challenge_started_at = 0.0
        self._blink_closed_seen = False
        self._challenge_steps = self._build_liveness_challenge()

    def _build_liveness_challenge(self) -> list[str]:
        # OPTIMIZADO: Sin challenges activos - solo detección pasiva de micromovimientos
        # Esto hace el desbloqueo tan rápido como iPhone Face ID
        return []

    def _challenge_prompt(self) -> str:
        # OPTIMIZADO: Mensaje simple sin instrucciones mareantes
        return "Prueba de vida: detectando..."

    def _extract_face_gray(self, frame: np.ndarray, face_box: tuple) -> Optional[np.ndarray]:
        try:
            x, y, w, h = [int(v) for v in face_box[:4]]
            if w <= 0 or h <= 0:
                return None

            pad = int(max(w, h) * 0.12)
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(frame.shape[1], x + w + pad)
            y2 = min(frame.shape[0], y + h + pad)
            if x2 <= x1 or y2 <= y1:
                return None

            roi = frame[y1:y2, x1:x2]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (96, 96), interpolation=cv2.INTER_AREA)
            return gray
        except Exception:
            return None

    def _update_liveness(self, frame: np.ndarray, face_box: tuple) -> None:
        gray = self._extract_face_gray(frame, face_box)
        if gray is None:
            return

        x, y, w, h = [int(v) for v in face_box[:4]]
        center = (x + (w * 0.5), y + (h * 0.5), max(1.0, float(w)), max(1.0, float(h)))

        self._liveness_face_history.append(gray)
        self._liveness_box_history.append(center)

        # OPTIMIZADO: Solo 2 frames mínimos para detección ultra-rápida (iPhone-style)
        if len(self._liveness_face_history) < 2:
            return

        motion_vals = []
        hist = list(self._liveness_face_history)
        for i in range(1, len(hist)):
            diff = cv2.absdiff(hist[i], hist[i - 1])
            motion_vals.append(float(np.mean(diff)))
        self._liveness_motion_score = float(np.mean(motion_vals)) if motion_vals else 0.0

        first = self._liveness_box_history[0]
        last = self._liveness_box_history[-1]
        norm = max(first[2], first[3], 1.0)
        shift = np.sqrt((last[0] - first[0]) ** 2 + (last[1] - first[1]) ** 2) / norm
        self._liveness_shift_score = float(shift)

        texture = float(cv2.Laplacian(hist[-1], cv2.CV_64F).var())

        # OPTIMIZADO: Thresholds más permisivos para desbloqueo rápido tipo iPhone
        movement_ok = (
            self._liveness_motion_score >= self.LIVENESS_MIN_MOTION
            or self._liveness_shift_score >= self.LIVENESS_MIN_BOX_SHIFT
        )
        texture_ok = texture >= 8.0  # Mejorado: de 20.0 a 8.0 - más tolerante con iluminación

        self._passive_liveness_ok = bool(movement_ok and texture_ok)
        self._update_active_liveness(frame, face_box)
        self._liveness_passed = self._passive_liveness_ok and self._active_liveness_ok

    def _update_active_liveness(self, frame: np.ndarray, face_box: tuple) -> None:
        if not self._challenge_steps:
            self._active_liveness_ok = True
            return

        now = datetime.now().timestamp()
        if self._challenge_started_at == 0.0:
            self._challenge_started_at = now
            self._challenge_ref_box = face_box
            return

        if now - self._challenge_started_at > self.LIVENESS_CHALLENGE_TIMEOUT:
            self._challenge_steps = self._build_liveness_challenge()
            self._challenge_index = 0
            self._challenge_started_at = now
            self._challenge_ref_box = face_box
            self._blink_closed_seen = False
            return

        if self._challenge_ref_box is None:
            self._challenge_ref_box = face_box
            return

        if self._challenge_index >= len(self._challenge_steps):
            self._active_liveness_ok = True
            return

        ref_x, ref_y, ref_w, ref_h = [float(v) for v in self._challenge_ref_box[:4]]
        x, y, w, h = [float(v) for v in face_box[:4]]
        ref_cx = ref_x + (ref_w * 0.5)
        ref_cy = ref_y + (ref_h * 0.5)
        cx = x + (w * 0.5)
        cy = y + (h * 0.5)
        dx_norm = (cx - ref_cx) / max(1.0, ref_w)
        area_ratio = ((w * h) / max(1.0, ref_w * ref_h)) - 1.0

        target = self._challenge_steps[self._challenge_index]
        passed = False
        if target == "left":
            passed = dx_norm <= -self.CHALLENGE_SHIFT_THRESHOLD
        elif target == "right":
            passed = dx_norm >= self.CHALLENGE_SHIFT_THRESHOLD
        elif target == "closer":
            passed = area_ratio >= self.CHALLENGE_SCALE_IN_THRESHOLD
        elif target == "away":
            passed = area_ratio <= self.CHALLENGE_SCALE_OUT_THRESHOLD
        elif target == "blink":
            passed = self._detect_blink(frame, face_box)

        if passed:
            self._challenge_index += 1
            self._challenge_ref_box = face_box
            if self._challenge_index >= len(self._challenge_steps):
                self._active_liveness_ok = True

    def _detect_blink(self, frame: np.ndarray, face_box: tuple) -> bool:
        if not self.face_manager:
            return False
        if not getattr(self.face_manager.embedding_extractor, "uses_dlib", False):
            return False

        landmarks = self.face_manager.get_landmarks(frame, face_box)
        if not landmarks or len(landmarks) < 68:
            return False

        def _ear(indices: list[int]) -> float:
            pts = [np.array(landmarks[i], dtype=np.float32) for i in indices]
            a = np.linalg.norm(pts[1] - pts[5])
            b = np.linalg.norm(pts[2] - pts[4])
            c = np.linalg.norm(pts[0] - pts[3])
            if c <= 0.0:
                return 0.0
            return float((a + b) / (2.0 * c))

        left_ear = _ear([36, 37, 38, 39, 40, 41])
        right_ear = _ear([42, 43, 44, 45, 46, 47])
        ear = (left_ear + right_ear) * 0.5

        if ear < 0.20:
            self._blink_closed_seen = True
            return False
        if self._blink_closed_seen and ear > 0.24:
            self._blink_closed_seen = False
            return True
        return False

    # ── Overlay de autenticación por PIN ──────────────────────────────────────

    def _build_pin_overlay(self) -> None:
        """Overlay de dos pasos: Paso 1 → matrícula, Paso 2 → PIN."""
        self.pin_overlay = ctk.CTkFrame(
            self,
            fg_color="#1A1A2E",
            corner_radius=0,
            width=self.WIN_W,
            height=self.WIN_H,
        )

        self.lbl_pin_step = ctk.CTkLabel(
            self.pin_overlay,
            text=t("pin.step1"),
            font=ctk.CTkFont(size=11),
            text_color=self.MUTED,
        )
        self.lbl_pin_step.pack(pady=(52, 2))

        self.lbl_pin_title = ctk.CTkLabel(
            self.pin_overlay,
            text=t("pin.title_enter_matricula"),
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=self.TEXT_COLOR,
        )
        self.lbl_pin_title.pack(pady=(0, 4))

        self.lbl_pin_instruction = ctk.CTkLabel(
            self.pin_overlay,
            text=t("pin.instruction_matricula"),
            font=ctk.CTkFont(size=13),
            text_color=self.MUTED,
        )
        self.lbl_pin_instruction.pack(pady=(0, 16))

        # Campo de entrada
        input_frame = ctk.CTkFrame(
            self.pin_overlay,
            fg_color="#2A2A3E",
            corner_radius=12,
            width=340,
            height=60,
        )
        input_frame.pack(pady=(0, 4))
        input_frame.pack_propagate(False)

        self.lbl_pin_display = ctk.CTkLabel(
            input_frame,
            text="",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="#FFFFFF",
        )
        self.lbl_pin_display.place(relx=0.5, rely=0.5, anchor="center")

        self.lbl_pin_error = ctk.CTkLabel(
            self.pin_overlay,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=self.DANGER,
        )
        self.lbl_pin_error.pack(pady=(4, 8))

        # Teclado numérico 3×4
        numpad_frame = ctk.CTkFrame(self.pin_overlay, fg_color="transparent")
        numpad_frame.pack()

        layout = [
            ("1", "2", "3"),
            ("4", "5", "6"),
            ("7", "8", "9"),
            ("⌫", "0", "✓"),
        ]

        for row_idx, row in enumerate(layout):
            for col_idx, label in enumerate(row):
                if label == "⌫":
                    cmd = self._pin_backspace
                    fg = "#3A3A5E"
                    hover = "#4A4A7E"
                elif label == "✓":
                    cmd = self._pin_confirm
                    fg = self.PRIMARY
                    hover = "#6A9F69"
                else:
                    digit = label
                    cmd = lambda d=digit: self._pin_digit(d)
                    fg = "#2A2A4E"
                    hover = "#3A3A6E"

                ctk.CTkButton(
                    numpad_frame,
                    text=label,
                    font=ctk.CTkFont(size=28, weight="bold"),
                    fg_color=fg,
                    hover_color=hover,
                    text_color="#FFFFFF",
                    width=96,
                    height=72,
                    corner_radius=12,
                    command=cmd,
                ).grid(row=row_idx, column=col_idx, padx=8, pady=8)

        ctk.CTkButton(
            self.pin_overlay,
            text=t("pin.cancel"),
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            hover_color="#333355",
            text_color=self.MUTED,
            border_width=1,
            border_color=self.MUTED,
            width=200,
            height=44,
            corner_radius=10,
            command=self._cancel_pin,
        ).pack(pady=(16, 0))

    def _show_pin_overlay(self) -> None:
        if self._success_shown:
            return
        self._camera_running = False  # detener reconocimiento mientras se usa el PIN
        self._pin_state = "matricula"
        self._pin_matricula = ""
        self._pin_code = ""
        self._found_user = None
        self.lbl_pin_step.configure(text=t("pin.step1"))
        self.lbl_pin_title.configure(
            text=t("pin.title_enter_matricula"), text_color=self.TEXT_COLOR
        )
        self.lbl_pin_instruction.configure(
            text=t("pin.instruction_matricula")
        )
        self.lbl_pin_display.configure(text="")
        self.lbl_pin_error.configure(text="")
        self.pin_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.pin_overlay.lift()

    def _hide_pin_overlay(self) -> None:
        self.pin_overlay.place_forget()

    def _update_pin_display(self) -> None:
        if self._pin_state == "matricula":
            self.lbl_pin_display.configure(text=self._pin_matricula)
        else:
            self.lbl_pin_display.configure(text="●" * len(self._pin_code))

    def _pin_digit(self, digit: str) -> None:
        self.lbl_pin_error.configure(text="")
        if self._pin_state == "matricula":
            if len(self._pin_matricula) < 8:          # máx 8 dígitos de matrícula
                self._pin_matricula += digit
        else:
            if len(self._pin_code) < 4:               # máx 4 dígitos de PIN
                self._pin_code += digit
        self._update_pin_display()

    def _pin_backspace(self) -> None:
        if self._pin_state == "matricula":
            self._pin_matricula = self._pin_matricula[:-1]
        else:
            self._pin_code = self._pin_code[:-1]
        self._update_pin_display()

    def _pin_confirm(self) -> None:
        if self._pin_state == "matricula":
            self._validate_matricula()
        else:
            self._verify_pin_auth()

    def _validate_matricula(self) -> None:
        """Paso 1: verifica que la matrícula exista en BD antes de pedir PIN."""
        mat = self._pin_matricula.strip()
        if not mat:
            self.lbl_pin_error.configure(text=t("pin.err_enter_matricula"))
            return
        if len(mat) < 5:
            self.lbl_pin_error.configure(text=t("pin.err_matricula_too_short"))
            return

        user = user_service.get_user_by_matricula(self._pin_matricula)
        if user is None:
            self._pin_matricula_fail_count += 1
            access_log_service.register_access(
                None, permitted=False, motivo="matricula_incorrecta"
            )
            if self._pin_matricula_fail_count >= 3:
                self._hide_pin_overlay()
                self._show_denied_to_standby()
                return
            remaining = 3 - self._pin_matricula_fail_count
            self.lbl_pin_error.configure(
                text=f"{t('pin.err_matricula_not_found')}  ({remaining} intento{'s' if remaining != 1 else ''} restante)"
            )
            self._pin_matricula = ""
            self._update_pin_display()
            return

        self._found_user = user
        full_name = " ".join(
            p for p in [user.get("nombre"), user.get("apPaterno")]
            if p
        ).strip()

        self._pin_state = "pin"
        self._pin_code = ""
        self.lbl_pin_step.configure(text=t("pin.step2"))
        self.lbl_pin_title.configure(
            text=t("pin.hello_name", name=full_name), text_color=self.PRIMARY
        )
        self.lbl_pin_instruction.configure(text=t("pin.instruction_pin"))
        self._update_pin_display()
        self.lbl_pin_error.configure(text="")

    def _verify_pin_auth(self) -> None:
        if not self._pin_code.strip():
            self.lbl_pin_error.configure(text=t("pin.err_enter_pin"))
            return

        if self._found_user is None:
            self.lbl_pin_error.configure(text=t("pin.err_restart"))
            return

        result = user_service.authenticate_user_by_pin(self._pin_matricula, self._pin_code)
        if result is None:
            self._pin_fail_count += 1
            remaining = self.PIN_MAX_FAILS - self._pin_fail_count
            if self._pin_fail_count >= self.PIN_MAX_FAILS:
                access_log_service.register_access(
                    None, permitted=False, motivo="limite_intentos_pin"
                )
                self._hide_pin_overlay()
                self._show_denied_to_standby()
                return
            access_log_service.register_access(
                None, permitted=False, motivo="pin_incorrecto"
            )
            s = "s" if remaining != 1 else ""
            self.lbl_pin_error.configure(
                text=f"{t('pin.err_pin_wrong')}  {t('pin.attempts_remaining', n=remaining, s=s)}"
            )
            self._pin_code = ""
            self._update_pin_display()
            return

        locker_id = result.get("idLocker")
        if locker_id:
            threading.Thread(target=locker_service.open_locker, args=(locker_id,), daemon=True).start()
        else:
            logger.info("PIN auth: usuario id=%s sin locker asignado", result.get("idUsuario"))

        access_log_service.register_access(
            result.get("idLockerAsignado"), permitted=True, motivo="pin"
        )

        full_name = " ".join(
            p for p in [result.get("nombre"), result.get("apPaterno"), result.get("apMaterno")]
            if p
        ).strip()

        user_data = {
            "nombre": full_name or "Usuario",
            "matricula": result.get("matricula") or "—",
            "locker_numero": locker_id,
            "locker_assignment_id": result.get("idLockerAsignado"),
            "fecha": datetime.now().strftime("%d/%m/%Y  %H:%M"),
        }
        self._hide_pin_overlay()
        self.on_face_match(user_data)

    def _cancel_pin(self) -> None:
        access_log_service.register_access(
            None, permitted=False, motivo="pin_cancelado"
        )
        self._go_standby()

    # ── Pantalla de bloqueo tras PIN fallido ──────────────────────────────────

    def _build_lock_overlay(self) -> None:
        """Pantalla de bloqueo mostrada tras agotar intentos de PIN."""
        self.lock_overlay = ctk.CTkFrame(
            self,
            fg_color="#0D0D1A",
            corner_radius=0,
            width=self.WIN_W,
            height=self.WIN_H,
        )

        ctk.CTkLabel(
            self.lock_overlay,
            text=t("lock.blocked"),
            font=ctk.CTkFont(size=48, weight="bold"),
            text_color=self.DANGER,
        ).pack(pady=(220, 8))

        ctk.CTkLabel(
            self.lock_overlay,
            text=t("lock.too_many_fails"),
            font=ctk.CTkFont(size=16),
            text_color=self.MUTED,
        ).pack(pady=(0, 36))

        self.lbl_lock_countdown = ctk.CTkLabel(
            self.lock_overlay,
            text="",
            font=ctk.CTkFont(size=18),
            text_color=self.TEXT_COLOR,
        )
        self.lbl_lock_countdown.pack()

        ctk.CTkLabel(
            self.lock_overlay,
            text=t("lock.auto_unlock"),
            font=ctk.CTkFont(size=12),
            text_color=self.MUTED,
        ).pack(pady=(12, 0))

    def _show_lock_screen(self) -> None:
        self._camera_running = False
        self.lock_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.lock_overlay.lift()
        self._lock_countdown(self.LOCK_SECONDS)

    def _hide_lock_overlay(self) -> None:
        self.lock_overlay.place_forget()

    def _lock_countdown(self, seconds: int) -> None:
        if not self.lock_overlay.winfo_ismapped():
            return
        if seconds <= 0:
            self._hide_lock_overlay()
            self._go_standby()
            return
        self.lbl_lock_countdown.configure(
            text=t("lock.wait", s=seconds, p="s" if seconds != 1 else "")
        )
        self.after(1000, self._lock_countdown, seconds - 1)

    def _recognize_current_face(self, frame: np.ndarray, faces: list) -> Optional[dict]:
        if not faces or not self.face_manager:
            return None

        face_box = (_largest_face(faces) or {}).get("box")
        if not face_box:
            return None

        probe_embedding = self.face_manager.get_embedding(frame, face_box)
        if probe_embedding is None:
            logger.debug("No se pudo extraer embedding para autenticación")
            return None

        probe_uses_dlib = getattr(self.face_manager.embedding_extractor, "uses_dlib", False)
        probe_model_prefix = "dlib" if probe_uses_dlib else "fallback"
        probe_vec = probe_embedding.astype(np.float32, copy=False)

        candidates = user_service.get_active_face_encodings()
        if not candidates:
            logger.warning("No hay encodings activos en BD para autenticar")
            return None

        matched, closest = user_service.find_best_face_match(probe_vec, probe_model_prefix, candidates)

        if matched is None:
            # Guardar closest para loguearlo una sola vez al agotar los intentos
            self._last_failed_closest = closest
            return None

        locker_id = matched.get("idLocker")
        user_id   = matched.get("idUsuario")
        if locker_id and self._camera_running:
            threading.Thread(target=locker_service.open_locker, args=(locker_id,), daemon=True).start()
        elif locker_id:
            logger.info("Reconocimiento completado pero cámara detenida — locker no abierto")
        else:
            logger.info("Usuario id=%s autenticado pero sin locker asignado", user_id)

        if locker_id:
            access_log_service.register_access(
                matched.get("idLockerAsignado"),
                permitted=True,
                user_id=user_id,
            )
        else:
            access_log_service.register_access(
                None,
                permitted=False,
                motivo="sin_asignacion",
                user_id=user_id,
            )

        full_name = " ".join(
            p for p in [matched.get("nombre"), matched.get("apPaterno"), matched.get("apMaterno")]
            if p
        ).strip()

        return {
            "nombre": full_name or "Usuario",
            "matricula": matched.get("matricula") or "—",
            "locker_numero": locker_id,
            "locker_assignment_id": matched.get("idLockerAsignado"),
            "fecha": datetime.now().strftime("%d/%m/%Y  %H:%M"),
        }
