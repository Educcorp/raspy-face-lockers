"""
DurationSelectScreen – elige por cuánto tiempo se usará el recurso (480×800 px).

Último paso antes de la autenticación facial en el flujo de "Activar
recurso": ModeSelectScreen → ResourceSelectScreen → aquí → ScanningScreen.

Solo interfaz: la duración elegida se pasa a ScanningScreen para mostrarla en
el overlay de éxito. Controlar que la herramienta se desactive sola al
cumplirse el tiempo es parte de la conexión real (pendiente, ver
core/tool_gpio_controller.py).
"""

import customtkinter as ctk

from ui.i18n import t
from ui import theme
from ui.theme import PALETTE
from ui.locker_screen.resource_select_screen import resource_display_name

# (minutos, clave i18n de la etiqueta). Tope de 3 horas por préstamo — pedido
# explícitamente para no dejar una herramienta activa indefinidamente antes
# de que exista el control real por presencia/permisos.
DURATIONS: list[tuple[int, str]] = [
    (30,  "duration.30min"),
    (60,  "duration.1h"),
    (90,  "duration.1h30"),
    (120, "duration.2h"),
    (150, "duration.2h30"),
    (180, "duration.3h"),
]


def duration_display_label(minutes: int | None) -> str:
    """Etiqueta localizada de una duración (usado también por ScanningScreen)."""
    for m, key in DURATIONS:
        if m == minutes:
            return t(key)
    if minutes:
        return f"{minutes} min"
    return "—"


class DurationSelectScreen(ctk.CTkFrame):
    """
    Selección del tiempo de uso del recurso (modo kiosk).

    Parámetros
    ----------
    parent     : widget padre (la ventana raíz LockerApp)
    controller : LockerApp – expone show_frame() para navegar
    """

    BG_COLOR = PALETTE["BG"]

    def __init__(self, parent: ctk.CTk, controller):
        super().__init__(parent, fg_color=self.BG_COLOR, corner_radius=0)
        self.controller = controller
        self._resource: dict | None = None
        self._build_ui()

    # ── Construcción de widgets ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent", height=64)
        header.pack(fill="x", padx=18, pady=(18, 6))

        ctk.CTkButton(
            header,
            text=t("common.back"),
            font=theme.font_body(14, "bold"),
            fg_color="transparent",
            hover_color=PALETTE["SURFACE_ALT"],
            text_color=PALETTE["TEXT"],
            width=110, height=40,
            corner_radius=14,
            command=self._go_back,
        ).pack(side="left")

        title_block = ctk.CTkFrame(self, fg_color="transparent")
        title_block.pack(fill="x", padx=24, pady=(10, 4))

        ctk.CTkLabel(
            title_block,
            text=t("duration.page_title"),
            font=theme.font_display(24, "bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
        ).pack(anchor="w")

        self.lbl_instruction = ctk.CTkLabel(
            title_block,
            text="",
            font=theme.font_body(14),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
            wraplength=420,
            justify="left",
        )
        self.lbl_instruction.pack(anchor="w", pady=(4, 0))

        ctk.CTkLabel(
            title_block,
            text=t("duration.max_note"),
            font=theme.font_body(12, "bold"),
            text_color=PALETTE["WARN"],
            fg_color="transparent",
        ).pack(anchor="w", pady=(8, 0))

        # ── Grilla de duraciones (2 columnas) ──────────────────────────────────
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=18, pady=(16, 18))
        grid.grid_columnconfigure((0, 1), weight=1, uniform="dur")

        for idx, (minutes, key) in enumerate(DURATIONS):
            row, col = divmod(idx, 2)
            ctk.CTkButton(
                grid,
                text=t(key),
                font=theme.font_body(18, "bold"),
                fg_color=PALETTE["CARD"],
                hover_color=PALETTE["ACCENT_SOFT"],
                text_color=PALETTE["TEXT"],
                border_width=1,
                border_color=PALETTE["BORDER"],
                height=88,
                corner_radius=theme.RADIUS_CARD,
                command=lambda m=minutes: self._select_duration(m),
            ).grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

    # ── Navegación ────────────────────────────────────────────────────────────

    def _select_duration(self, minutes: int) -> None:
        from ui.locker_screen.scanning_screen import ScanningScreen
        self.controller.show_frame(
            ScanningScreen,
            mode="recurso",
            resource=self._resource,
            duration_minutes=minutes,
        )

    def _go_back(self) -> None:
        from ui.locker_screen.resource_select_screen import ResourceSelectScreen
        self.controller.show_frame(ResourceSelectScreen)

    # ── API pública ───────────────────────────────────────────────────────────

    def on_show(self, resource: dict | None = None) -> None:
        self._resource = resource
        self.lbl_instruction.configure(
            text=t("duration.instruction", resource=resource_display_name(resource))
        )
