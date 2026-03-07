"""
StandbyScreen – pantalla de espera del locker físico (800×480 px).

Es la primera pantalla visible. Muestra el logo/nombre del sistema
y una instrucción para acercarse a la cámara.
Cuando se detecta actividad (o el botón de prueba en desarrollo)
navega a ScanningScreen vía controller.show_frame().
"""

import customtkinter as ctk


class StandbyScreen(ctk.CTkFrame):
    """
    Pantalla de espera (modo kiosk).

    Parámetros
    ----------
    parent     : widget padre (la ventana raíz LockerApp)
    controller : LockerApp – expone show_frame() para navegar
    """

    BG_COLOR    = "#0D1117"   # fondo oscuro
    ACCENT      = "#2563EB"   # azul institucional
    TEXT_COLOR  = "#F0F6FC"

    def __init__(self, parent: ctk.CTk, controller):
        super().__init__(parent, fg_color=self.BG_COLOR, corner_radius=0)
        self.controller = controller
        self._build_ui()

    # ── Construcción de widgets ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.grid_rowconfigure((0, 1, 2, 3, 4), weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Logo / ícono superior ─────────────────────────────────────────────
        lbl_icon = ctk.CTkLabel(
            self,
            text="🔒",
            font=ctk.CTkFont(size=72),
            text_color=self.ACCENT,
        )
        lbl_icon.grid(row=0, column=0, pady=(40, 0))

        # ── Nombre del sistema ────────────────────────────────────────────────
        lbl_title = ctk.CTkLabel(
            self,
            text="Smart Locker",
            font=ctk.CTkFont(size=36, weight="bold"),
            text_color=self.TEXT_COLOR,
        )
        lbl_title.grid(row=1, column=0)

        # ── Instrucción principal ─────────────────────────────────────────────
        lbl_instruction = ctk.CTkLabel(
            self,
            text="Acerca tu rostro a la cámara",
            font=ctk.CTkFont(size=22),
            text_color="#8B949E",
        )
        lbl_instruction.grid(row=2, column=0)

        # ── Indicador animado (placeholder) ──────────────────────────────────
        self.lbl_dot = ctk.CTkLabel(
            self,
            text="● ● ●",
            font=ctk.CTkFont(size=18),
            text_color=self.ACCENT,
        )
        self.lbl_dot.grid(row=3, column=0)
        self._animate_dots()

        # ── Botón DEV: ir a scanning (solo durante desarrollo) ────────────────
        btn_dev = ctk.CTkButton(
            self,
            text="[DEV] Iniciar escaneo",
            font=ctk.CTkFont(size=14),
            fg_color="#21262D",
            hover_color="#30363D",
            text_color="#8B949E",
            width=200, height=32,
            command=self._go_scanning,
        )
        btn_dev.grid(row=4, column=0, pady=(0, 20))

    # ── Lógica ────────────────────────────────────────────────────────────────

    def on_show(self) -> None:
        """Llamado por LockerApp.show_frame() al traer esta pantalla al frente."""
        self._animate_dots()

    def _go_scanning(self) -> None:
        from ui.locker_screen.scanning_screen import ScanningScreen
        self.controller.show_frame(ScanningScreen)

    def _animate_dots(self, step: int = 0) -> None:
        """Alterna el brillo del indicador ● ● ● de forma cíclica."""
        patterns = ["●  ○  ○", "○  ●  ○", "○  ○  ●", "○  ●  ○"]
        self.lbl_dot.configure(text=patterns[step % len(patterns)])
        self._anim_job = self.after(500, self._animate_dots, step + 1)
