"""
DurationSelectScreen – elige por cuánto tiempo se usará el recurso (480×800 px).

Último paso antes de la autenticación facial en el flujo de "Activar
recurso": ModeSelectScreen → ResourceSelectScreen → aquí → ScanningScreen.

La duración se elige con un temporizador tipo "spinner" (±15 min) en vez de
botones fijos — más granular y compacto en pantalla táctil. La sesión de uso
real (recurso_uso, con su candado de concurrencia) se reclama al autenticarse
en ScanningScreen, no aquí; esta pantalla solo hace una comprobación
defensiva por si el recurso se ocupó justo antes de llegar.
"""

import customtkinter as ctk

from services import resource_service
from ui.i18n import t
from ui import theme
from ui.theme import PALETTE
from ui.locker_screen.resource_select_screen import resource_display_name

# Tope de 3 horas por préstamo — pedido explícitamente para no dejar una
# herramienta activa indefinidamente. Mínimo 30 min, pasos de 15 min.
MIN_MINUTES = 30
MAX_MINUTES = 180
STEP_MINUTES = 15
DEFAULT_MINUTES = 30


def duration_display_label(minutes: int | None) -> str:
    """Etiqueta localizada de una duración (usado también por ScanningScreen).

    Generada dinámicamente (ya no hay una lista fija de valores posibles: el
    usuario elige los minutos libremente con el spinner de esta pantalla).
    """
    if not minutes:
        return "—"
    hours, mins = divmod(int(minutes), 60)
    parts = []
    if hours:
        parts.append(f"{hours} h")
    if mins or not hours:
        parts.append(f"{mins} min")
    return " ".join(parts)


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
        self._minutes = DEFAULT_MINUTES
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

        # ── Temporizador tipo spinner (±15 min, 30 min–3 h) ─────────────────────
        spinner = ctk.CTkFrame(self, fg_color="transparent")
        spinner.pack(fill="both", expand=True, padx=18, pady=(16, 4))

        ctk.CTkButton(
            spinner,
            text="▲",
            font=ctk.CTkFont(size=22, weight="bold"),
            fg_color=PALETTE["CARD"],
            hover_color=PALETTE["ACCENT_SOFT"],
            text_color=PALETTE["TEXT"],
            border_width=1,
            border_color=PALETTE["BORDER"],
            width=72, height=56,
            corner_radius=theme.RADIUS_CARD,
            command=lambda: self._adjust(STEP_MINUTES),
        ).pack(pady=(10, 0))

        self.lbl_duration_preview = ctk.CTkLabel(
            spinner,
            text="",
            font=theme.font_display(40, "bold"),
            text_color=PALETTE["TEXT"],
            fg_color="transparent",
        )
        self.lbl_duration_preview.pack(pady=18)

        ctk.CTkButton(
            spinner,
            text="▼",
            font=ctk.CTkFont(size=22, weight="bold"),
            fg_color=PALETTE["CARD"],
            hover_color=PALETTE["ACCENT_SOFT"],
            text_color=PALETTE["TEXT"],
            border_width=1,
            border_color=PALETTE["BORDER"],
            width=72, height=56,
            corner_radius=theme.RADIUS_CARD,
            command=lambda: self._adjust(-STEP_MINUTES),
        ).pack()

        self.lbl_busy_warning = ctk.CTkLabel(
            self,
            text="",
            font=theme.font_body(13, "bold"),
            text_color=PALETTE["DANGER"],
            fg_color="transparent",
        )
        self.lbl_busy_warning.pack(pady=(0, 4))

        self.btn_confirm = ctk.CTkButton(
            self,
            text=t("duration.confirm"),
            font=theme.font_body(17, "bold"),
            fg_color=PALETTE["ACCENT"],
            hover_color=PALETTE["ACCENT_HOVER"],
            text_color=PALETTE["WHITE"],
            height=58,
            corner_radius=theme.RADIUS_PILL,
            command=self._confirm,
        )
        self.btn_confirm.pack(fill="x", padx=18, pady=(0, 18))

    # ── Temporizador ──────────────────────────────────────────────────────────

    def _adjust(self, delta: int) -> None:
        self._minutes = max(MIN_MINUTES, min(MAX_MINUTES, self._minutes + delta))
        self._render_preview()

    def _render_preview(self) -> None:
        self.lbl_duration_preview.configure(text=duration_display_label(self._minutes))

    # ── Navegación ────────────────────────────────────────────────────────────

    def _confirm(self) -> None:
        # Chequeo defensivo: el recurso pudo ocuparse (otro kiosco) entre que
        # se tocó su tarjeta y se llegó aquí. El candado real vive en
        # resource_service.claim_session(), esto solo evita configurar un
        # tiempo en vano.
        recurso_id = (self._resource or {}).get("idRecurso")
        if recurso_id is not None:
            try:
                if resource_service.get_active_session(recurso_id) is not None:
                    self.lbl_busy_warning.configure(text=t("duration.busy"))
                    self.after(1500, self._go_back)
                    return
            except Exception:
                pass  # si la consulta falla, se deja que claim_session decida

        from ui.locker_screen.scanning_screen import ScanningScreen
        self.controller.show_frame(
            ScanningScreen,
            mode=ScanningScreen.FLOW_RESOURCE,
            resource=self._resource,
            duration_minutes=self._minutes,
        )

    def _go_back(self) -> None:
        from ui.locker_screen.resource_select_screen import ResourceSelectScreen
        self.controller.show_frame(ResourceSelectScreen)

    # ── API pública ───────────────────────────────────────────────────────────

    def on_show(self, resource: dict | None = None) -> None:
        self._resource = resource
        self._minutes = DEFAULT_MINUTES
        self.lbl_busy_warning.configure(text="")
        self._render_preview()
        self.lbl_instruction.configure(
            text=t("duration.instruction", resource=resource_display_name(resource))
        )
