"""
ResourceSelectScreen – catálogo de recursos compartidos activables (480×800 px).

Se llega aquí SIN autenticar: ModeSelectScreen → aquí directo. A pedido
explícito del usuario (2026-09-30, revirtiendo el orden anterior) primero se
elige el recurso y luego, en DurationSelectScreen, el tiempo — la
autenticación (ScanningScreen, FLOW_RESOURCE_CLAIM_AUTH) es el ÚLTIMO paso,
ahí es donde de verdad se valida autorización (resource_service.
is_user_authorized) y se reclama la sesión. Como todavía no hay usuario
identificado en esta pantalla, el catálogo no puede filtrar por autorización
ni por dueño — solo distingue libre/"EN USO" (`recurso_uso`):
    - libre → "Seleccionar", va a elegir el tiempo
    - "EN USO" → "Ver estado", pide autenticarse (FLOW_RESOURCE_END_AUTH) y
      solo si la identidad coincide con recurso_uso.idUsuario muestra el
      progreso o deja terminar el uso — cualquier otra identidad se deniega
      ahí, no aquí (no hay forma de saber de antemano quién es el dueño)
"""

import customtkinter as ctk
import logging

from services import resource_service
from ui.i18n import t
from ui import theme
from ui.theme import PALETTE

logger = logging.getLogger(__name__)

# Mapeo nombre de recurso (columna `recursos.nombre`) → ícono + claves i18n de
# descripción. Un recurso sin entrada aquí usa el ícono/descripción genéricos.
_RESOURCE_DISPLAY: dict[str, dict] = {
    "taladro": {"icon": "🛠️", "desc_key": "resource.taladro.desc"},
}
_DEFAULT_ICON = "🔧"


def resource_display_name(resource: dict | None) -> str:
    """Nombre a mostrar de un recurso (usado también por ScanningScreen)."""
    if not resource:
        return t("resource.taladro.name")
    return resource.get("nombre") or t("resource.taladro.name")


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
        self._body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._body.pack(fill="both", expand=True, padx=18, pady=(0, 18))

    def _load_resources(self) -> None:
        """Recarga el catálogo real y el estado de uso de cada uno — se llama
        en cada on_show() para no mostrar "EN USO" obsoleto. Sin usuario
        identificado todavía: muestra TODOS los recursos activos, solo
        distinguiendo libre/en uso (la autorización se valida después, al
        autenticar)."""
        for w in self._body.winfo_children():
            w.destroy()

        try:
            resources = resource_service.get_active_resources()
        except Exception as exc:
            logger.warning("No se pudo cargar el catálogo de recursos: %s", exc)
            resources = []

        shown = 0
        for resource in resources:
            session = None
            try:
                session = resource_service.get_active_session(resource["idRecurso"])
            except Exception as exc:
                logger.warning("No se pudo consultar sesión de recurso %s: %s",
                                resource.get("idRecurso"), exc)

            self._build_resource_card(self._body, resource, in_use=session is not None)
            shown += 1

        if shown == 0:
            ctk.CTkLabel(
                self._body,
                text=t("resource.none_available"),
                font=theme.font_body(14),
                text_color=PALETTE["MUTED"],
                fg_color="transparent",
                wraplength=380, justify="center",
            ).pack(pady=40)

    def _build_resource_card(self, parent, resource: dict, in_use: bool = False) -> None:
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

        display = _RESOURCE_DISPLAY.get((resource.get("nombre") or "").strip().lower(), {})

        ctk.CTkLabel(
            inner,
            text=display.get("icon", _DEFAULT_ICON),
            font=ctk.CTkFont(size=34),
            fg_color="transparent",
        ).pack(side="left", padx=(0, 16))

        text_col = ctk.CTkFrame(inner, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)

        name_row = ctk.CTkFrame(text_col, fg_color="transparent")
        name_row.pack(fill="x")

        ctk.CTkLabel(
            name_row,
            text=resource_display_name(resource),
            font=theme.font_display(18, "bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
            anchor="w",
        ).pack(side="left")

        if in_use:
            ctk.CTkLabel(
                name_row,
                text=t("resource.in_use"),
                font=theme.font_body(11, "bold"),
                text_color=PALETTE["WHITE"],
                fg_color=PALETTE["WARN"],
                corner_radius=8,
                width=70, height=22,
            ).pack(side="left", padx=(10, 0))

        desc_key = display.get("desc_key", "")
        if desc_key:
            ctk.CTkLabel(
                text_col,
                text=t(desc_key),
                font=theme.font_body(12),
                text_color=PALETTE["MUTED"],
                fg_color="transparent",
                anchor="w",
                wraplength=220,
                justify="left",
            ).pack(fill="x", pady=(2, 0))

        ctk.CTkButton(
            card,
            text=t("resource.view_status") if in_use else t("resource.select"),
            font=theme.font_body(15, "bold"),
            fg_color=PALETTE["WARN"] if in_use else PALETTE["ACCENT"],
            hover_color=PALETTE["WARN"] if in_use else PALETTE["ACCENT_HOVER"],
            text_color=PALETTE["WHITE"],
            height=48,
            corner_radius=theme.RADIUS_PILL,
            command=(
                (lambda r=resource: self._view_status(r)) if in_use
                else (lambda r=resource: self._select_resource(r))
            ),
        ).pack(fill="x", padx=18, pady=(0, 18))

    # ── Navegación ────────────────────────────────────────────────────────────

    def _select_resource(self, resource: dict) -> None:
        from ui.locker_screen.duration_select_screen import DurationSelectScreen
        self.controller.show_frame(DurationSelectScreen, resource=resource)

    def _view_status(self, resource: dict) -> None:
        # Cualquiera puede tocar "Ver estado" (todavía no sabemos quién es) —
        # FLOW_RESOURCE_END_AUTH autentica y solo deja pasar al dueño real,
        # verificado contra recurso_uso.idUsuario en ese momento.
        from ui.locker_screen.scanning_screen import ScanningScreen
        self.controller.show_frame(
            ScanningScreen,
            mode=ScanningScreen.FLOW_RESOURCE_END_AUTH,
            resource=resource,
        )

    def _go_back(self) -> None:
        from ui.locker_screen.mode_select_screen import ModeSelectScreen
        self.controller.show_frame(ModeSelectScreen)

    # ── API pública ───────────────────────────────────────────────────────────

    def on_show(self) -> None:
        self._load_resources()
