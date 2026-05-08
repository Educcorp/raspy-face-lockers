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
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import tkinter
import logging
from typing import Optional
from datetime import datetime
from collections import deque
import random

from config import FACE_RECOGNITION_CONFIG
from config import GPIO_CONFIG
from core.gpio_controller import get_locker_gpio_controller
from services import user_service, locker_service, access_log_service

logger = logging.getLogger(__name__)


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
    DISPLAY_SECONDS = 8
    RECOGNITION_INTERVAL_FRAMES = 5   # intentos de reconocimiento cada 5 frames (~0.33s)
    STABLE_FACE_FRAMES = 12           # rostro estable ~0.8s antes de intentar reconocimiento
    RECOGNITION_COOLDOWN_SECONDS = 3.0  # mínimo 3s entre intentos de reconocimiento
    LIVENESS_HISTORY_FRAMES = 12      # 12 frames de historial de movimiento (~0.8s)
    LIVENESS_MIN_MOTION = 1.5         # requiere movimiento natural real (no ruido)
    LIVENESS_MIN_BOX_SHIFT = 0.015    # desplazamiento mínimo visible del rostro
    MIN_SCAN_SECONDS = 3.5            # tiempo mínimo de escaneo antes de intentar identificar
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

        # Variables de captura de cámara
        self._camera_thread: Optional[threading.Thread] = None
        self._camera_running = False
        self._camera_frame: Optional[np.ndarray] = None
        self._detected_faces = []
        self._photo_image: Optional[tkinter.PhotoImage] = None

        # Datos del usuario reconocido
        self._user_data: Optional[dict] = None

        # Estado del overlay de PIN
        self._pin_state: str = "matricula"  # "matricula" | "pin"
        self._pin_matricula: str = ""
        self._pin_code: str = ""
        self._pin_fail_count: int = 0
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
            text="POSICIONA TU ROSTRO",
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

        # ── Botón de retroceso (flecha) en la parte inferior ─────────────────
        self.btn_back = ctk.CTkButton(
            self,
            text="←",
            font=ctk.CTkFont(size=40, weight="bold"),
            fg_color="transparent",
            bg_color="transparent",
            hover_color="#CCCCCC",
            text_color="#FFFFFF",
            border_width=3,
            border_color="#FFFFFF",
            width=72, height=72,
            corner_radius=16,
            command=self._go_standby,
        )
        self.btn_back.place(x=80, rely=0.94, anchor="center")

        # ── Overlay de éxito (oculto por defecto) ────────────────────────────
        # Contenedor con fondo oscuro para overlay modal
        self.overlay_bg = ctk.CTkFrame(
            self,
            fg_color="#2A2A2E",  # Gris oscuro semi-transparente visualmente
            corner_radius=0,
            width=480,
            height=800,
            border_width=0,
        )

        # Frame principal del overlay con configuración explícita
        self.success_frame = ctk.CTkFrame(
            self.overlay_bg,
            fg_color="#5B8C5A",
            corner_radius=20,
            width=430,
            height=250,
            border_width=0,
        )
        # No se muestra aún — se coloca con .place() al detectar éxito

        # Layout principal horizontal: ícono (izquierda) + texto (derecha)
        success_content = ctk.CTkFrame(self.success_frame, fg_color="transparent", corner_radius=0)
        success_content.pack(fill="both", expand=True, padx=(40, 16), pady=16)
        success_content.grid_columnconfigure(0, weight=0)
        success_content.grid_columnconfigure(1, weight=1)
        success_content.grid_rowconfigure(0, weight=1)

        icon_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "assets", "icons", "icon_persona_blanco.png"
        )
        self._success_icon = None
        try:
            if os.path.exists(icon_path):
                icon_img = Image.open(icon_path)
                self._success_icon = ctk.CTkImage(
                    light_image=icon_img,
                    dark_image=icon_img,
                    size=(118, 118),
                )
        except Exception as e:
            logger.warning(f"No se pudo cargar icono de éxito: {e}")

        self.lbl_success_icon = ctk.CTkLabel(
            success_content,
            text="",
            image=self._success_icon,
            fg_color="transparent",
            width=120,
            height=120,
        )
        self.lbl_success_icon.grid(row=0, column=0, sticky="nw", padx=(22, 12))

        text_content = ctk.CTkFrame(success_content, fg_color="transparent", corner_radius=0)
        text_content.grid(row=0, column=1, sticky="nsew")

        # Título de locker
        self.lbl_success_title = ctk.CTkLabel(
            text_content,
            text="Locker numero",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
            anchor="w",
            justify="left",
        )
        self.lbl_success_title.pack(fill="x")

        # Número de locker
        self.lbl_success_locker = ctk.CTkLabel(
            text_content,
            text="00",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
            anchor="w",
            justify="left",
        )
        self.lbl_success_locker.pack(fill="x", pady=(0, 3))

        # Nombre del usuario
        self.lbl_success_name = ctk.CTkLabel(
            text_content,
            text="—",
            font=ctk.CTkFont(size=15),
            text_color="#FFFFFF",
            fg_color="transparent",
            anchor="w",
            justify="left",
        )
        self.lbl_success_name.pack(fill="x", pady=(0, 2))

        # Matrícula
        self.lbl_success_matricula = ctk.CTkLabel(
            text_content,
            text="Matrícula —",
            font=ctk.CTkFont(size=15),
            text_color="#FFFFFF",
            fg_color="transparent",
            anchor="w",
            justify="left",
        )
        self.lbl_success_matricula.pack(fill="x", pady=(0, 2))

        # Fecha
        self.lbl_success_fecha = ctk.CTkLabel(
            text_content,
            text="—",
            font=ctk.CTkFont(size=15),
            text_color="#FFFFFF",
            fg_color="transparent",
            anchor="w",
            justify="left",
        )
        self.lbl_success_fecha.pack(fill="x", pady=(0, 8))

        # Countdown
        self.lbl_countdown = ctk.CTkLabel(
            text_content,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#E6F4E6",
            fg_color="transparent",
            anchor="w",
            justify="left",
        )
        self.lbl_countdown.pack(fill="x")

    # ── Captura de video en background ────────────────────────────────────────

    def _camera_loop(self) -> None:
        """Thread worker que captura frames y detecta rostros."""
        import time

        if not self.face_manager:
            logger.error("FaceManager no inicializado")
            self.after(0, self._show_camera_error, "Gestor de reconocimiento facial no disponible")
            return

        if not self.face_manager.initialized:
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
        frame_count = 0

        try:
            while self._camera_running:
                frame, faces = self.face_manager.detect_faces_in_frame()

                if frame is None:
                    time.sleep(0.05)
                    continue

                frame_count += 1
                self._camera_frame = frame
                self._detected_faces = faces
                self._face_detected = len(faces) > 0
                self._frame_counter += 1

                if self._success_shown:
                    time.sleep(0.066)
                    continue

                now = time.time()

                if faces:
                    if self._stable_face_frames == 0:
                        # Primera vez que aparece el rostro en esta sesión
                        self._face_first_seen_ts = now
                    self._stable_face_frames += 1
                    self._last_seen_face_box = faces[0].get("box")
                    if self._last_seen_face_box:
                        self._update_liveness(frame, self._last_seen_face_box)
                else:
                    self._stable_face_frames = 0
                    self._last_seen_face_box = None
                    self._face_first_seen_ts = 0.0
                    self._scan_progress_pct = 0
                    self._reset_liveness_state()

                # Calcular cuánto tiempo lleva el rostro visible y actualizar progreso
                if self._face_first_seen_ts > 0:
                    scan_elapsed = now - self._face_first_seen_ts
                    self._scan_progress_pct = min(100, int(scan_elapsed / self.MIN_SCAN_SECONDS * 100))
                else:
                    scan_elapsed = 0.0
                    self._scan_progress_pct = 0

                enough_frames = self._frame_counter % self.RECOGNITION_INTERVAL_FRAMES == 0
                enough_stability = self._stable_face_frames >= self.STABLE_FACE_FRAMES
                cooldown_ok = (now - self._last_recognition_ts) >= self.RECOGNITION_COOLDOWN_SECONDS
                liveness_ok = self._liveness_passed
                scan_time_ok = scan_elapsed >= self.MIN_SCAN_SECONDS

                if faces and enough_frames and enough_stability and cooldown_ok and liveness_ok and scan_time_ok:
                    self._last_recognition_ts = now
                    try:
                        user_data = self._recognize_current_face(frame, faces)
                        if user_data:
                            self.after(0, self.on_face_match, user_data)
                        else:
                            self.after(0, self.on_face_no_match)
                    except Exception as recognition_error:
                        logger.error(f"Error durante autenticación facial: {recognition_error}")
                        self.after(0, self.on_face_no_match)

                try:
                    self._update_camera_display(frame, faces)
                except Exception as e:
                    logger.error(f"Error actualizando display: {e}")

                time.sleep(0.066)

                if frame_count % 30 == 0:
                    logger.info(f"Camera loop: {frame_count} frames, {len(faces)} rostros")

        except Exception as e:
            logger.error(f"Error en camera loop: {e}")
            self.after(0, self._show_camera_error, f"Error crítico: {str(e)}")
        finally:
            if self.face_manager:
                try:
                    self.face_manager.release()
                except:
                    pass
            logger.info(f"Camera loop finalizado. Total: {frame_count}")

    def _update_camera_display(self, frame: np.ndarray, faces: list) -> None:
        """Dibuja el frame en modo espejo y letterbox (sin zoom), con guía de rostro."""
        try:
            # BGR → RGB y espejo horizontal (modo selfie)
            frame_rgb = cv2.flip(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), 1)
            h, w = frame_rgb.shape[:2]

            # Letterbox: escalar manteniendo aspecto, sin recortar
            scale = min(self.WIN_W / w, self.WIN_H / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            frame_resized = cv2.resize(frame_rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

            # Centrar en lienzo negro
            canvas_arr = np.zeros((self.WIN_H, self.WIN_W, 3), dtype=np.uint8)
            x_off = (self.WIN_W - new_w) // 2
            y_off = (self.WIN_H - new_h) // 2
            canvas_arr[y_off:y_off + new_h, x_off:x_off + new_w] = frame_resized

            pil_image = Image.fromarray(canvas_arr, mode="RGB")
            draw = ImageDraw.Draw(pil_image)

            # Calcular cuadro guía (coordenadas en pantalla, ya en espejo)
            if len(faces) > 0:
                face_box = faces[0].get("box")
                if face_box:
                    fx, fy, fw, fh = face_box
                    # Espejo: invertir x en el espacio del frame original
                    fx_m = w - fx - fw
                    # Escalar al espacio de pantalla + offset letterbox
                    xs = int(fx_m * scale) + x_off
                    ys = int(fy  * scale) + y_off
                    ws = int(fw  * scale)
                    hs = int(fh  * scale)
                    pad = int(max(ws, hs) * 0.3)
                    x1 = max(0,        xs - pad)
                    y1 = max(0,        ys - pad)
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

            ppm_path = "/tmp/locker_scan.ppm"
            try:
                pil_image.save(ppm_path, "PPM")
                self._photo_image = tkinter.PhotoImage(file=ppm_path)
                self.after(0, self._set_camera_image)
            except Exception as e:
                logger.warning(f"Error creando PhotoImage: {e}")

        except Exception as e:
            logger.error(f"Error actualizando display: {e}")

    def _default_guide_box(self) -> tuple[int, int, int, int]:
        """Cuadro guía centrado cuando no hay rostro detectado."""
        cx, cy = self.WIN_W // 2, self.WIN_H // 2 - 40
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
        
        # Título de error
        self.canvas.create_text(
            self.WIN_W // 2, 150,
            text="✗ Error de Cámara",
            font=("Arial", 24, "bold"),
            fill="#FF6B6B",
            justify="center"
        )
        
        # Mensaje de error detallado
        self.canvas.create_text(
            self.WIN_W // 2, 300,
            text=error_msg,
            font=("Arial", 14),
            fill="#FFFFFF",
            justify="center",
            width=360
        )
        
        # Instrucción
        self.canvas.create_text(
            self.WIN_W // 2, 550,
            text="Presiona ← para volver al inicio",
            font=("Arial", 12),
            fill="#CCCCCC",
            justify="center"
        )
        
        # Actualizar status label
        self.lbl_status.configure(
            text="✗ Cámara no disponible",
            text_color="#FF6B6B"
        )
        
        # Asegurarse de que los botones estén visibles
        self.btn_back.place(x=80, rely=0.94, anchor="center")


    def _set_camera_image(self) -> None:
        """Pone la imagen en el canvas (main thread)."""
        try:
            if self._photo_image is not None:
                self.canvas.delete("all")
                self.canvas.create_image(0, 0, anchor="nw", image=self._photo_image)
                self.canvas.image = self._photo_image
                # Mantener el botón de regreso encima del canvas en todo momento
                self.btn_back.lift()

                # Actualizar barra de progreso y mensajes de estado
                if not self._success_shown:
                    if self._face_detected:
                        if self._liveness_passed:
                            pct = self._scan_progress_pct
                            self.scan_progress_bar.set(pct / 100)
                            if pct >= 100:
                                self.lbl_status.configure(
                                    text="IDENTIFICANDO...",
                                    text_color="#A5D6A7",
                                )
                            else:
                                self.lbl_status.configure(
                                    text=f"ESCANEANDO...  {pct}%",
                                    text_color="#FFD54F",
                                )
                        else:
                            self.scan_progress_bar.set(0)
                            self.lbl_status.configure(
                                text="Mueve ligeramente tu rostro",
                                text_color="#FFD54F",
                            )
                    else:
                        self.scan_progress_bar.set(0)
                        self.lbl_status.configure(
                            text="Posiciona tu rostro en el encuadre",
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
        self._reset_liveness_state()
        self._pin_fail_count = 0
        self._found_user = None
        self.lbl_status.configure(text="INICIANDO CÁMARA...", text_color="#FFFFFF")
        self.lbl_attempts.configure(text="")
        self.scan_progress_bar.set(0)
        self.overlay_bg.place_forget()
        self._hide_pin_overlay()
        self._hide_lock_overlay()
        self.btn_back.place(x=80, rely=0.94, anchor="center")
        self.btn_back.lift()

        if not self._camera_running:
            self._camera_running = True
            self._camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
            self._camera_thread.start()
            self.after(1000, lambda: self.lbl_status.configure(
                text="POSICIONA TU ROSTRO", text_color="#FFFFFF"
            ))

    def on_hide(self) -> None:
        """Detiene captura de vídeo al salir de la pantalla."""
        self._camera_running = False
        if self._camera_thread:
            self._camera_thread.join(timeout=2.0)
        try:
            self.gpio_controller.cleanup()
        except Exception as e:
            logger.warning(f"No se pudo limpiar GPIO al salir de scanning: {e}")
        if self._return_job:
            self.after_cancel(self._return_job)
            self._return_job = None
        logger.info("Camera capture detenido")

    def on_face_match(self, user_data: dict) -> None:
        """Muestra el overlay de resultado según si el usuario tiene locker o no."""
        self._success_shown = True
        self._camera_running = False  # detener cámara — ya no se necesita detectar más
        self._user_data = user_data

        locker_num = user_data.get("locker_numero")   # None si no tiene locker

        if locker_num:
            self.lbl_status.configure(text="✓ ACCESO CONCEDIDO", text_color="#A5D6A7")
            self.lbl_success_title.configure(text="Locker número")
            self.lbl_success_locker.configure(text=str(locker_num))
        else:
            # Usuario registrado en el sistema pero sin locker asignado
            self.lbl_status.configure(text="IDENTIDAD VERIFICADA", text_color="#FFD54F")
            self.lbl_success_title.configure(text="Sin locker")
            self.lbl_success_locker.configure(text="asignado")

        self.lbl_attempts.configure(text="")
        self.lbl_success_name.configure(text=user_data.get("nombre", "—"))
        self.lbl_success_matricula.configure(
            text=f"Matrícula  {user_data.get('matricula', '—')}"
        )
        self.lbl_success_fecha.configure(text=user_data.get("fecha", "—"))

        # Mostrar overlay de fondo completo
        self.overlay_bg.place(x=0, y=0, relwidth=1, relheight=1)
        # Centrar el cuadro verde dentro del overlay
        self.success_frame.place(relx=0.5, rely=0.66, anchor="center")
        self.btn_back.place_forget()

        # Iniciar countdown
        self._start_countdown(self.DISPLAY_SECONDS)

    def on_face_no_match(self) -> None:
        """Llamado cuando no hay match."""
        if self._success_shown:
            return

        self._reset_liveness_state()
        self._attempts += 1
        self.lbl_attempts.configure(
            text=f"Intentos: {self._attempts} / {self.MAX_ATTEMPTS}"
        )
        if self._attempts >= self.MAX_ATTEMPTS:
            self.lbl_status.configure(text="✗ No reconocido — usa tu PIN", text_color="#EF9A9A")
            self.after(1200, self._show_pin_overlay)
        else:
            self.lbl_status.configure(
                text=f"Rostro no reconocido ({self._attempts}/{self.MAX_ATTEMPTS})",
                text_color="#FFCC80",
            )

    # ── Countdown ─────────────────────────────────────────────────────────────

    def _start_countdown(self, seconds: int) -> None:
        if self._return_job is not None:
            self.after_cancel(self._return_job)

        if seconds <= 0:
            self._go_standby()
            return

        self.lbl_countdown.configure(text=f"Volviendo al inicio en {seconds} s…")
        self._return_job = self.after(1000, self._start_countdown, seconds - 1)

    # ── Métodos internos ──────────────────────────────────────────────────────

    def _go_standby(self) -> None:
        from ui.locker_screen.standby_screen import StandbyScreen
        self.controller.show_frame(StandbyScreen)

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

        # Indicador de paso
        self.lbl_pin_step = ctk.CTkLabel(
            self.pin_overlay,
            text="PASO 1 DE 2  ·  IDENTIFÍCATE",
            font=ctk.CTkFont(size=11),
            text_color=self.MUTED,
        )
        self.lbl_pin_step.pack(pady=(52, 2))

        # Título dinámico (cambia entre pasos)
        self.lbl_pin_title = ctk.CTkLabel(
            self.pin_overlay,
            text="Ingresa tu matrícula",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=self.TEXT_COLOR,
        )
        self.lbl_pin_title.pack(pady=(0, 4))

        # Subtítulo / instrucción
        self.lbl_pin_instruction = ctk.CTkLabel(
            self.pin_overlay,
            text="Escribe tu número de matrícula y presiona  ✓",
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
            text="Cancelar",
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            hover_color="#333355",
            text_color=self.MUTED,
            border_width=1,
            border_color=self.MUTED,
            width=200,
            height=44,
            corner_radius=10,
            command=self._go_standby,
        ).pack(pady=(16, 0))

    def _show_pin_overlay(self) -> None:
        if self._success_shown:
            return
        self._pin_state = "matricula"
        self._pin_matricula = ""
        self._pin_code = ""
        self._found_user = None
        self.lbl_pin_step.configure(text="PASO 1 DE 2  ·  IDENTIFÍCATE")
        self.lbl_pin_title.configure(
            text="Ingresa tu matrícula", text_color=self.TEXT_COLOR
        )
        self.lbl_pin_instruction.configure(
            text="Escribe tu número de matrícula y presiona  ✓"
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
            if len(self._pin_matricula) < 12:
                self._pin_matricula += digit
        else:
            if len(self._pin_code) < 8:
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
        if not self._pin_matricula.strip():
            self.lbl_pin_error.configure(text="Ingresa tu matrícula")
            return

        user = user_service.get_user_by_matricula(self._pin_matricula)
        if user is None:
            self.lbl_pin_error.configure(text="Matrícula no encontrada")
            return

        self._found_user = user
        full_name = " ".join(
            p for p in [user.get("nombre"), user.get("apPaterno")]
            if p
        ).strip()

        self._pin_state = "pin"
        self._pin_code = ""
        self.lbl_pin_step.configure(text="PASO 2 DE 2  ·  VERIFICA TU IDENTIDAD")
        self.lbl_pin_title.configure(
            text=f"Hola, {full_name}", text_color=self.PRIMARY
        )
        self.lbl_pin_instruction.configure(text="Ingresa tu PIN de 4 dígitos")
        self._update_pin_display()
        self.lbl_pin_error.configure(text="")

    def _verify_pin_auth(self) -> None:
        if not self._pin_code.strip():
            self.lbl_pin_error.configure(text="Ingresa tu PIN")
            return

        if self._found_user is None:
            self.lbl_pin_error.configure(text="Error: reinicia el proceso")
            return

        result = user_service.authenticate_user_by_pin(self._pin_matricula, self._pin_code)
        if result is None:
            self._pin_fail_count += 1
            remaining = self.PIN_MAX_FAILS - self._pin_fail_count
            if self._pin_fail_count >= self.PIN_MAX_FAILS:
                self._hide_pin_overlay()
                self.after(200, self._show_lock_screen)
                return
            self.lbl_pin_error.configure(
                text=f"Matrícula o PIN incorrecto  ({remaining} intento{'s' if remaining != 1 else ''} restante)"
            )
            self._pin_code = ""
            self._update_pin_display()
            return

        locker_id = result.get("idLocker")
        if locker_id:
            locker_service.open_locker(locker_id)
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
            "fecha": datetime.now().strftime("%d/%m/%Y  %H:%M"),
        }
        self._hide_pin_overlay()
        self.on_face_match(user_data)

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
            text="BLOQUEADO",
            font=ctk.CTkFont(size=48, weight="bold"),
            text_color=self.DANGER,
        ).pack(pady=(220, 8))

        ctk.CTkLabel(
            self.lock_overlay,
            text="Demasiados intentos fallidos",
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
            text="El sistema se desbloqueará automáticamente",
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
            text=f"Espera  {seconds}  segundo{'s' if seconds != 1 else ''}…"
        )
        self.after(1000, self._lock_countdown, seconds - 1)

    def _recognize_current_face(self, frame: np.ndarray, faces: list) -> Optional[dict]:
        if not faces or not self.face_manager:
            return None

        face_box = faces[0].get("box")
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
            access_log_service.register_access(
                closest.get("idLockerAsignado") if closest else None,
                permitted=False,
            )
            return None

        locker_id = matched.get("idLocker")
        if locker_id:
            locker_service.open_locker(locker_id)
        else:
            logger.info("Usuario id=%s autenticado pero sin locker asignado", matched.get("idUsuario"))

        access_log_service.register_access(matched.get("idLockerAsignado"), permitted=True)

        full_name = " ".join(
            p for p in [matched.get("nombre"), matched.get("apPaterno"), matched.get("apMaterno")]
            if p
        ).strip()

        return {
            "nombre": full_name or "Usuario",
            "matricula": matched.get("matricula") or "—",
            "locker_numero": locker_id,
            "fecha": datetime.now().strftime("%d/%m/%Y  %H:%M"),
        }
