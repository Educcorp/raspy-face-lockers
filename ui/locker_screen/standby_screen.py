"""
StandbyScreen – pantalla de espera del locker físico (800×480 px).

Es la primera pantalla visible. Muestra el logo/nombre del sistema
y una instrucción para acercarse a la cámara.
Cuando se detecta actividad (o el botón de prueba en desarrollo)
navega a ScanningScreen vía controller.show_frame().
"""

import customtkinter as ctk
import threading
import logging
import os
from PIL import Image

logger = logging.getLogger(__name__)


class StandbyScreen(ctk.CTkFrame):
    """
    Pantalla de espera (modo kiosk).

    Parámetros
    ----------
    parent     : widget padre (la ventana raíz LockerApp)
    controller : LockerApp – expone show_frame() para navegar
    """

    BG_COLOR    = "#5B8C5A"   # fondo verde solicitado
    PRIMARY     = "#5B8C5A"   # verde pizarrón suave
    SECONDARY   = "#E6F4E6"
    TEXT_COLOR  = "#FFFFFF"
    MUTED       = "#F2FBF2"

    def __init__(self, parent: ctk.CTk, controller):
        super().__init__(parent, fg_color=self.BG_COLOR, corner_radius=0)
        self.controller = controller
        self._monitor_thread: threading.Thread | None = None
        self._monitor_running = False
        self._transitioning = False

        try:
            from core.face_recognition import get_face_recognition_manager
            self.face_manager = get_face_recognition_manager()
        except Exception as e:
            logger.error(f"No se pudo inicializar face manager en standby: {e}")
            self.face_manager = None

        self._build_ui()

    # ── Construcción de widgets ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        # 6 filas distribuidas verticalmente en 480×800
        self.grid_rowconfigure((0, 1, 2, 3, 4, 5), weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Espacio superior ──────────────────────────────────────────────────
        ctk.CTkLabel(self, text="", fg_color="transparent").grid(row=0, column=0)

        # ── Logo / ícono ──────────────────────────────────────────────────────
        logo_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "assets", "icons", "smartlocker_logo.png"
        )
        self._logo_image = None
        try:
            if os.path.exists(logo_path):
                logo_img = Image.open(logo_path)
                self._logo_image = ctk.CTkImage(
                    light_image=logo_img,
                    dark_image=logo_img,
                    size=(320, 110),
                )
        except Exception as e:
            logger.warning(f"No se pudo cargar logo SmartLocker: {e}")

        lbl_logo = ctk.CTkLabel(
            self,
            text="",
            image=self._logo_image,
            fg_color="transparent",
        )
        lbl_logo.grid(row=1, column=0, rowspan=2)

        # ── Instrucción principal ─────────────────────────────────────────────
        lbl_instruction = ctk.CTkLabel(
            self,
            text="Acerca tu rostro a la cámara",
            font=ctk.CTkFont(size=22),
            text_color=self.MUTED,
            fg_color="transparent",
        )
        lbl_instruction.grid(row=3, column=0)

        # ── Indicador animado ─────────────────────────────────────────────────
        self.lbl_dot = ctk.CTkLabel(
            self,
            text="● ● ●",
            font=ctk.CTkFont(size=20),
            text_color=self.SECONDARY,
            fg_color="transparent",
        )
        self.lbl_dot.grid(row=4, column=0)
        self._animate_dots()

        # ── Botón Iniciar escaneo ─────────────────────────────────────────
        btn_start = ctk.CTkButton(
            self,
            text="Iniciar escaneo",
            font=ctk.CTkFont(size=19, weight="bold"),
            fg_color="transparent",
            bg_color="transparent",
            hover_color="#FFFFFF22",
            text_color="#FFFFFF",
            border_width=2,
            border_color="#FFFFFF",
            width=300, height=56,
            corner_radius=16,
            command=self._go_scanning,
        )
        btn_start.grid(row=5, column=0, pady=(0, 30))

    # ── Lógica ────────────────────────────────────────────────────────────────

    def on_show(self) -> None:
        """Llamado por LockerApp.show_frame() al traer esta pantalla al frente."""
        self._transitioning = False
        self._animate_dots()
        self._start_face_monitor()

    def on_hide(self) -> None:
        self._stop_face_monitor()

    def _start_face_monitor(self) -> None:
        if self._monitor_running or self.face_manager is None:
            return

        self._monitor_running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _stop_face_monitor(self) -> None:
        self._monitor_running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
            self._monitor_thread = None

    def _monitor_loop(self) -> None:
        import time

        if self.face_manager is None:
            return

        try:
            if not self.face_manager.initialized:
                self.face_manager.initialize()

            stable_hits = 0
            while self._monitor_running and not self._transitioning:
                frame, faces = self.face_manager.detect_faces_in_frame()
                if frame is None:
                    time.sleep(0.15)
                    continue

                if faces:
                    stable_hits += 1
                else:
                    stable_hits = 0

                if stable_hits >= 3:
                    self._transitioning = True
                    self.after(0, self._go_scanning)
                    break

                time.sleep(0.12)
        except Exception as e:
            logger.warning(f"Monitor de rostro en standby falló: {e}")
        finally:
            # Si vamos a Scanning, preservamos la cámara para evitar
            # carrera de liberar/reinicializar que deja libcamera en
            # estado inconsistente (Configured vs Available).
            if self._transitioning:
                logger.info("Transición a escaneo: preservando cámara abierta")
                return
            self._release_face_manager()

    def _release_face_manager(self) -> None:
        try:
            if self.face_manager and self.face_manager.initialized:
                self.face_manager.release()
        except Exception as e:
            logger.debug(f"No se pudo liberar face_manager en standby: {e}")

    def _go_scanning(self) -> None:
        self._transitioning = True
        from ui.locker_screen.scanning_screen import ScanningScreen
        self.controller.show_frame(ScanningScreen)

    def _animate_dots(self, step: int = 0) -> None:
        """Alterna el brillo del indicador ● ● ● de forma cíclica."""
        patterns = ["●  ○  ○", "○  ●  ○", "○  ○  ●", "○  ●  ○"]
        self.lbl_dot.configure(text=patterns[step % len(patterns)])
        self._anim_job = self.after(500, self._animate_dots, step + 1)
