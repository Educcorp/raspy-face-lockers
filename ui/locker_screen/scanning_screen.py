"""
ScanningScreen – pantalla de escaneo facial (800×480 px).

Muestra el feed de la cámara y el feedback visual mientras
cv2.dnn procesa el rostro. Cuando el reconocimiento termina:
  - Éxito  → controller.show_user(user_data)
  - Fallo  → mostrar mensaje + volver a StandbyScreen tras 3 intentos
"""

import customtkinter as ctk

class ScanningScreen(ctk.CTkFrame):
    """
    Pantalla activa durante el reconocimiento facial.

    Parámetros
    ----------
    parent     : widget padre (LockerApp)
    controller : LockerApp – expone show_frame() / show_user()
    """

    BG_COLOR   = "#0D1117"
    ACCENT     = "#2563EB"
    SUCCESS    = "#22C55E"
    WARNING    = "#F59E0B"
    DANGER     = "#EF4444"
    TEXT_COLOR = "#F0F6FC"

    MAX_ATTEMPTS = 3

    def __init__(self, parent: ctk.CTk, controller) -> None:
        super().__init__(parent, fg_color=self.BG_COLOR, corner_radius=0)
        self.controller = controller
        self._attempts  = 0
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

        # ── Área de cámara — cuadrada, ocupa buen espacio vertical ───────────
        self.camera_frame = ctk.CTkFrame(
            self,
            width=380, height=380,
            fg_color="#161B22",
            border_color=self.ACCENT,
            border_width=2,
            corner_radius=12,
        )
        self.camera_frame.grid(row=1, column=0, padx=20, pady=10)
        self.camera_frame.grid_propagate(False)

        self.lbl_camera_placeholder = ctk.CTkLabel(
            self.camera_frame,
            text="📷\nCámara activa",
            font=ctk.CTkFont(size=22),
            text_color="#8B949E",
        )
        self.lbl_camera_placeholder.place(relx=0.5, rely=0.5, anchor="center")

        # ── Estado / feedback ─────────────────────────────────────────────────
        self.lbl_status = ctk.CTkLabel(
            self,
            text="Posiciona tu rostro en el recuadro…",
            font=ctk.CTkFont(size=18),
            text_color="#8B949E",
        )
        self.lbl_status.grid(row=2, column=0, pady=(0, 4))

        # ── Contador de intentos ──────────────────────────────────────────────
        self.lbl_attempts = ctk.CTkLabel(
            self,
            text=f"Intentos: 0 / {self.MAX_ATTEMPTS}",
            font=ctk.CTkFont(size=15),
            text_color="#8B949E",
        )
        self.lbl_attempts.grid(row=3, column=0)

        # ── Botones DEV (apilados verticalmente) ──────────────────────────────
        dev_frame = ctk.CTkFrame(self, fg_color="transparent")
        dev_frame.grid(row=4, column=0, pady=(0, 24))

        btn_back = ctk.CTkButton(
            dev_frame,
            text="[DEV] ← Volver",
            font=ctk.CTkFont(size=14),
            fg_color="#21262D",
            hover_color="#30363D",
            text_color="#8B949E",
            width=200, height=36,
            command=self._go_standby,
        )
        btn_back.grid(row=0, column=0, padx=10)

        btn_success = ctk.CTkButton(
            dev_frame,
            text="[DEV] Simular éxito",
            font=ctk.CTkFont(size=14),
            fg_color="#21262D",
            hover_color="#30363D",
            text_color=self.SUCCESS,
            width=200, height=36,
            command=self._dev_simulate_success,
        )
        btn_success.grid(row=0, column=1, padx=10)

    # ── API pública (llamada desde core/face_recognition) ────────────────────

    def on_show(self) -> None:
        """Resetea el estado cada vez que esta pantalla se vuelve activa."""
        self._attempts = 0
        self._update_status("Posiciona tu rostro en el recuadro…", color="#8B949E")
        self.lbl_attempts.configure(text=f"Intentos: 0 / {self.MAX_ATTEMPTS}")

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

    def _update_status(self, text: str, color: str = "#8B949E") -> None:
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
