"""
UserDisplayScreen – pantalla de acceso concedido (800×480 px).

Muestra el nombre del usuario, número de casillero y fecha/hora.
Después de DISPLAY_SECONDS segundos vuelve automáticamente a StandbyScreen.
"""

import customtkinter as ctk


class UserDisplayScreen(ctk.CTkFrame):
    """
    Pantalla post-autenticación exitosa.

    Parámetros
    ----------
    parent     : widget padre (LockerApp)
    controller : LockerApp – expone show_frame()
    """

    BG_COLOR   = "#F5F0EB"
    PRIMARY    = "#5B8C5A"
    SUCCESS    = "#5B8C5A"
    TEXT_COLOR = "#3D3D3D"
    MUTED      = "#8C8279"

    DISPLAY_SECONDS = 8   # tiempo antes de volver a standby

    def __init__(self, parent: ctk.CTk, controller) -> None:
        super().__init__(parent, fg_color=self.BG_COLOR, corner_radius=0)
        self.controller   = controller
        self._return_job  = None
        self._build_ui()

    # ── Construcción de UI ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Layout vertical aprovecha la altura de 800 px
        self.grid_rowconfigure((0, 1, 2, 3, 4, 5, 6), weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Espacio superior ──────────────────────────────────────────────────
        ctk.CTkLabel(self, text="", fg_color="transparent").grid(row=0, column=0)

        # ── Ícono de éxito ────────────────────────────────────────────────────
        lbl_check = ctk.CTkLabel(
            self,
            text="OK",
            font=ctk.CTkFont(size=110, weight="bold"),
            text_color=self.SUCCESS,
            fg_color="transparent",
        )
        lbl_check.grid(row=1, column=0)

        # ── Bienvenida ────────────────────────────────────────────────────────
        lbl_welcome = ctk.CTkLabel(
            self,
            text="Acceso concedido",
            font=ctk.CTkFont(size=22),
            text_color=self.MUTED,
            fg_color="transparent",
        )
        lbl_welcome.grid(row=2, column=0)

        # ── Nombre del usuario ────────────────────────────────────────────────
        self.lbl_nombre = ctk.CTkLabel(
            self,
            text="—",
            font=ctk.CTkFont(size=34, weight="bold"),
            text_color=self.TEXT_COLOR,
            fg_color="transparent",
        )
        self.lbl_nombre.grid(row=3, column=0, pady=(10, 0))

        # ── Número de casillero ───────────────────────────────────────────────
        self.lbl_locker = ctk.CTkLabel(
            self,
            text="Casillero  —",
            font=ctk.CTkFont(size=30),
            text_color=self.PRIMARY,
            fg_color="transparent",
        )
        self.lbl_locker.grid(row=4, column=0, pady=(6, 0))

        # ── Fecha y hora ──────────────────────────────────────────────────────
        self.lbl_fecha = ctk.CTkLabel(
            self,
            text="—",
            font=ctk.CTkFont(size=18),
            text_color=self.MUTED,
            fg_color="transparent",
        )
        self.lbl_fecha.grid(row=5, column=0, pady=(6, 0))

        # ── Contador regresivo ────────────────────────────────────────────────
        self.lbl_countdown = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=15),
            text_color=self.MUTED,
            fg_color="transparent",
        )
        self.lbl_countdown.grid(row=6, column=0, pady=(0, 30))

    # ── API pública ───────────────────────────────────────────────────────────

    def load_user(self, user_data: dict) -> None:
        """
        Carga los datos del usuario autenticado.

        user_data = {
            "nombre":        str,
            "locker_numero": int,
            "fecha":         str,
        }
        """
        self.lbl_nombre.configure(text=user_data.get("nombre", "—"))
        self.lbl_locker.configure(
            text=f"Casillero  {user_data.get('locker_numero', '—')}"
        )
        self.lbl_fecha.configure(text=user_data.get("fecha", "—"))

    def on_show(self, user_data: dict | None = None, **_kwargs) -> None:
        """Carga datos (si vienen) e inicia el contador regresivo."""
        if user_data:
            self.load_user(user_data)
        self._start_countdown(self.DISPLAY_SECONDS)

    def on_hide(self) -> None:
        """Cancela el countdown pendiente al salir de la pantalla."""
        if self._return_job is not None:
            self.after_cancel(self._return_job)
            self._return_job = None

    # ── Métodos internos ──────────────────────────────────────────────────────

    def _start_countdown(self, seconds: int) -> None:
        if self._return_job is not None:
            self.after_cancel(self._return_job)

        if seconds <= 0:
            self._go_standby()
            return

        self.lbl_countdown.configure(
            text=f"Volviendo al inicio en {seconds} s…"
        )
        self._return_job = self.after(
            1000, self._start_countdown, seconds - 1
        )

    def _go_standby(self) -> None:
        from ui.locker_screen.standby_screen import StandbyScreen
        self.controller.show_frame(StandbyScreen)

