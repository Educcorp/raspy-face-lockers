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
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import tkinter
import logging
from typing import Optional
from datetime import datetime
from datetime import timedelta
from collections import deque
import random

from config import FACE_RECOGNITION_CONFIG
from database.connection import fetch_all, execute

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
    DISPLAY_SECONDS = 8
    RECOGNITION_INTERVAL_FRAMES = 6
    STABLE_FACE_FRAMES = 8
    RECOGNITION_COOLDOWN_SECONDS = 2.0
    LIVENESS_HISTORY_FRAMES = 10
    LIVENESS_MIN_MOTION = 2.4
    LIVENESS_MIN_BOX_SHIFT = 0.03
    LIVENESS_CHALLENGE_TIMEOUT = 9.0
    CHALLENGE_SHIFT_THRESHOLD = 0.16
    CHALLENGE_SCALE_IN_THRESHOLD = 0.18
    CHALLENGE_SCALE_OUT_THRESHOLD = -0.15

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

        # Inicializar módulo de reconocimiento facial
        try:
            from core.face_recognition import get_face_recognition_manager
            self.face_manager = get_face_recognition_manager()
        except Exception as e:
            logger.error(f"Error importando FaceRecognitionManager: {e}")
            self.face_manager = None

        self._build_ui()
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

        # ── Status label en la parte superior ─────────────────────────────────
        self.lbl_status = ctk.CTkLabel(
            self,
            text="POSICIONA TU ROSTRO",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=self.TEXT_COLOR,
            fg_color="transparent",
            bg_color="transparent",
            corner_radius=0,
            height=40,
        )
        self.lbl_status.place(relx=0.5, y=100, anchor="center")

        # ── Contador de intentos ──────────────────────────────────────────────
        self.lbl_attempts = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=self.MUTED,
            fg_color="transparent",
        )
        self.lbl_attempts.place(relx=0.5, y=72, anchor="n")

        # ── Botón de retroceso (flecha) en la parte inferior ─────────────────
        self.btn_back = ctk.CTkButton(
            self,
            text="←",
            font=ctk.CTkFont(size=40, weight="bold"),
            fg_color=self.PRIMARY,  # Verde del tema
            hover_color="#4A7A49",
            text_color="#FFFFFF",
            width=70, height=70,
            corner_radius=12,  # Esquinas redondeadas pero cuadrado
            command=self._go_standby,
        )
        self.btn_back.place(x=80, rely=0.94, anchor="center")

        # ── Overlay de éxito (oculto por defecto) ────────────────────────────
        # Diseño horizontal más compacto
        self.success_frame = ctk.CTkFrame(
            self,
            fg_color="#5B8C5A",  # Verde del tema
            corner_radius=20,
            width=440,
            height=240,
            border_width=0,
        )
        # No se muestra aún — se coloca con .place() al detectar éxito

        # Todo el contenido centrado verticalmente con pack

        # ✓ ROSTRO GENERADO
        self.lbl_success_title = ctk.CTkLabel(
            self.success_frame,
            text="✓ ROSTRO GENERADO",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
        )
        self.lbl_success_title.pack(pady=(15, 10))

        # Frame horizontal para LOCKER + número
        locker_frame = ctk.CTkFrame(
            self.success_frame,
            fg_color="transparent",
        )
        locker_frame.pack(pady=(5, 10))

        # "LOCKER" (izquierda)
        lbl_locker_title = ctk.CTkLabel(
            locker_frame,
            text="LOCKER",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
        )
        lbl_locker_title.pack(side="left", padx=(0, 8))

        # Número de locker (derecha)
        self.lbl_success_locker = ctk.CTkLabel(
            locker_frame,
            text="00",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
        )
        self.lbl_success_locker.pack(side="left")

        # Nombre del usuario
        self.lbl_success_name = ctk.CTkLabel(
            self.success_frame,
            text="—",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
        )
        self.lbl_success_name.pack(pady=(0, 4))

        # Matrícula
        self.lbl_success_matricula = ctk.CTkLabel(
            self.success_frame,
            text="Matrícula —",
            font=ctk.CTkFont(size=13),
            text_color="#E8F5E9",
            fg_color="transparent",
        )
        self.lbl_success_matricula.pack(pady=(0, 4))

        # Fecha
        self.lbl_success_fecha = ctk.CTkLabel(
            self.success_frame,
            text="—",
            font=ctk.CTkFont(size=12),
            text_color="#E8F5E9",
            fg_color="transparent",
        )
        self.lbl_success_fecha.pack(pady=(0, 8))

        # Countdown
        self.lbl_countdown = ctk.CTkLabel(
            self.success_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#C8E6C9",
            fg_color="transparent",
        )
        self.lbl_countdown.pack(pady=(0, 10))

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

                if faces:
                    self._stable_face_frames += 1
                    self._last_seen_face_box = faces[0].get("box")
                    if self._last_seen_face_box:
                        self._update_liveness(frame, self._last_seen_face_box)
                else:
                    self._stable_face_frames = 0
                    self._last_seen_face_box = None
                    self._reset_liveness_state()

                enough_frames = self._frame_counter % self.RECOGNITION_INTERVAL_FRAMES == 0
                enough_stability = self._stable_face_frames >= self.STABLE_FACE_FRAMES
                cooldown_ok = (time.time() - self._last_recognition_ts) >= self.RECOGNITION_COOLDOWN_SECONDS
                liveness_ok = self._liveness_passed

                if faces and enough_frames and enough_stability and cooldown_ok and liveness_ok:
                    self._last_recognition_ts = time.time()
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
        """Dibuja el frame de cámara a pantalla completa con cuadro dinámico siguiendo el rostro."""
        try:
            # Picamera2 "RGB888" retorna BGR en memoria — convertir a RGB para PIL
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Redimensionar con crop al centro para llenar pantalla completa
            h, w = frame_rgb.shape[:2]
            target_aspect = self.WIN_W / self.WIN_H  # 480/800 = 0.6
            frame_aspect = w / h

            if frame_aspect > target_aspect:
                # Frame es más ancho - crop horizontal
                new_h = h
                new_w = int(h * target_aspect)
                x_offset = (w - new_w) // 2
                y_offset = 0
                frame_cropped = frame_rgb[y_offset:y_offset+new_h, x_offset:x_offset+new_w]
            else:
                # Frame es más alto - crop vertical
                new_w = w
                new_h = int(w / target_aspect)
                x_offset = 0
                y_offset = (h - new_h) // 2
                frame_cropped = frame_rgb[y_offset:y_offset+new_h, x_offset:x_offset+new_w]

            # Redimensionar al tamaño exacto de la pantalla
            frame_resized = cv2.resize(frame_cropped, (self.WIN_W, self.WIN_H), interpolation=cv2.INTER_LINEAR)

            # Convertir a PIL
            pil_image = Image.fromarray(frame_resized, mode="RGB")

            # Dibujar guía de escaneo con esquinas en L
            draw = ImageDraw.Draw(pil_image)

            # Determinar coordenadas del cuadro (dinámicas si hay rostro, fijas si no)
            if len(faces) > 0:
                face_box = faces[0].get("box")
                if face_box:
                    # Calcular factor de escala para las coordenadas de la cara
                    scale_x = self.WIN_W / new_w
                    scale_y = self.WIN_H / new_h

                    x, y, face_w, face_h = face_box

                    # Ajustar coordenadas por el crop
                    if frame_aspect > target_aspect:
                        # Crop horizontal
                        x = x - x_offset
                    else:
                        # Crop vertical
                        y = y - y_offset

                    # Escalar al tamaño de pantalla
                    x = int(x * scale_x)
                    y = int(y * scale_y)
                    face_w = int(face_w * scale_x)
                    face_h = int(face_h * scale_y)

                    # Agregar padding al cuadro para que sea más amplio
                    padding = int(max(face_w, face_h) * 0.3)
                    x1 = max(0, x - padding)
                    y1 = max(0, y - padding)
                    x2 = min(self.WIN_W, x + face_w + padding)
                    y2 = min(self.WIN_H, y + face_h + padding)
                else:
                    # Si no hay box, usar coordenadas fijas
                    cx, cy = self.WIN_W // 2, self.WIN_H // 2 - 40
                    box_width = 280
                    box_height = 360
                    x1 = cx - (box_width // 2)
                    y1 = cy - (box_height // 2)
                    x2 = cx + (box_width // 2)
                    y2 = cy + (box_height // 2)
            else:
                # Sin rostro: guía fija centrada
                cx, cy = self.WIN_W // 2, self.WIN_H // 2 - 40
                box_width = 280
                box_height = 360
                x1 = cx - (box_width // 2)
                y1 = cy - (box_height // 2)
                x2 = cx + (box_width // 2)
                y2 = cy + (box_height // 2)

            # Color del cuadro: verde si rostro detectado correctamente, rojo si no
            if self._liveness_passed:
                box_color = (90, 180, 90)  # Verde
            else:
                box_color = (200, 80, 80)  # Rojo

            # Dibujar solo las esquinas en forma de L
            corner_length = 40  # Longitud de cada línea de la esquina
            line_width = 5

            # Esquina superior izquierda
            draw.line([(x1, y1), (x1 + corner_length, y1)], fill=box_color, width=line_width)  # Horizontal
            draw.line([(x1, y1), (x1, y1 + corner_length)], fill=box_color, width=line_width)  # Vertical

            # Esquina superior derecha
            draw.line([(x2 - corner_length, y1), (x2, y1)], fill=box_color, width=line_width)  # Horizontal
            draw.line([(x2, y1), (x2, y1 + corner_length)], fill=box_color, width=line_width)  # Vertical

            # Esquina inferior izquierda
            draw.line([(x1, y2 - corner_length), (x1, y2)], fill=box_color, width=line_width)  # Vertical
            draw.line([(x1, y2), (x1 + corner_length, y2)], fill=box_color, width=line_width)  # Horizontal

            # Esquina inferior derecha
            draw.line([(x2, y2 - corner_length), (x2, y2)], fill=box_color, width=line_width)  # Vertical
            draw.line([(x2 - corner_length, y2), (x2, y2)], fill=box_color, width=line_width)  # Horizontal

            # Convertir a RGB para PhotoImage
            pil_rgb = pil_image.convert("RGB")

            import tempfile
            ppm_path = "/tmp/locker_scan.ppm"
            try:
                pil_rgb.save(ppm_path, "PPM")
                new_photo = tkinter.PhotoImage(file=ppm_path)
                self._photo_image = new_photo
                self.after(0, self._set_camera_image)
            except Exception as e:
                logger.warning(f"Error creando PhotoImage: {e}")

        except Exception as e:
            logger.error(f"Error actualizando display: {e}")

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

                # Actualizar texto del status según detección (label siempre visible)
                if not self._success_shown:
                    if self._face_detected:
                        if self._liveness_passed:
                            self.lbl_status.configure(
                                text="✓ ROSTRO DETECTADO",
                                text_color="#A5D6A7",
                            )
                        else:
                            challenge_text = self._challenge_prompt()
                            # Extraer solo la acción del desafío
                            if ":" in challenge_text:
                                action = challenge_text.split(":")[1].strip().upper()
                            else:
                                action = "VALIDANDO..."
                            self.lbl_status.configure(
                                text=action,
                                text_color="#FFD54F",
                            )
                    else:
                        self.lbl_status.configure(
                            text="POSICIONA TU ROSTRO",
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
        self._reset_liveness_state()
        self.lbl_status.configure(text="INICIANDO CÁMARA...", text_color="#FFFFFF")
        self.lbl_attempts.configure(text="")
        self.success_frame.place_forget()
        self.btn_back.place(x=80, rely=0.94, anchor="center")

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
        if self._return_job:
            self.after_cancel(self._return_job)
            self._return_job = None
        logger.info("Camera capture detenido")

    def on_face_match(self, user_data: dict) -> None:
        """Muestra el overlay verde de éxito con los datos del usuario."""
        self._success_shown = True
        self._user_data = user_data

        self.lbl_status.configure(text="✓ ACCESO CONCEDIDO", text_color="#A5D6A7")
        self.lbl_attempts.configure(text="")

        # Llenar datos en el overlay con el nuevo diseño
        locker_num = user_data.get("locker_numero", "—")
        self.lbl_success_locker.configure(
            text=str(locker_num)  # Solo el número
        )
        self.lbl_success_name.configure(text=user_data.get("nombre", "—"))
        self.lbl_success_matricula.configure(
            text=f"Matrícula  {user_data.get('matricula', '—')}"
        )
        self.lbl_success_fecha.configure(text=user_data.get("fecha", "—"))

        # Mostrar overlay verde (posicionado más abajo)
        self.success_frame.place(relx=0.5, rely=0.63, anchor="center")
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
            self.lbl_status.configure(text="✗ Acceso denegado", text_color="#EF9A9A")
            self.after(2500, self._go_standby)
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
        patterns = [
            ["left", "right", "closer"],
            ["right", "left", "closer"],
            ["closer", "away", "left"],
        ]
        steps = random.choice(patterns).copy()
        uses_dlib = bool(
            self.face_manager
            and getattr(self.face_manager.embedding_extractor, "uses_dlib", False)
        )
        if uses_dlib:
            steps.append("blink")
        return steps

    def _challenge_prompt(self) -> str:
        if not self._challenge_steps:
            return "Prueba de vida: espera…"
        current = self._challenge_steps[min(self._challenge_index, len(self._challenge_steps) - 1)]
        labels = {
            "left": "Prueba de vida: mueve tu cabeza a la izquierda",
            "right": "Prueba de vida: mueve tu cabeza a la derecha",
            "closer": "Prueba de vida: acércate un poco",
            "away": "Prueba de vida: aléjate un poco",
            "blink": "Prueba de vida: parpadea una vez",
        }
        return labels.get(current, "Prueba de vida en progreso")

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

        if len(self._liveness_face_history) < 4:
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

        movement_ok = (
            self._liveness_motion_score >= self.LIVENESS_MIN_MOTION
            or self._liveness_shift_score >= self.LIVENESS_MIN_BOX_SHIFT
        )
        texture_ok = texture >= 20.0

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

        candidates = self._load_active_face_encodings()
        if not candidates:
            logger.warning("No hay encodings activos en BD para autenticar")
            return None

        best_candidate = None
        best_distance = 999.0
        for candidate in candidates:
            stored_vec = candidate.get("vector_np")
            if stored_vec is None:
                continue
            distance = self.face_manager.embedding_extractor.compare_embeddings(
                probe_embedding.astype(np.float32, copy=False),
                stored_vec,
            )
            if distance < best_distance:
                best_distance = distance
                best_candidate = candidate

        if not best_candidate:
            return None

        threshold = self._threshold_for_model(best_candidate.get("modelo"))
        logger.info(
            "Auth facial: mejor candidato id=%s distancia=%.4f umbral=%.4f modelo=%s",
            best_candidate.get("idUsuario"),
            best_distance,
            threshold,
            best_candidate.get("modelo"),
        )

        if best_distance > threshold:
            self._register_access_attempt(best_candidate.get("idLockerAsignado"), permitted=False)
            return None

        self._register_access_attempt(best_candidate.get("idLockerAsignado"), permitted=True)
        full_name = " ".join(
            p for p in [
                best_candidate.get("nombre"),
                best_candidate.get("apPaterno"),
                best_candidate.get("apMaterno"),
            ] if p
        ).strip()

        return {
            "nombre": full_name or "Usuario",
            "matricula": best_candidate.get("matricula") or "—",
            "locker_numero": best_candidate.get("idLocker") or "Sin asignar",
            "fecha": datetime.now().strftime("%d/%m/%Y  %H:%M"),
        }

    def _threshold_for_model(self, model_name: Optional[str]) -> float:
        default_threshold = float(FACE_RECOGNITION_CONFIG.get("distance_threshold", 0.6))
        if (model_name or "").startswith("fallback"):
            return 0.95
        return default_threshold

    def _load_active_face_encodings(self) -> list[dict]:
        rows = fetch_all(
            """
            SELECT
                e.idUsuario,
                e.vector,
                e.dimension,
                e.vectorDtype,
                e.modelo,
                u.nombre,
                u.apPaterno,
                u.apMaterno,
                u.matricula,
                a.idLockerAsignado,
                l.idLocker
            FROM encoding e
            JOIN usuarios u
                ON u.idUsuario = e.idUsuario
            LEFT JOIN asignacion_locker a
                ON a.idUsuario = u.idUsuario AND a.estado = 'activo'
            LEFT JOIN lockers l
                ON l.idLocker = a.idLocker
            WHERE e.estado = 'activo'
              AND u.estado = 'activo'
            """
        )

        parsed: list[dict] = []
        for row in rows:
            raw = row.get("vector")
            dim = int(row.get("dimension") or 128)
            dtype_name = (row.get("vectorDtype") or "float32").strip().lower()
            dtype = np.float64 if dtype_name == "float64" else np.float32
            if raw is None:
                continue

            vector_np = np.frombuffer(raw, dtype=dtype)
            if vector_np.size != dim:
                logger.warning(
                    "Encoding inválido usuario=%s esperado=%s real=%s",
                    row.get("idUsuario"),
                    dim,
                    vector_np.size,
                )
                continue

            if dtype != np.float32:
                vector_np = vector_np.astype(np.float32)

            row["vector_np"] = vector_np
            parsed.append(row)

        return parsed

    def _register_access_attempt(self, locker_assignment_id: Optional[int], permitted: bool) -> None:
        try:
            now = datetime.now()
            expires_at = now + (timedelta(minutes=5) if permitted else timedelta(minutes=1))
            execute(
                """
                INSERT INTO historial_accesos
                    (idLockerAsignado, accesoPermitido, motivo, fechaExpiracion)
                VALUES (?, ?, ?, ?)
                """,
                (
                    locker_assignment_id,
                    "si" if permitted else "no",
                    "facial",
                    expires_at.strftime("%Y-%m-%dT%H:%M:%S"),
                ),
            )
        except Exception as e:
            logger.warning(f"No se pudo registrar historial de acceso: {e}")
