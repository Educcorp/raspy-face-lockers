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

    BG_COLOR    = "#F5F0EB"   # fondo crema claro escolar
    PRIMARY     = "#5B8C5A"   # verde pizarrón suave
    SECONDARY   = "#7BA7BC"   # azul cielo apagado
    TEXT_COLOR  = "#3D3D3D"   # texto oscuro legible
    MUTED       = "#8C8279"   # texto secundario cálido

    def __init__(self, parent: ctk.CTk, controller):
        super().__init__(parent, fg_color=self.BG_COLOR, corner_radius=0)
        self.controller = controller
        self._build_ui()

    # ── Construcción de widgets ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        # 6 filas distribuidas verticalmente en 480×800
        self.grid_rowconfigure((0, 1, 2, 3, 4, 5), weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Espacio superior ──────────────────────────────────────────────────
        ctk.CTkLabel(self, text="", fg_color="transparent").grid(row=0, column=0)

        # ── Logo / ícono ──────────────────────────────────────────────────────
        lbl_icon = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=96),
            text_color=self.PRIMARY,
            fg_color="transparent",
        )
        lbl_icon.grid(row=1, column=0)

        # ── Nombre del sistema ────────────────────────────────────────────────
        lbl_title = ctk.CTkLabel(
            self,
            text="Smart Locker",
            font=ctk.CTkFont(size=38, weight="bold"),
            text_color=self.TEXT_COLOR,
            fg_color="transparent",
        )
        lbl_title.grid(row=2, column=0)

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
            fg_color=self.PRIMARY,
            hover_color="#4A7A49",
            text_color="#FFFFFF",
            width=300, height=56,
            corner_radius=12,
            command=self._go_scanning,
        )
        btn_start.grid(row=5, column=0, pady=(0, 30))

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
