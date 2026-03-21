"""
StandbyScreen – pantalla de espera del locker físico (800×480 px).

Es la primera pantalla visible. Muestra el logo/nombre del sistema
y una instrucción de acercarse a la cámara.
Después de AUTO_DELAY segundos navega automáticamente a ScanningScreen.
Tocar cualquier parte de la pantalla también inicia el escaneo al instante.
"""

import customtkinter as ctk


class StandbyScreen(ctk.CTkFrame):
    """
    Pantalla de espera (modo kiosk). Sin botones manuales.

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

    AUTO_DELAY  = 3           # segundos antes de entrar a la cámara automáticamente

    def __init__(self, parent: ctk.CTk, controller):
        super().__init__(parent, fg_color=self.BG_COLOR, corner_radius=0)
        self.controller = controller
        self._anim_job  = None
        self._nav_job   = None
        self._countdown = self.AUTO_DELAY
        self._build_ui()

        # Tocar la pantalla arranca inmediatamente
        self.bind("<Button-1>", lambda _: self._go_scanning())
        for child in self.winfo_children():
            child.bind("<Button-1>", lambda _: self._go_scanning())

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
        lbl_icon.bind("<Button-1>", lambda _: self._go_scanning())

        # ── Nombre del sistema ────────────────────────────────────────────────
        lbl_title = ctk.CTkLabel(
            self,
            text="Smart Locker",
            font=ctk.CTkFont(size=38, weight="bold"),
            text_color=self.TEXT_COLOR,
            fg_color="transparent",
        )
        lbl_title.grid(row=2, column=0)
        lbl_title.bind("<Button-1>", lambda _: self._go_scanning())

        # ── Instrucción principal ─────────────────────────────────────────────
        lbl_instruction = ctk.CTkLabel(
            self,
            text="Acerca tu rostro a la cámara",
            font=ctk.CTkFont(size=22),
            text_color=self.MUTED,
            fg_color="transparent",
        )
        lbl_instruction.grid(row=3, column=0)
        lbl_instruction.bind("<Button-1>", lambda _: self._go_scanning())

        # ── Indicador animado ─────────────────────────────────────────────────
        self.lbl_dot = ctk.CTkLabel(
            self,
            text="● ● ●",
            font=ctk.CTkFont(size=20),
            text_color=self.SECONDARY,
            fg_color="transparent",
        )
        self.lbl_dot.grid(row=4, column=0)
        self.lbl_dot.bind("<Button-1>", lambda _: self._go_scanning())

        # ── Countdown de auto-inicio ──────────────────────────────────────────
        self.lbl_countdown = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=15),
            text_color=self.MUTED,
            fg_color="transparent",
        )
        self.lbl_countdown.grid(row=5, column=0, pady=(0, 30))
        self.lbl_countdown.bind("<Button-1>", lambda _: self._go_scanning())

    # ── Lógica ────────────────────────────────────────────────────────────────

    def on_show(self, **_kwargs) -> None:
        """Llamado por LockerApp.show_frame() al traer esta pantalla al frente."""
        self._countdown = self.AUTO_DELAY
        self._animate_dots()
        self._tick_countdown()

    def on_hide(self, **_kwargs) -> None:
        """Cancela timers pendientes al salir de la pantalla."""
        if self._anim_job is not None:
            self.after_cancel(self._anim_job)
            self._anim_job = None
        if self._nav_job is not None:
            self.after_cancel(self._nav_job)
            self._nav_job = None

    def _tick_countdown(self) -> None:
        """Actualiza el label del countdown y navega a scanning al llegar a 0."""
        if self._countdown > 0:
            self.lbl_countdown.configure(
                text=f"Iniciando escaneo en {self._countdown} s…  (toca para adelantar)"
            )
            self._countdown -= 1
            self._nav_job = self.after(1000, self._tick_countdown)
        else:
            self.lbl_countdown.configure(text="")
            self._go_scanning()

    def _go_scanning(self) -> None:
        """Cancela timers y navega a ScanningScreen."""
        if self._nav_job is not None:
            self.after_cancel(self._nav_job)
            self._nav_job = None
        if self._anim_job is not None:
            self.after_cancel(self._anim_job)
            self._anim_job = None
        from ui.locker_screen.scanning_screen import ScanningScreen
        self.controller.show_frame(ScanningScreen)

    def _animate_dots(self, step: int = 0) -> None:
        """Alterna el brillo del indicador ● ● ● de forma cíclica."""
        patterns = ["●  ○  ○", "○  ●  ○", "○  ○  ●", "○  ●  ○"]
        self.lbl_dot.configure(text=patterns[step % len(patterns)])
        self._anim_job = self.after(500, self._animate_dots, step + 1)
