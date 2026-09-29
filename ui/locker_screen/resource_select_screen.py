"""
ResourceSelectScreen – catálogo de recursos compartidos activables (480×800 px).

Se llega aquí desde ModeSelectScreen al elegir "Activar recurso". Muestra
tarjetas seleccionables; hoy solo existe el Taladro (TOOL_GPIO_CONFIG en
config.py solo tiene ese canal), pero la lista está pensada para crecer sin
tocar el layout — agregar una entrada a AVAILABLE_RESOURCES basta.

Solo interfaz: no consulta la BD ni valida permisos todavía (eso llega junto
con la conexión real del relay del taladro).
"""

import customtkinter as ctk
import logging

from ui.i18n import t
from ui import theme
from ui.theme import PALETTE

logger = logging.getLogger(__name__)

# Catálogo de recursos activables. Cada entrada: id interno (para más adelante
# mapear con TOOL_GPIO_CONFIG["pins"]), ícono (emoji, sin depender de glifos
# de Font Awesome no definidos en ui/theme.py), y claves i18n de nombre/desc.
AVAILABLE_RESOURCES: list[dict] = [
    {
        "id": "taladro",
        "icon": "🛠️",
        "name_key": "resource.taladro.name",
        "desc_key": "resource.taladro.desc",
    },
]


def resource_display_name(resource: dict | None) -> str:
    """Nombre localizado de un recurso (usado también por ScanningScreen)."""
    if resource and resource.get("name_key"):
        return t(resource["name_key"])
    return t("resource.taladro.name")


class ResourceSelectScreen(ctk.CTkFrame):
    """
    Catálogo de recursos compartidos (modo kiosk).

    Parámetros
    ----------
    parent     : widget padre (la ventana raíz LockerApp)
    controller : LockerApp – expone show_frame() para navegar
    """

    BG_COLOR = PALETTE["BG"]

    def __init__(self, parent: ctk.CTk, controller):
        super().__init__(parent, fg_color=self.BG_COLOR, corner_radius=0)
        self.controller = controller
        self._build_ui()

    # ── Construcción de widgets ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ── Encabezado con botón de volver ─────────────────────────────────────
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

        # ── Título + instrucción ────────────────────────────────────────────────
        title_block = ctk.CTkFrame(self, fg_color="transparent")
        title_block.pack(fill="x", padx=24, pady=(10, 16))

        ctk.CTkLabel(
            title_block,
            text=t("resource.page_title"),
            font=theme.font_display(24, "bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_block,
            text=t("resource.instruction"),
            font=theme.font_body(14),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        # ── Lista de recursos ────────────────────────────────────────────────
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        for resource in AVAILABLE_RESOURCES:
            self._build_resource_card(body, resource)

    def _build_resource_card(self, parent, resource: dict) -> None:
        card = ctk.CTkFrame(
            parent,
            fg_color=PALETTE["CARD"],
            corner_radius=theme.RADIUS_CARD,
            border_width=1,
            border_color=PALETTE["BORDER"],
        )
        card.pack(fill="x", pady=(0, 14))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=18)

        ctk.CTkLabel(
            inner,
            text=resource.get("icon", "🔧"),
            font=ctk.CTkFont(size=34),
            fg_color="transparent",
        ).pack(side="left", padx=(0, 16))

        text_col = ctk.CTkFrame(inner, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            text_col,
            text=resource_display_name(resource),
            font=theme.font_display(18, "bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            text_col,
            text=t(resource.get("desc_key", "")),
            font=theme.font_body(12),
            text_color=PALETTE["MUTED"],
            fg_color="transparent",
            anchor="w",
            wraplength=220,
            justify="left",
        ).pack(fill="x", pady=(2, 0))

        ctk.CTkButton(
            card,
            text=t("resource.select"),
            font=theme.font_body(15, "bold"),
            fg_color=PALETTE["ACCENT"],
            hover_color=PALETTE["ACCENT_HOVER"],
            text_color=PALETTE["WHITE"],
            height=48,
            corner_radius=theme.RADIUS_PILL,
            command=lambda r=resource: self._select_resource(r),
        ).pack(fill="x", padx=18, pady=(0, 18))

    # ── Navegación ────────────────────────────────────────────────────────────

    def _select_resource(self, resource: dict) -> None:
        from ui.locker_screen.duration_select_screen import DurationSelectScreen
        self.controller.show_frame(DurationSelectScreen, resource=resource)

    def _go_back(self) -> None:
        from ui.locker_screen.mode_select_screen import ModeSelectScreen
        self.controller.show_frame(ModeSelectScreen)

    # ── API pública ───────────────────────────────────────────────────────────

    def on_show(self) -> None:
        pass
