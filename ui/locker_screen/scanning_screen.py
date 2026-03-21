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

from services.recognition_service import recognize_user_from_face
from services.locker_service import build_access_payload, register_access_attempt

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
    RECOGNITION_INTERVAL_FRAMES = 12

    # Dimensiones de la ventana
    WIN_W = 480
    WIN_H = 800

    def __init__(self, parent: ctk.CTk, controller) -> None:
        super().__init__(parent, fg_color=self.BG_COLOR, corner_radius=0)
        self.controller = controller
        self._attempts  = 0
        self._face_detected = False
        self._success_shown = False
        self._recognition_in_flight = False
        self._return_job = None
        self._deny_job = None

        # Variables de captura de cámara
        self._camera_thread: Optional[threading.Thread] = None
        self._camera_running = False
        self._camera_frame: Optional[np.ndarray] = None
        self._detected_faces = []
        self._photo_image: Optional[tkinter.PhotoImage] = None

        # Datos del usuario reconocido
        self._user_data: Optional[dict] = None
        self._last_recognition_frame = 0

        # Inicializar módulo de reconocimiento facial
        try:
            from core.face_recognition import get_face_recognition_manager
            self.face_manager = get_face_recognition_manager()
        except Exception as e:
            logger.error(f"Error importando FaceRecognitionManager: {e}")
            self.face_manager = None

        # Pre-generar la máscara de silueta
        self._silhouette_mask = self._create_silhouette_mask()

        self._build_ui()

    # ── Crear silueta de persona ──────────────────────────────────────────────

    def _create_silhouette_mask(self) -> Image.Image:
        """Crea una máscara PNG con la silueta de cabeza/hombros recortada."""
        mask = Image.new("RGBA", (self.WIN_W, self.WIN_H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(mask)

        # Fondo semitransparente oscuro
        draw.rectangle([(0, 0), (self.WIN_W, self.WIN_H)], fill=(0, 0, 0, 100))

        cx, cy = self.WIN_W // 2, self.WIN_H // 2 - 60

        # Recortar zona de la cabeza (elipse)
        head_rx, head_ry = 95, 120
        head_box = [cx - head_rx, cy - head_ry - 30, cx + head_rx, cy + head_ry - 30]
        draw.ellipse(head_box, fill=(0, 0, 0, 0))

        # Recortar zona cuello + hombros (elipse ancha)
        body_cy = cy + head_ry + 20
        body_rx, body_ry = 160, 100
        body_box = [cx - body_rx, body_cy - 10, cx + body_rx, body_cy + body_ry + 40]
        draw.ellipse(body_box, fill=(0, 0, 0, 0))

        return mask

    def _draw_silhouette_outline(self, draw: ImageDraw.Draw, color_rgba: tuple) -> None:
        """Dibuja el contorno de la silueta (cabeza + hombros) con el color dado."""
        cx, cy = self.WIN_W // 2, self.WIN_H // 2 - 60
        color_rgb = color_rgba[:3]

        head_rx, head_ry = 95, 120
        head_box = [cx - head_rx, cy - head_ry - 30, cx + head_rx, cy + head_ry - 30]
        draw.ellipse(head_box, outline=color_rgb, width=3)

        body_cy = cy + head_ry + 20
        body_rx, body_ry = 160, 100
        body_box = [cx - body_rx, body_cy - 10, cx + body_rx, body_cy + body_ry + 40]
        draw.ellipse(body_box, outline=color_rgb, width=3)

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
            text="Posiciona tu rostro en la silueta",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=self.TEXT_COLOR,
            fg_color="#2A2A3E",
            corner_radius=16,
            height=36,
            width=360,
        )
        self.lbl_status.place(relx=0.5, y=30, anchor="n")

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
            font=ctk.CTkFont(size=28, weight="bold"),
            fg_color="#3A3A50",
            hover_color="#4A4A60",
            text_color="#FFFFFF",
            width=56, height=56,
            corner_radius=28,
            command=self._go_standby,
        )
        self.btn_back.place(x=80, rely=0.94, anchor="center")

        # ── Overlay de éxito (oculto por defecto) ────────────────────────────
        self.success_frame = ctk.CTkFrame(
            self,
            fg_color=self.SUCCESS,
            corner_radius=20,
            width=420,
            height=260,
        )
        # No se muestra aún — se coloca con .place() al detectar éxito

        # Contenido del overlay de éxito
        self.lbl_success_icon = ctk.CTkLabel(
            self.success_frame,
            text="✓",
            font=ctk.CTkFont(size=52, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
        )
        self.lbl_success_icon.pack(pady=(15, 2))

        self.lbl_success_title = ctk.CTkLabel(
            self.success_frame,
            text="Escaneo exitoso",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
        )
        self.lbl_success_title.pack(pady=(0, 4))

        self.lbl_success_name = ctk.CTkLabel(
            self.success_frame,
            text="—",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
        )
        self.lbl_success_name.pack(pady=(0, 2))

        self.lbl_success_locker = ctk.CTkLabel(
            self.success_frame,
            text="Casillero —",
            font=ctk.CTkFont(size=16),
            text_color="#E8F5E9",
            fg_color="transparent",
        )
        self.lbl_success_locker.pack(pady=(0, 2))

        self.lbl_success_fecha = ctk.CTkLabel(
            self.success_frame,
            text="—",
            font=ctk.CTkFont(size=14),
            text_color="#C8E6C9",
            fg_color="transparent",
        )
        self.lbl_success_fecha.pack(pady=(0, 2))

        self.lbl_countdown = ctk.CTkLabel(
            self.success_frame,
            text="",
            font=ctk.CTkFont(size=13),
            text_color="#A5D6A7",
            fg_color="transparent",
        )
        self.lbl_countdown.pack(pady=(2, 8))

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
            if not self.face_manager.initialize():
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

                if (
                    not self._success_shown
                    and not self._recognition_in_flight
                    and self._face_detected
                    and (frame_count - self._last_recognition_frame) >= self.RECOGNITION_INTERVAL_FRAMES
                ):
                    self._last_recognition_frame = frame_count
                    self._recognition_in_flight = True
                    try:
                        face_box = faces[0].get("box")
                        logger.info(f"[RECONOCIMIENTO] Intento #{self._attempts + 1}, box={face_box}")

                        # Generar embedding HOG del frame actual
                        embedding = self.face_manager.get_embedding(frame, face_box)
                        if embedding is None:
                            logger.warning("[RECONOCIMIENTO] Embedding None — sin extracción")
                            self._recognition_in_flight = False
                            self.after(0, self.on_face_no_match)
                        else:
                            logger.info(f"[RECONOCIMIENTO] Embedding OK shape={embedding.shape} norm={float(embedding @ embedding):.3f}")

                            # Buscar en base de datos
                            from services.recognition_service import find_best_user_match
                            match = find_best_user_match(embedding)
                            logger.info(f"[RECONOCIMIENTO] match={match}")

                            if match:
                                payload = build_access_payload(match)
                                payload["fecha"] = datetime.now().strftime("%d/%m/%Y  %H:%M")
                                logger.info(f"[RECONOCIMIENTO] ✓ Acceso: {payload}")
                                self._success_shown = True
                                self._recognition_in_flight = False
                                self.after(0, self.on_face_match, payload)
                            else:
                                logger.info("[RECONOCIMIENTO] Sin coincidencia en DB")
                                register_access_attempt(None, False, "rostro no reconocido")
                                self._recognition_in_flight = False
                                self.after(0, self.on_face_no_match)

                    except Exception as recog_error:
                        logger.error(f"[RECONOCIMIENTO] Excepción: {recog_error}", exc_info=True)
                        self._recognition_in_flight = False
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
        """Dibuja el frame de cámara a pantalla completa con silueta superpuesta."""
        try:
            # Picamera2 "RGB888" retorna BGR en memoria — convertir a RGB para PIL
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Redimensionar manteniendo aspect ratio (no estirar)
            h, w = frame_rgb.shape[:2]
            scale = min(self.WIN_W / w, self.WIN_H / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            # Redimensionar
            frame_resized = cv2.resize(frame_rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            # Crear canvas con fondo negro y centrar la imagen
            canvas = np.zeros((self.WIN_H, self.WIN_W, 3), dtype=np.uint8)
            y_offset = (self.WIN_H - new_h) // 2
            x_offset = (self.WIN_W - new_w) // 2
            canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = frame_resized
            
            # Convertir a PIL directamente (sin conversión de canales)
            pil_image = Image.fromarray(canvas, mode="RGB").convert("RGBA")

            # Superponer la máscara de silueta semitransparente
            pil_image = Image.alpha_composite(pil_image, self._silhouette_mask)

            # Dibujar contorno de silueta: rojo si no hay rostro, verde si sí
            draw = ImageDraw.Draw(pil_image)
            if len(faces) > 0:
                self._draw_silhouette_outline(draw, self.SILHOUETTE_FACE_OK)
            else:
                self._draw_silhouette_outline(draw, self.SILHOUETTE_NO_FACE)

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

                # Actualizar texto del status según detección
                if not self._success_shown:
                    if self._face_detected:
                        self.lbl_status.configure(
                            text="Rostro detectado — analizando…",
                            text_color="#A5D6A7",
                        )
                    else:
                        self.lbl_status.configure(
                            text="Posiciona tu rostro en la silueta",
                            text_color="#FFFFFF",
                        )
        except Exception as e:
            logger.error(f"Error mostrando imagen: {e}")

    # ── API pública ───────────────────────────────────────────────────────────

    def on_show(self, **_kwargs) -> None:
        """Inicia captura de vídeo cuando la pantalla se activa."""
        self._attempts = 0
        self._success_shown = False
        self._recognition_in_flight = False
        self._user_data = None
        self._last_recognition_frame = 0
        self.lbl_status.configure(text="Iniciando cámara…", text_color="#FFFFFF")
        self.lbl_attempts.configure(text="")
        self.success_frame.place_forget()
        self.btn_back.place(x=80, rely=0.94, anchor="center")

        if self._deny_job:
            self.after_cancel(self._deny_job)
            self._deny_job = None

        if not self._camera_running:
            self._camera_running = True
            self._camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
            self._camera_thread.start()
            self.after(1000, lambda: self.lbl_status.configure(
                text="Posiciona tu rostro en la silueta", text_color="#FFFFFF"
            ))

    def on_hide(self, **_kwargs) -> None:
        """Detiene captura de vídeo al salir de la pantalla."""
        self._camera_running = False
        if self._camera_thread:
            self._camera_thread.join(timeout=2.0)
        if self._return_job:
            self.after_cancel(self._return_job)
            self._return_job = None
        if self._deny_job:
            self.after_cancel(self._deny_job)
            self._deny_job = None
        logger.info("Camera capture detenido")

    def on_face_match(self, user_data: dict) -> None:
        """Navega a UserDisplayScreen pasando los datos reales del usuario."""
        self._success_shown = True
        self._user_data = user_data

        if self._deny_job:
            self.after_cancel(self._deny_job)
            self._deny_job = None

        from ui.locker_screen.user_display import UserDisplayScreen
        # Pasamos user_data como kwarg → on_show() lo recibe y llama load_user()
        self.controller.show_frame(UserDisplayScreen, user_data=user_data)

        logger.info(
            "Acceso concedido: user_id=%s, locker=%s",
            user_data.get("user_id"),
            user_data.get("locker_numero"),
        )

    def on_face_no_match(self) -> None:
        """Llamado cuando no hay match."""
        self._recognition_in_flight = False

        if self._success_shown:
            return

        self._attempts += 1
        self.lbl_attempts.configure(
            text=f"Intentos: {self._attempts} / {self.MAX_ATTEMPTS}"
        )
        if self._attempts >= self.MAX_ATTEMPTS:
            self.lbl_status.configure(text="✗ Acceso denegado", text_color="#EF9A9A")
            self._deny_job = self.after(2500, self._go_standby)
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

        self.lbl_countdown.configure(text=f"Redirigiendo al inicio en {seconds} s…")
        self._return_job = self.after(1000, self._start_countdown, seconds - 1)

    # ── Métodos internos ──────────────────────────────────────────────────────

    def _go_standby(self) -> None:
        self._deny_job = None
        from ui.locker_screen.standby_screen import StandbyScreen
        self.controller.show_frame(StandbyScreen)
