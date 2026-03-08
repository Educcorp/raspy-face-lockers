"""
ScanningScreen – pantalla de escaneo facial (800×480 px).

Muestra el feed de la cámara y el feedback visual mientras
cv2.dnn procesa el rostro. Cuando el reconocimiento termina:
  - Éxito  → controller.show_user(user_data)
  - Fallo  → mostrar mensaje + volver a StandbyScreen tras 3 intentos
"""

import customtkinter as ctk
import threading
import cv2
import numpy as np
from PIL import Image, ImageDraw
import tkinter
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ScanningScreen(ctk.CTkFrame):
    """
    Pantalla activa durante el reconocimiento facial.

    Parámetros
    ----------
    parent     : widget padre (LockerApp)
    controller : LockerApp – expone show_frame() / show_user()
    """

    BG_COLOR   = "#0c112f"
    ACCENT     = "#33a8a3"
    SUCCESS    = "#22C55E"
    WARNING    = "#F59E0B"
    DANGER     = "#EF4444"
    TEXT_COLOR = "#c7cfd5"

    MAX_ATTEMPTS = 3

    def __init__(self, parent: ctk.CTk, controller) -> None:
        super().__init__(parent, fg_color=self.BG_COLOR, corner_radius=0)
        self.controller = controller
        self._attempts  = 0
        
        # Variables de captura de cámara
        self._camera_thread: Optional[threading.Thread] = None
        self._camera_running = False
        self._camera_frame: Optional[np.ndarray] = None
        self._detected_faces = []
        self._photo_image: Optional[tkinter.PhotoImage] = None
        
        # Inicializar módulo de reconocimiento facial
        try:
            from core.face_recognition import get_face_recognition_manager
            self.face_manager = get_face_recognition_manager()
        except Exception as e:
            logger.error(f"Error importando FaceRecognitionManager: {e}")
            self.face_manager = None
        
        self._build_ui()

    # ── Construcción de UI ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Layout vertical: título / cámara / estado / intentos / botones DEV
        self.grid_rowconfigure((0, 1, 2, 3, 4), weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Título ────────────────────────────────────────────────────────────
        lbl_title = ctk.CTkLabel(
            self,
            text="Reconocimiento facial",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=self.TEXT_COLOR,
        )
        lbl_title.grid(row=0, column=0, pady=(30, 0))

        # ── Área de cámara — mostrará el feed de vídeo ──────────────────────
        self.camera_frame = ctk.CTkFrame(
            self,
            width=380, height=380,
            fg_color="#05403F",
            border_color=self.ACCENT,
            border_width=2,
            corner_radius=12,
        )
        self.camera_frame.grid(row=1, column=0, padx=20, pady=10)
        self.camera_frame.grid_propagate(False)

        # Label para mostrar video feed
        self.lbl_camera = ctk.CTkLabel(
            self.camera_frame,
            text="📷\nIniciando cámara…",
            font=ctk.CTkFont(size=22),
            text_color="#6b7a8a",
            fg_color="transparent",
        )
        self.lbl_camera.place(relx=0.5, rely=0.5, anchor="center")

        # ── Estado / feedback ─────────────────────────────────────────────────
        self.lbl_status = ctk.CTkLabel(
            self,
            text="Posiciona tu rostro en el recuadro…",
            font=ctk.CTkFont(size=18),
            text_color="#6b7a8a",
        )
        self.lbl_status.grid(row=2, column=0, pady=(0, 4))

        # ── Contador de intentos ──────────────────────────────────────────────
        self.lbl_attempts = ctk.CTkLabel(
            self,
            text=f"Intentos: 0 / {self.MAX_ATTEMPTS}",
            font=ctk.CTkFont(size=15),
            text_color="#6b7a8a",
        )
        self.lbl_attempts.grid(row=3, column=0)

        # ── Botones DEV (apilados verticalmente) ──────────────────────────────
        dev_frame = ctk.CTkFrame(self, fg_color="transparent")
        dev_frame.grid(row=4, column=0, pady=(0, 24))

        btn_back = ctk.CTkButton(
            dev_frame,
            text="[DEV] ← Volver",
            font=ctk.CTkFont(size=14),
            fg_color="#05403F",
            hover_color="#272c4a",
            text_color="#6b7a8a",
            width=200, height=36,
            command=self._go_standby,
        )
        btn_back.grid(row=0, column=0, padx=10)

        btn_success = ctk.CTkButton(
            dev_frame,
            text="[DEV] Simular éxito",
            font=ctk.CTkFont(size=14),
            fg_color="#05403F",
            hover_color="#272c4a",
            text_color=self.SUCCESS,
            width=200, height=36,
            command=self._dev_simulate_success,
        )
        btn_success.grid(row=0, column=1, padx=10)

    # ── Captura de video en background ────────────────────────────────────────

    def _camera_loop(self) -> None:
        """Thread worker que captura frames y detecta rostros."""
        import time
        
        if not self.face_manager:
            logger.error("FaceManager no inicializado")
            return

        if not self.face_manager.initialized:
            if not self.face_manager.initialize():
                logger.error("No se pudo inicializar cámara")
                return

        logger.info("Camera loop iniciado")
        frame_count = 0
        last_status_update = 0

        try:
            while self._camera_running:
                # Capturar frame y detectar rostros
                frame, faces = self.face_manager.detect_faces_in_frame()

                if frame is None:
                    time.sleep(0.05)  # Pequeña pausa si no hay frame
                    continue

                frame_count += 1

                # Guardar frame y rostros detectados
                self._camera_frame = frame
                self._detected_faces = faces

                # Convertir a PIL Image para mostrar
                try:
                    self._update_camera_display(frame, faces)
                    logger.debug(f"Frame actualizado #{frame_count}, rostros: {len(faces)}")
                except Exception as e:
                    logger.error(f"Error actualizando display: {e}")

                # Pequeña pausa para no saturar la UI (~15 FPS)
                time.sleep(0.066)

                # Log de progreso cada 30 frames (~2 segundos)
                if frame_count % 30 == 0:
                    logger.info(f"Camera loop activo: {frame_count} frames capturados, {len(faces)} rostros últimos")

        except Exception as e:
            logger.error(f"Error en camera loop: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            if self.face_manager:
                try:
                    self.face_manager.release()
                except:
                    pass
            logger.info(f"Camera loop finalizado. Total frames: {frame_count}")

    def _update_camera_display(self, frame: np.ndarray, faces: list) -> None:
        """Actualiza la pantalla con el frame actual y dibuja caras detectadas."""
        try:
            # Convertir BGR → RGB para PIL
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Redimensionar a 380×380 (tamaño del camera_frame)
            frame_resized = cv2.resize(frame_rgb, (380, 380))

            # Dibujar rectángulos alrededor de rostros detectados
            pil_image = Image.fromarray(frame_resized)
            draw = ImageDraw.Draw(pil_image)

            # Escala de coordenadas (del frame original al redimensionado)
            scale_x = 380 / frame_rgb.shape[1]
            scale_y = 380 / frame_rgb.shape[0]

            for face in faces:
                x, y, w, h = face["box"]
                # Redimensionar coordenadas
                x1 = int(x * scale_x)
                y1 = int(y * scale_y)
                x2 = int((x + w) * scale_x)
                y2 = int((y + h) * scale_y)

                # Dibujar rectángulo verde
                draw.rectangle(
                    [(x1, y1), (x2, y2)],
                    outline=(34, 197, 94),  # GREEN #22C55E
                    width=3,
                )

            # Convertir PIL Image a tkinter PhotoImage usando formato PPM
            # Nota: Usar archivo temporal porque carga es más rápida
            import tempfile
            import os
            
            ppm_path = "/tmp/locker_frame.ppm"
            try:
                pil_image.save(ppm_path, "PPM")
                
                # Crear nuevo PhotoImage
                new_photo = tkinter.PhotoImage(file=ppm_path)
                
                # Guardar referencia ANTES de actualizar (critical!)
                self._photo_image = new_photo
                
                # Actualizar label en main thread
                self.after(0, self._set_camera_image)
            except Exception as e:
                logger.warning(f"Error creando PhotoImage: {e}")

        except Exception as e:
            logger.error(f"Error actualizando display: {e}")

    def _set_camera_image(self) -> None:
        """Actualiza la imagen en el label (debe llamarse desde main thread)."""
        try:
            if self._photo_image is not None:
                self.lbl_camera.configure(image=self._photo_image, text="")
                self.lbl_camera.image = self._photo_image  # Mantener referencia
        except Exception as e:
            logger.error(f"Error mostrando imagen: {e}")

    # ── API pública ───────────────────────────────────────────────────────────

    def on_show(self) -> None:
        """Inicia captura de vídeo cuando la pantalla se vuelve activa."""
        self._attempts = 0
        self._update_status("Iniciando cámara…", color="#6b7a8a")
        self.lbl_attempts.configure(text=f"Intentos: 0 / {self.MAX_ATTEMPTS}")

        # Iniciar thread de captura de cámara
        if not self._camera_running:
            logger.info("Iniciando ScanningScreen - preparando captura de video")
            self._camera_running = True
            self._camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
            self._camera_thread.start()
            logger.info("Camera capture thread iniciado exitosamente")
            
            # Actualizar status después de 1 segundo (cuando ya debe estar capturando)
            self.after(1000, lambda: self._update_status("Posiciona tu rostro en el recuadro…", color="#6b7a8a"))

    def on_hide(self) -> None:
        """Detiene captura de vídeo cuando se sale de la pantalla."""
        self._camera_running = False
        if self._camera_thread:
            self._camera_thread.join(timeout=2.0)
        logger.info("Camera capture detenido")

    def on_face_match(self, user_data: dict) -> None:
        """Llamado por el motor de reconocimiento al obtener un match."""
        self._update_status("✓ Acceso concedido", color=self.SUCCESS)
        self.after(800, lambda: self.controller.show_user(user_data))

    def on_face_no_match(self) -> None:
        """Llamado por el motor de reconocimiento cuando no hay match."""
        self._attempts += 1
        self.lbl_attempts.configure(
            text=f"Intentos: {self._attempts} / {self.MAX_ATTEMPTS}"
        )
        if self._attempts >= self.MAX_ATTEMPTS:
            self._update_status("✗ Acceso denegado", color=self.DANGER)
            self.after(2500, self._go_standby)
        else:
            self._update_status(
                f"Rostro no reconocido. Intento {self._attempts}/{self.MAX_ATTEMPTS}",
                color=self.WARNING,
            )

    # ── Métodos internos ──────────────────────────────────────────────────────

    def _update_status(self, text: str, color: str = "#6b7a8a") -> None:
        self.lbl_status.configure(text=text, text_color=color)

    def _go_standby(self) -> None:
        from ui.locker_screen.standby_screen import StandbyScreen
        self.controller.show_frame(StandbyScreen)

    def _dev_simulate_success(self) -> None:
        """Solo para desarrollo: simula un acceso exitoso."""
        dummy_user = {
            "nombre":        "Juan Pérez López",
            "locker_numero": 3,
            "fecha":         "07/03/2026  14:32",
        }
        self.on_face_match(dummy_user)
